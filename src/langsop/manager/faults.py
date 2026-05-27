"""Fault records for IR8 manager projection.

Fault records are review evidence only. They never dispatch agents, execute
commands, control resources, or promote generated context to authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .records import (
    ManagerIssue,
    ManagerIssueKind,
    ManagerIssueSeverity,
    ManagerReadinessResult,
    NO_DISPATCH_NOTICE,
)


class ManagerFaultKind(str, Enum):
    """Accepted IR8 manager fault kinds."""

    STALE_BOUNDARY_INPUT = "stale_boundary_input"
    UNSUPPORTED_REQUIREMENT = "unsupported_requirement"
    CONTESTED_COORDINATION_CLAIM = "contested_coordination_claim"
    UNCLASSIFIED_AUTHORITY_SENSITIVE_RECORD = "unclassified_authority_sensitive_record"
    GENERATED_OUTPUT_AUTHORITY_PROMOTION = "generated_output_authority_promotion"
    GRAPH_CHECKPOINT_AUTHORITY_PROMOTION = "graph_checkpoint_authority_promotion"
    DRY_RUN_TO_LIVE_CONTROL_PROMOTION = "dry_run_to_live_control_promotion"
    HUMAN_OVERRIDE_REQUIRED = "human_override_required"
    REQUESTED_FORBIDDEN_SCOPE = "requested_forbidden_scope"
    MODEL_ROUTE_AMBIGUITY = "model_route_ambiguity"
    COMPLETION_GATE_BYPASS = "completion_gate_bypass"
    PROOF_OBLIGATION_BYPASS = "proof_obligation_bypass"
    DISPATCH_REQUESTED = "dispatch_requested"
    LIVE_EFFECT_REQUESTED = "live_effect_requested"
    UNKNOWN_MANAGER_FAULT = "unknown_manager_fault"


class ManagerFaultSeverity(str, Enum):
    """Fault severity vocabulary for review routing."""

    BLOCKED = "blocked"
    STALE = "stale"
    FAULT = "fault"
    INTERRUPT = "interrupt"
    REFUSED = "refused"


@dataclass(frozen=True)
class ManagerFaultRecord:
    """Durable fault evidence emitted by manager projection."""

    fault_id: str
    fault_kind: ManagerFaultKind
    severity: ManagerFaultSeverity
    work_ref: str
    evidence_ref_set: tuple[str, ...]
    triggering_record_ref_set: tuple[str, ...]
    missing_requirement_set: tuple[str, ...] = ()
    safe_next_route: str = "SOP_first_review"
    non_authority_notice: str = NO_DISPATCH_NOTICE
    dispatch_authorized: bool = False
    live_effect_performed: bool = False


def manager_fault_record_from_issue(
    issue: ManagerIssue,
    *,
    work_ref: str,
    evidence_ref_set: Iterable[str] = (),
    triggering_record_ref_set: Iterable[str] = (),
    missing_requirement_set: Iterable[str] = (),
) -> ManagerFaultRecord:
    """Project a fault record from a manager issue."""

    fault_kind = fault_kind_for_issue_kind(issue.issue_kind)
    return ManagerFaultRecord(
        fault_id=f"{work_ref}:{fault_kind.value}",
        fault_kind=fault_kind,
        severity=ManagerFaultSeverity(issue.severity.value),
        work_ref=work_ref,
        evidence_ref_set=tuple(evidence_ref_set),
        triggering_record_ref_set=tuple(triggering_record_ref_set),
        missing_requirement_set=tuple(missing_requirement_set),
        safe_next_route=safe_next_route_for_fault(fault_kind, issue.severity),
        dispatch_authorized=False,
        live_effect_performed=False,
    )


def manager_fault_records_from_readiness(
    readiness: ManagerReadinessResult,
    *,
    work_ref: str,
    evidence_ref_set: Iterable[str] = (),
) -> tuple[ManagerFaultRecord, ...]:
    """Project fault records from all readiness issues."""

    evidence = tuple(evidence_ref_set)
    return tuple(
        manager_fault_record_from_issue(
            issue,
            work_ref=work_ref,
            evidence_ref_set=evidence,
            triggering_record_ref_set=(issue.field_name,) if issue.field_name else (),
            missing_requirement_set=_missing_requirement_for_issue(issue),
        )
        for issue in readiness.issues
    )


def fault_kind_for_issue_kind(issue_kind: ManagerIssueKind) -> ManagerFaultKind:
    """Map manager issue vocabulary to durable fault kinds."""

    try:
        return ManagerFaultKind(issue_kind.value)
    except ValueError:
        return ManagerFaultKind.UNKNOWN_MANAGER_FAULT


def safe_next_route_for_fault(
    fault_kind: ManagerFaultKind,
    severity: ManagerIssueSeverity | ManagerFaultSeverity,
) -> str:
    """Return the safe route that preserves SOP-first review."""

    if fault_kind in {
        ManagerFaultKind.STALE_BOUNDARY_INPUT,
        ManagerFaultKind.COMPLETION_GATE_BYPASS,
        ManagerFaultKind.PROOF_OBLIGATION_BYPASS,
    }:
        return "rebake_or_refresh_authority"
    if fault_kind in {
        ManagerFaultKind.UNCLASSIFIED_AUTHORITY_SENSITIVE_RECORD,
        ManagerFaultKind.MODEL_ROUTE_AMBIGUITY,
    }:
        return "classify_and_route_before_action"
    if fault_kind in {
        ManagerFaultKind.GENERATED_OUTPUT_AUTHORITY_PROMOTION,
        ManagerFaultKind.GRAPH_CHECKPOINT_AUTHORITY_PROMOTION,
        ManagerFaultKind.DRY_RUN_TO_LIVE_CONTROL_PROMOTION,
        ManagerFaultKind.REQUESTED_FORBIDDEN_SCOPE,
        ManagerFaultKind.DISPATCH_REQUESTED,
        ManagerFaultKind.LIVE_EFFECT_REQUESTED,
    }:
        return "refuse_and_require_separate_authority"
    if str(severity) in {ManagerIssueSeverity.INTERRUPT.value, ManagerFaultSeverity.INTERRUPT.value}:
        return "SOP_first_interrupt_review"
    return "SOP_first_review"


def validate_manager_fault_record(record: ManagerFaultRecord) -> bool:
    """Return true when a fault record preserves no-dispatch and no-live-effect."""

    return (
        bool(record.fault_id)
        and bool(record.work_ref)
        and bool(record.evidence_ref_set or record.triggering_record_ref_set or record.missing_requirement_set)
        and record.non_authority_notice == NO_DISPATCH_NOTICE
        and not record.dispatch_authorized
        and not record.live_effect_performed
    )


def _missing_requirement_for_issue(issue: ManagerIssue) -> tuple[str, ...]:
    if issue.issue_kind == ManagerIssueKind.UNSUPPORTED_REQUIREMENT:
        return ("accepted_support_record",)
    if issue.issue_kind == ManagerIssueKind.MODEL_ROUTE_AMBIGUITY:
        return ("model_route",)
    if issue.issue_kind == ManagerIssueKind.COMPLETION_GATE_BYPASS:
        return ("completion_review",)
    if issue.issue_kind == ManagerIssueKind.PROOF_OBLIGATION_BYPASS:
        return ("proof_obligation",)
    return ()
