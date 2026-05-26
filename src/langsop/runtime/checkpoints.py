"""Checkpoint models for the bounded IR4 runtime graph proof.

Checkpoint records are generated execution state only. This module validates
freshness and authority boundaries without reading or writing checkpoint files.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json

from .graph_state import (
    GraphIssue,
    GraphIssueKind,
    GraphIssueSeverity,
    GraphValidationResult,
    NON_AUTHORITY_WARNING,
)


CHECKPOINT_SCHEMA_VERSION = "ir4-runtime-checkpoint-v1"


class CheckpointFreshnessResult(str, Enum):
    """Checkpoint freshness classifications from the accepted policy."""

    CURRENT = "current"
    STALE = "stale"
    CHECKPOINT_AUTHORITY_CONFUSION = "checkpoint_authority_confusion"


class CheckpointAuthorityResult(str, Enum):
    """Authority-boundary classifications for checkpoint records."""

    NON_AUTHORITATIVE_EXECUTION_STATE = "non_authoritative_execution_state"
    AUTHORITY_CONFUSION_DETECTED = "authority_confusion_detected"
    CHECKPOINT_READINESS_AUTHORITY_CONFUSION = "checkpoint_readiness_authority_confusion"


class CheckpointResumeCondition(str, Enum):
    """Accepted resume conditions for checkpoint validation results."""

    NOT_REQUIRED = "not_required"
    REBUILD_FROM_SOURCE_AUTHORITY = "rebuild_from_source_authority"
    ACCEPTED_AUTHORITY_RECONCILIATION = "accepted_authority_reconciliation"
    ACCEPTED_COMPLETION_REVIEW_REQUIRED = "accepted_completion_review_required"
    ACCEPTED_REPAIR_REVIEW_REQUIRED = "accepted_repair_review_required"


@dataclass(frozen=True)
class CheckpointEnvelope:
    """Projection-only checkpoint record used by later runner code."""

    checkpoint_id: str
    fixture_id: str
    active_work_packet_ref: str
    freshness_basis_ref_set: tuple[str, ...]
    graph_phase: str
    current_node_id: str
    checkpoint_schema_version: str = CHECKPOINT_SCHEMA_VERSION
    checkpoint_status: str = "generated_projection_only"
    presented_as_authority: bool = False
    claims_readiness: bool = False
    pending_interrupt_ref: str | None = None
    non_authority_warning: str = NON_AUTHORITY_WARNING


@dataclass(frozen=True)
class CheckpointValidationResult:
    """Pure checkpoint validation result."""

    checkpoint_freshness_result: CheckpointFreshnessResult
    checkpoint_authority_result: CheckpointAuthorityResult
    resume_condition: CheckpointResumeCondition
    validation: GraphValidationResult

    @property
    def accepted(self) -> bool:
        return self.validation.accepted


def deterministic_checkpoint_id(
    *,
    fixture_id: str,
    active_work_packet_ref: str,
    freshness_basis_ref_set: tuple[str, ...],
    graph_phase: str,
    current_node_id: str,
    checkpoint_schema_version: str = CHECKPOINT_SCHEMA_VERSION,
) -> str:
    """Return a stable id for fixed checkpoint contents."""

    payload = {
        "active_work_packet_ref": active_work_packet_ref,
        "checkpoint_schema_version": checkpoint_schema_version,
        "current_node_id": current_node_id,
        "fixture_id": fixture_id,
        "freshness_basis_ref_set": sorted(freshness_basis_ref_set),
        "graph_phase": graph_phase,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_checkpoint_envelope(
    *,
    fixture_id: str,
    active_work_packet_ref: str,
    freshness_basis_ref_set: tuple[str, ...],
    graph_phase: str,
    current_node_id: str,
    presented_as_authority: bool = False,
    claims_readiness: bool = False,
    pending_interrupt_ref: str | None = None,
) -> CheckpointEnvelope:
    """Build a projection-only checkpoint envelope without persisting it."""

    checkpoint_id = deterministic_checkpoint_id(
        fixture_id=fixture_id,
        active_work_packet_ref=active_work_packet_ref,
        freshness_basis_ref_set=tuple(freshness_basis_ref_set),
        graph_phase=graph_phase,
        current_node_id=current_node_id,
    )
    return CheckpointEnvelope(
        checkpoint_id=checkpoint_id,
        fixture_id=fixture_id,
        active_work_packet_ref=active_work_packet_ref,
        freshness_basis_ref_set=tuple(freshness_basis_ref_set),
        graph_phase=graph_phase,
        current_node_id=current_node_id,
        presented_as_authority=presented_as_authority,
        claims_readiness=claims_readiness,
        pending_interrupt_ref=pending_interrupt_ref,
    )


def validate_checkpoint(
    checkpoint: CheckpointEnvelope,
    *,
    accepted_freshness_basis_ref_set: tuple[str, ...],
) -> CheckpointValidationResult:
    """Validate checkpoint freshness and authority without trusting its state."""

    issues: list[GraphIssue] = []
    authority_result = CheckpointAuthorityResult.NON_AUTHORITATIVE_EXECUTION_STATE
    freshness_result = CheckpointFreshnessResult.CURRENT
    resume_condition = CheckpointResumeCondition.NOT_REQUIRED

    if checkpoint.presented_as_authority:
        authority_result = CheckpointAuthorityResult.AUTHORITY_CONFUSION_DETECTED
        freshness_result = CheckpointFreshnessResult.CHECKPOINT_AUTHORITY_CONFUSION
        resume_condition = CheckpointResumeCondition.ACCEPTED_AUTHORITY_RECONCILIATION
        issues.append(
            GraphIssue(
                GraphIssueKind.CHECKPOINT_AUTHORITY_CONFUSION,
                GraphIssueSeverity.INTERRUPT,
                "checkpoint state was presented as source authority",
                "presented_as_authority",
            )
        )

    if checkpoint.claims_readiness:
        authority_result = CheckpointAuthorityResult.CHECKPOINT_READINESS_AUTHORITY_CONFUSION
        freshness_result = CheckpointFreshnessResult.CHECKPOINT_AUTHORITY_CONFUSION
        resume_condition = CheckpointResumeCondition.ACCEPTED_COMPLETION_REVIEW_REQUIRED
        issues.append(
            GraphIssue(
                GraphIssueKind.CHECKPOINT_AUTHORITY_CONFUSION,
                GraphIssueSeverity.FAULT,
                "checkpoint state attempted to satisfy readiness or gate authority",
                "claims_readiness",
            )
        )

    if set(checkpoint.freshness_basis_ref_set) != set(accepted_freshness_basis_ref_set):
        freshness_result = CheckpointFreshnessResult.STALE
        if resume_condition == CheckpointResumeCondition.NOT_REQUIRED:
            resume_condition = CheckpointResumeCondition.REBUILD_FROM_SOURCE_AUTHORITY
        issues.append(
            GraphIssue(
                GraphIssueKind.STALE_PROJECTION,
                GraphIssueSeverity.STALE,
                "checkpoint freshness basis does not match accepted source state",
                "freshness_basis_ref_set",
            )
        )

    if checkpoint.checkpoint_status != "generated_projection_only":
        authority_result = CheckpointAuthorityResult.AUTHORITY_CONFUSION_DETECTED
        freshness_result = CheckpointFreshnessResult.CHECKPOINT_AUTHORITY_CONFUSION
        resume_condition = CheckpointResumeCondition.ACCEPTED_REPAIR_REVIEW_REQUIRED
        issues.append(
            GraphIssue(
                GraphIssueKind.GENERATED_AUTHORITY,
                GraphIssueSeverity.FAULT,
                "checkpoint status must remain generated_projection_only",
                "checkpoint_status",
            )
        )

    return CheckpointValidationResult(
        checkpoint_freshness_result=freshness_result,
        checkpoint_authority_result=authority_result,
        resume_condition=resume_condition,
        validation=GraphValidationResult(not issues, tuple(issues)),
    )
