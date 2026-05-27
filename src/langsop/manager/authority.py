"""Authority classification helpers for IR8 manager records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .records import (
    ManagerAuthorityClass,
    ManagerIssue,
    ManagerIssueKind,
    ManagerIssueSeverity,
)


SOURCE_RECORD_KIND_SET: frozenset[str] = frozenset(
    {"source_document", "canonical_specification", "sjs_signature", "completion_review"}
)
EXECUTION_EVIDENCE_KIND_SET: frozenset[str] = frozenset({"accepted_proof_pack", "accepted_test_result"})
COORDINATION_KIND_SET: frozenset[str] = frozenset({"coordination_claim", "rendezvous_packet"})
OPERATIONS_DRY_RUN_KIND_SET: frozenset[str] = frozenset({"operation_dry_run_result", "dry_run_evidence"})
GENERATED_PROJECTION_KIND_SET: frozenset[str] = frozenset({"generated_projection", "generated_report"})
GRAPH_CHECKPOINT_KIND_SET: frozenset[str] = frozenset({"graph_checkpoint", "langgraph_checkpoint"})
CARRIER_CONTEXT_KIND_SET: frozenset[str] = frozenset({"mailbox_message", "chat_message", "terminal_output"})
HUMAN_OVERRIDE_KIND_SET: frozenset[str] = frozenset({"human_override", "human_approval"})

PROMOTABLE_TO_SOURCE_AUTHORITY_SET: frozenset[ManagerAuthorityClass] = frozenset(
    {ManagerAuthorityClass.SOURCE_AUTHORITY}
)


@dataclass(frozen=True)
class ManagerAuthorityClassification:
    """Pure authority classification result for one manager-visible record."""

    record_ref: str
    record_kind: str
    authority_class: ManagerAuthorityClass
    issues: tuple[ManagerIssue, ...] = ()
    source_authority_promoted: bool = False
    dispatch_authorized: bool = False
    live_effect_performed: bool = False

    @property
    def accepted(self) -> bool:
        return not self.issues


def classify_manager_record_authority(
    record_kind: str,
    *,
    requested_promotion: str = "",
) -> ManagerAuthorityClass:
    """Classify a manager-visible record without granting new authority."""

    if record_kind in SOURCE_RECORD_KIND_SET:
        return ManagerAuthorityClass.SOURCE_AUTHORITY
    if record_kind in EXECUTION_EVIDENCE_KIND_SET:
        return ManagerAuthorityClass.ACCEPTED_EXECUTION_EVIDENCE
    if record_kind in COORDINATION_KIND_SET:
        return ManagerAuthorityClass.COORDINATION_RECORD
    if record_kind in OPERATIONS_DRY_RUN_KIND_SET:
        return ManagerAuthorityClass.OPERATIONS_DRY_RUN_RECORD
    if record_kind in GENERATED_PROJECTION_KIND_SET:
        return ManagerAuthorityClass.GENERATED_PROJECTION
    if record_kind in GRAPH_CHECKPOINT_KIND_SET:
        return ManagerAuthorityClass.GRAPH_CHECKPOINT
    if record_kind in CARRIER_CONTEXT_KIND_SET:
        return ManagerAuthorityClass.CARRIER_CONTEXT
    if record_kind in HUMAN_OVERRIDE_KIND_SET:
        return ManagerAuthorityClass.HUMAN_OVERRIDE_CONTEXT
    if requested_promotion == "source_authority":
        return ManagerAuthorityClass.UNKNOWN
    return ManagerAuthorityClass.MANAGER_PLANNING_RECORD


def classify_manager_authority_from_mapping(data: Mapping[str, object]) -> ManagerAuthorityClassification:
    """Classify a manager-visible mapping by record kind and promotion request."""

    return validate_manager_authority_classification(
        record_ref=str(data.get("record_ref", data.get("fixture_case_id", ""))),
        record_kind=str(data.get("record_kind", data.get("carrier_context_kind", ""))),
        requested_promotion=str(data.get("requested_promotion", "")),
        source_authority_promoted=_as_bool(data.get("source_authority_promoted", False)),
        dispatch_authorized=_as_bool(data.get("dispatch_authorized", False)),
        live_effect_performed=_as_bool(data.get("live_effect_performed", False)),
    )


def validate_manager_authority_classification(
    *,
    record_ref: str,
    record_kind: str,
    requested_promotion: str = "",
    source_authority_promoted: bool = False,
    dispatch_authorized: bool = False,
    live_effect_performed: bool = False,
) -> ManagerAuthorityClassification:
    """Validate a record classification against IR8 non-promotion rules."""

    authority_class = classify_manager_record_authority(record_kind, requested_promotion=requested_promotion)
    issues: list[ManagerIssue] = []
    if not record_ref:
        issues.append(
            ManagerIssue(
                ManagerIssueKind.MISSING_FIELD,
                ManagerIssueSeverity.FAULT,
                "record_ref is required",
                "record_ref",
            )
        )

    if requested_promotion == "source_authority" and authority_class not in PROMOTABLE_TO_SOURCE_AUTHORITY_SET:
        issues.append(
            _promotion_issue_for_authority_class(authority_class, "requested_promotion")
        )

    if source_authority_promoted and authority_class not in PROMOTABLE_TO_SOURCE_AUTHORITY_SET:
        issues.append(
            _promotion_issue_for_authority_class(authority_class, "source_authority_promoted")
        )

    if dispatch_authorized:
        issues.append(
            ManagerIssue(
                ManagerIssueKind.DISPATCH_REQUESTED,
                ManagerIssueSeverity.REFUSED,
                "manager authority classification may not authorize dispatch",
                "dispatch_authorized",
            )
        )

    if live_effect_performed:
        issues.append(
            ManagerIssue(
                ManagerIssueKind.LIVE_EFFECT_REQUESTED,
                ManagerIssueSeverity.REFUSED,
                "manager authority classification may not perform live effects",
                "live_effect_performed",
            )
        )

    return ManagerAuthorityClassification(
        record_ref=record_ref,
        record_kind=record_kind,
        authority_class=authority_class,
        issues=tuple(issues),
        source_authority_promoted=False,
        dispatch_authorized=False,
        live_effect_performed=False,
    )


def _promotion_issue_for_authority_class(
    authority_class: ManagerAuthorityClass,
    field_name: str,
) -> ManagerIssue:
    if authority_class == ManagerAuthorityClass.GENERATED_PROJECTION:
        kind = ManagerIssueKind.GENERATED_OUTPUT_AUTHORITY_PROMOTION
    elif authority_class == ManagerAuthorityClass.GRAPH_CHECKPOINT:
        kind = ManagerIssueKind.GRAPH_CHECKPOINT_AUTHORITY_PROMOTION
    elif authority_class == ManagerAuthorityClass.OPERATIONS_DRY_RUN_RECORD:
        kind = ManagerIssueKind.DRY_RUN_TO_LIVE_CONTROL_PROMOTION
    else:
        kind = ManagerIssueKind.MISSING_SOURCE_AUTHORITY
    return ManagerIssue(
        kind,
        ManagerIssueSeverity.REFUSED,
        f"{authority_class.value} cannot be promoted to source or dispatch authority",
        field_name,
    )


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes"}
    return bool(value)
