"""Handoff, human override, and refusal records for IR8 manager projection."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .faults import ManagerFaultRecord, manager_fault_records_from_readiness
from .records import (
    ManagerIssue,
    ManagerIssueKind,
    ManagerIssueSeverity,
    ManagerReadinessResult,
    NO_DISPATCH_NOTICE,
    NO_LIVE_EFFECT_NOTICE,
)


class ManagerHandoffKind(str, Enum):
    """Accepted IR8 manager handoff kinds."""

    MANAGER_TO_SURFACE = "manager_to_surface"
    SURFACE_TO_MANAGER = "surface_to_manager"
    MANAGER_COORDINATION = "manager_coordination"
    MANAGER_OPERATIONS = "manager_operations"
    HUMAN_OVERRIDE = "human_override"
    REFUSAL = "refusal"
    INTERRUPT = "interrupt"


class ManagerHandoffStatus(str, Enum):
    """Handoff status without dispatch authority."""

    READY_FOR_REVIEW = "ready_for_review"
    BLOCKED = "blocked"
    INTERRUPTED = "interrupted"
    REFUSED = "refused"
    CONTEXT_ONLY = "context_only"


@dataclass(frozen=True)
class ManagerHandoffRecord:
    """Handoff evidence between manager, surfaces, coordination, or operations."""

    handoff_id: str
    handoff_kind: ManagerHandoffKind
    status: ManagerHandoffStatus
    source_ref_set: tuple[str, ...]
    authority_notice_ref: str
    payload_ref_set: tuple[str, ...]
    required_route_set: tuple[str, ...]
    fault_ref_set: tuple[str, ...] = ()
    non_authority_notice: str = NO_DISPATCH_NOTICE
    dispatch_authorized: bool = False
    live_effect_performed: bool = False


@dataclass(frozen=True)
class HumanOverrideRecord:
    """Scoped, fresh, revocable human override context."""

    override_id: str
    scope: str
    authority_notice_ref: str
    freshness_state: str
    revocation_route: str
    risk_context_ref: str
    source_ref_set: tuple[str, ...]
    non_authority_notice: str = NO_DISPATCH_NOTICE
    dispatch_authorized: bool = False
    live_effect_performed: bool = False


@dataclass(frozen=True)
class ManagerRefusalRecord:
    """Refusal evidence for unsafe, unsupported, or authority-promoting requests."""

    refusal_id: str
    refusal_reason: ManagerIssueKind
    requested_effect: str
    source_ref_set: tuple[str, ...]
    evidence_ref_set: tuple[str, ...]
    safe_next_route: str
    fault_record_set: tuple[ManagerFaultRecord, ...] = ()
    non_authority_notice: str = NO_LIVE_EFFECT_NOTICE
    dispatch_authorized: bool = False
    live_effect_performed: bool = False


def manager_handoff_record_from_parts(
    *,
    handoff_id: str,
    handoff_kind: str | ManagerHandoffKind,
    status: str | ManagerHandoffStatus,
    source_ref_set: Iterable[str],
    authority_notice_ref: str,
    payload_ref_set: Iterable[str],
    required_route_set: Iterable[str],
    fault_ref_set: Iterable[str] = (),
) -> ManagerHandoffRecord:
    """Build a manager handoff record while preserving no-dispatch semantics."""

    return ManagerHandoffRecord(
        handoff_id=handoff_id,
        handoff_kind=ManagerHandoffKind(handoff_kind),
        status=ManagerHandoffStatus(status),
        source_ref_set=tuple(source_ref_set),
        authority_notice_ref=authority_notice_ref,
        payload_ref_set=tuple(payload_ref_set),
        required_route_set=tuple(required_route_set),
        fault_ref_set=tuple(fault_ref_set),
        dispatch_authorized=False,
        live_effect_performed=False,
    )


def human_override_record_from_parts(
    *,
    override_id: str,
    scope: str,
    authority_notice_ref: str,
    freshness_state: str,
    revocation_route: str,
    risk_context_ref: str,
    source_ref_set: Iterable[str],
) -> HumanOverrideRecord:
    """Build scoped human override context without granting dispatch."""

    return HumanOverrideRecord(
        override_id=override_id,
        scope=scope,
        authority_notice_ref=authority_notice_ref,
        freshness_state=freshness_state,
        revocation_route=revocation_route,
        risk_context_ref=risk_context_ref,
        source_ref_set=tuple(source_ref_set),
        dispatch_authorized=False,
        live_effect_performed=False,
    )


def validate_human_override_record(record: HumanOverrideRecord) -> tuple[ManagerIssue, ...]:
    """Validate that human override context is scoped, fresh, and revocable."""

    issues: list[ManagerIssue] = []
    if not record.scope:
        issues.append(_override_issue("override scope is required", "scope"))
    if record.freshness_state not in {"fresh", "present_fresh_scoped_revocable"}:
        issues.append(_override_issue("override freshness must be fresh", "freshness_state"))
    if not record.revocation_route:
        issues.append(_override_issue("override revocation route is required", "revocation_route"))
    if not record.risk_context_ref:
        issues.append(_override_issue("override risk context is required", "risk_context_ref"))
    if record.dispatch_authorized or record.live_effect_performed:
        issues.append(
            ManagerIssue(
                ManagerIssueKind.REQUESTED_FORBIDDEN_SCOPE,
                ManagerIssueSeverity.REFUSED,
                "human override context cannot authorize dispatch or live effects",
                "dispatch_authorized",
            )
        )
    return tuple(issues)


def manager_refusal_record_from_issue(
    issue: ManagerIssue,
    *,
    refusal_id: str,
    requested_effect: str,
    source_ref_set: Iterable[str],
    evidence_ref_set: Iterable[str],
) -> ManagerRefusalRecord:
    """Project refusal evidence from one manager issue."""

    fault = ManagerFaultRecord(
        fault_id=f"{refusal_id}:{issue.issue_kind.value}",
        fault_kind=_fault_kind_for_refusal(issue),
        severity=_fault_severity_for_refusal(issue),
        work_ref=refusal_id,
        evidence_ref_set=tuple(evidence_ref_set),
        triggering_record_ref_set=(issue.field_name,) if issue.field_name else (),
        safe_next_route=safe_next_route_for_refusal(issue),
    )
    return ManagerRefusalRecord(
        refusal_id=refusal_id,
        refusal_reason=issue.issue_kind,
        requested_effect=requested_effect,
        source_ref_set=tuple(source_ref_set),
        evidence_ref_set=tuple(evidence_ref_set),
        safe_next_route=safe_next_route_for_refusal(issue),
        fault_record_set=(fault,),
        dispatch_authorized=False,
        live_effect_performed=False,
    )


def manager_refusal_records_from_readiness(
    readiness: ManagerReadinessResult,
    *,
    work_ref: str,
    requested_effect: str = "",
    source_ref_set: Iterable[str] = (),
) -> tuple[ManagerRefusalRecord, ...]:
    """Project refusal records for refused or interrupted readiness issues."""

    fault_records = manager_fault_records_from_readiness(
        readiness,
        work_ref=work_ref,
        evidence_ref_set=source_ref_set,
    )
    refusal_issues = tuple(
        issue
        for issue in readiness.issues
        if issue.severity in {ManagerIssueSeverity.REFUSED, ManagerIssueSeverity.INTERRUPT, ManagerIssueSeverity.STALE}
    )
    return tuple(
        ManagerRefusalRecord(
            refusal_id=f"{work_ref}:{issue.issue_kind.value}:refusal",
            refusal_reason=issue.issue_kind,
            requested_effect=requested_effect,
            source_ref_set=tuple(source_ref_set),
            evidence_ref_set=tuple(source_ref_set) or (issue.issue_kind.value,),
            safe_next_route=safe_next_route_for_refusal(issue),
            fault_record_set=tuple(
                fault for fault in fault_records if fault.fault_kind.value == issue.issue_kind.value
            ),
            dispatch_authorized=False,
            live_effect_performed=False,
        )
        for issue in refusal_issues
    )


def handoff_record_from_readiness(
    readiness: ManagerReadinessResult,
    *,
    handoff_id: str,
    handoff_kind: str | ManagerHandoffKind,
    source_ref_set: Iterable[str],
    authority_notice_ref: str,
    payload_ref_set: Iterable[str],
) -> ManagerHandoffRecord:
    """Build a review handoff from readiness without dispatching anything."""

    if readiness.has_refusal:
        status = ManagerHandoffStatus.REFUSED
    elif readiness.has_interrupt:
        status = ManagerHandoffStatus.INTERRUPTED
    elif readiness.has_blocker or readiness.has_fault:
        status = ManagerHandoffStatus.BLOCKED
    elif readiness.accepted:
        status = ManagerHandoffStatus.READY_FOR_REVIEW
    else:
        status = ManagerHandoffStatus.CONTEXT_ONLY
    return manager_handoff_record_from_parts(
        handoff_id=handoff_id,
        handoff_kind=handoff_kind,
        status=status,
        source_ref_set=source_ref_set,
        authority_notice_ref=authority_notice_ref,
        payload_ref_set=payload_ref_set,
        required_route_set=("completion_review",),
        fault_ref_set=tuple(issue.issue_kind.value for issue in readiness.issues),
    )


def validate_manager_handoff_record(record: ManagerHandoffRecord) -> tuple[ManagerIssue, ...]:
    """Validate no-dispatch and required-route shape for a handoff."""

    issues: list[ManagerIssue] = []
    if not record.handoff_id:
        issues.append(_missing_field_issue("handoff_id"))
    if not record.authority_notice_ref:
        issues.append(_missing_field_issue("authority_notice_ref"))
    if not record.required_route_set:
        issues.append(_missing_field_issue("required_route_set"))
    if record.dispatch_authorized or record.live_effect_performed:
        issues.append(
            ManagerIssue(
                ManagerIssueKind.DISPATCH_REQUESTED,
                ManagerIssueSeverity.REFUSED,
                "handoff records cannot authorize dispatch or live effects",
                "dispatch_authorized",
            )
        )
    return tuple(issues)


def safe_next_route_for_refusal(issue: ManagerIssue) -> str:
    """Return the safe route for a refusal or interrupt issue."""

    if issue.issue_kind in {
        ManagerIssueKind.REQUESTED_FORBIDDEN_SCOPE,
        ManagerIssueKind.DRY_RUN_TO_LIVE_CONTROL_PROMOTION,
        ManagerIssueKind.GENERATED_OUTPUT_AUTHORITY_PROMOTION,
        ManagerIssueKind.GRAPH_CHECKPOINT_AUTHORITY_PROMOTION,
    }:
        return "refuse_and_require_separate_authority"
    if issue.issue_kind == ManagerIssueKind.MODEL_ROUTE_AMBIGUITY:
        return "declare_model_route"
    if issue.issue_kind == ManagerIssueKind.STALE_BOUNDARY_INPUT:
        return "rebake_or_refresh_authority"
    return "SOP_first_review"


def _missing_field_issue(field_name: str) -> ManagerIssue:
    return ManagerIssue(
        ManagerIssueKind.MISSING_FIELD,
        ManagerIssueSeverity.FAULT,
        f"{field_name} is required",
        field_name,
    )


def _override_issue(reason: str, field_name: str) -> ManagerIssue:
    return ManagerIssue(
        ManagerIssueKind.HUMAN_OVERRIDE_REQUIRED,
        ManagerIssueSeverity.BLOCKED,
        reason,
        field_name,
    )


def _fault_kind_for_refusal(issue: ManagerIssue):  # type: ignore[no-untyped-def]
    from .faults import fault_kind_for_issue_kind

    return fault_kind_for_issue_kind(issue.issue_kind)


def _fault_severity_for_refusal(issue: ManagerIssue):  # type: ignore[no-untyped-def]
    from .faults import ManagerFaultSeverity

    return ManagerFaultSeverity(issue.severity.value)
