"""Refusal and SOP-first interrupt models for IR7 operation planning."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Mapping

from .requests import (
    OperationRequestEnvelope,
    OperationRequestIssueKind,
    OperationRequestIssueSeverity,
    OperationRequestValidationIssue,
    OperationRequestValidationResult,
)


REFUSAL_NON_AUTHORITY_NOTICE = "refusal_record_is_evidence_not_command"
INTERRUPT_NON_AUTHORITY_NOTICE = "sop_first_interrupt_context_is_review_evidence_not_live_authority"


class OperationRefusalReason(str, Enum):
    """Accepted refusal reasons from the IR7 refusal contract."""

    MISSING_REQUIRED_IDENTITY_FIELD = "missing_required_identity_field"
    MISSING_REQUIRED_SAFETY_FIELD = "missing_required_safety_field"
    STALE_AUTHORITY_NOTICE = "stale_authority_notice"
    STALE_BOUNDARY_INPUT = "stale_boundary_input"
    AMBIGUOUS_RESOURCE_TARGET = "ambiguous_resource_target"
    LIVE_EFFECT_REQUESTED = "live_effect_requested"
    HIGH_RISK_TARGET_WITHOUT_IR7_S03_REVIEW = "high_risk_target_without_IR7-S03_review"
    MISSING_ROLLBACK_OR_ABORT_ROUTE = "missing_rollback_or_abort_route"
    CREDENTIAL_BOUNDARY_TOUCHED = "credential_boundary_touched"
    NETWORK_EXPOSURE_REQUESTED = "network_exposure_requested"
    DESTRUCTIVE_ACTION_POSSIBLE = "destructive_action_possible"
    COORDINATION_CLAIM_PROMOTED_TO_DISPATCH = "coordination_claim_promoted_to_dispatch"
    MAILBOX_CARRIER_PROMOTED_TO_DISPATCH = "mailbox_carrier_promoted_to_dispatch"
    GENERATED_PROJECTION_PROMOTED_TO_AUTHORITY = "generated_projection_promoted_to_authority"


class OperationRefusalOutput(str, Enum):
    """Stable refusal output vocabulary."""

    REFUSED_OPERATION_REQUEST = "refused_operation_request"
    BLOCKED_OPERATION_REQUEST = "blocked_operation_request"
    REFUSED_LIVE_CONTROL = "refused_live_control"
    REFUSED_GPU_CONTROL = "refused_gpu_control"
    REFUSED_MODEL_RUNTIME_CONTROL = "refused_model_runtime_control"
    REFUSED_JOB_CONTROL = "refused_job_control"
    REFUSED_CREDENTIAL_CONTROL = "refused_credential_control"
    REFUSED_NETWORK_CONTROL = "refused_network_control"
    REFUSED_DESTRUCTIVE_FILESYSTEM_CONTROL = "refused_destructive_filesystem_control"
    REQUIRED_RESOURCE_SAFETY_REVIEW = "required_resource_safety_review"
    REQUIRED_HUMAN_REVIEW = "required_human_review"
    SOP_FIRST_INTERRUPT_CONTEXT = "sop_first_interrupt_context"


class OperationRefusalValidationIssueKind(str, Enum):
    """Issue vocabulary for refusal record validation."""

    MISSING_FIELD = "missing_field"
    MISSING_NON_AUTHORITY_NOTICE = "missing_non_authority_notice"
    COMMAND_OR_LIVE_EFFECT_CLAIMED = "command_or_live_effect_claimed"


class OperationRefusalValidationSeverity(str, Enum):
    """How a refusal validation issue should be treated."""

    FAULT = "fault"
    REFUSED = "refused"


REQUIRED_REFUSAL_RECORD_FIELD_SET: tuple[str, ...] = (
    "refusal_id",
    "operation_request_ref",
    "requested_effect",
    "resource_target",
    "actor_ref",
    "carrier_surface",
    "authority_notice_ref",
    "refusal_reason",
    "refused_effect_set",
    "safe_next_route",
    "evidence_ref_set",
    "non_authority_notice",
)


@dataclass(frozen=True)
class OperationRefusalRecord:
    """Refusal evidence for an unsafe or under-supported operation request."""

    refusal_id: str
    operation_request_ref: str
    requested_effect: str
    resource_target: str
    actor_ref: str
    carrier_surface: str
    authority_notice_ref: str
    refusal_reason: OperationRefusalReason
    refused_effect_set: tuple[str, ...]
    safe_next_route: str
    evidence_ref_set: tuple[str, ...]
    non_authority_notice: str = REFUSAL_NON_AUTHORITY_NOTICE
    refusal_output_set: tuple[OperationRefusalOutput, ...] = ()
    live_effect_performed: bool = False
    command_generated: bool = False


@dataclass(frozen=True)
class SOPFirstInterruptContext:
    """Review context for ambiguous, stale, contradicted, or future-live requests."""

    interrupt_id: str
    operation_request_ref: str
    interrupt_reason: OperationRefusalReason
    evidence_ref_set: tuple[str, ...]
    required_route_set: tuple[str, ...]
    non_authority_notice: str = INTERRUPT_NON_AUTHORITY_NOTICE


@dataclass(frozen=True)
class OperationRefusalValidationIssue:
    """One refusal record validation issue."""

    issue_kind: OperationRefusalValidationIssueKind
    severity: OperationRefusalValidationSeverity
    reason: str
    field_name: str | None = None


@dataclass(frozen=True)
class OperationRefusalValidation:
    """Pure validation result for refusal and interrupt records."""

    accepted: bool
    issues: tuple[OperationRefusalValidationIssue, ...] = ()


def operation_refusal_record_from_parts(
    *,
    refusal_id: str,
    operation_request_ref: str,
    requested_effect: str,
    resource_target: str,
    actor_ref: str,
    carrier_surface: str,
    authority_notice_ref: str,
    refusal_reason: str | OperationRefusalReason,
    refused_effect_set: Iterable[str],
    safe_next_route: str,
    evidence_ref_set: Iterable[str],
    non_authority_notice: str = REFUSAL_NON_AUTHORITY_NOTICE,
    refusal_output_set: Iterable[str | OperationRefusalOutput] = (),
    live_effect_performed: bool = False,
    command_generated: bool = False,
) -> OperationRefusalRecord:
    """Build a refusal record while normalizing sets and enums."""

    return OperationRefusalRecord(
        refusal_id=refusal_id,
        operation_request_ref=operation_request_ref,
        requested_effect=requested_effect,
        resource_target=resource_target,
        actor_ref=actor_ref,
        carrier_surface=carrier_surface,
        authority_notice_ref=authority_notice_ref,
        refusal_reason=OperationRefusalReason(refusal_reason),
        refused_effect_set=tuple(refused_effect_set),
        safe_next_route=safe_next_route,
        evidence_ref_set=tuple(evidence_ref_set),
        non_authority_notice=non_authority_notice,
        refusal_output_set=tuple(OperationRefusalOutput(item) for item in refusal_output_set),
        live_effect_performed=live_effect_performed,
        command_generated=command_generated,
    )


def operation_refusal_record_from_mapping(data: Mapping[str, object]) -> OperationRefusalRecord:
    """Build a refusal record from mapping data."""

    return operation_refusal_record_from_parts(
        refusal_id=str(data.get("refusal_id", "")),
        operation_request_ref=str(data.get("operation_request_ref", "")),
        requested_effect=str(data.get("requested_effect", "")),
        resource_target=str(data.get("resource_target", "")),
        actor_ref=str(data.get("actor_ref", "")),
        carrier_surface=str(data.get("carrier_surface", "")),
        authority_notice_ref=str(data.get("authority_notice_ref", "")),
        refusal_reason=str(data.get("refusal_reason", OperationRefusalReason.LIVE_EFFECT_REQUESTED.value)),
        refused_effect_set=_as_string_sequence(data.get("refused_effect_set", ())),
        safe_next_route=str(data.get("safe_next_route", "")),
        evidence_ref_set=_as_string_sequence(data.get("evidence_ref_set", ())),
        non_authority_notice=str(data.get("non_authority_notice", REFUSAL_NON_AUTHORITY_NOTICE)),
        refusal_output_set=_as_string_sequence(data.get("refusal_output_set", ())),
        live_effect_performed=_as_bool(data.get("live_effect_performed", False)),
        command_generated=_as_bool(data.get("command_generated", False)),
    )


def refusal_record_from_request_validation(
    envelope: OperationRequestEnvelope,
    validation: OperationRequestValidationResult,
    *,
    refusal_id: str | None = None,
) -> OperationRefusalRecord:
    """Project a refusal record from validation issues without making commands."""

    primary_issue = _primary_issue(validation.issues)
    reason = refusal_reason_for_issue(primary_issue)
    output_set = refusal_output_set_for_request(envelope, reason, validation)
    return operation_refusal_record_from_parts(
        refusal_id=refusal_id or f"{envelope.operation_request_id}:refusal",
        operation_request_ref=envelope.operation_request_id,
        requested_effect=envelope.intended_effect,
        resource_target=envelope.resource_target,
        actor_ref=envelope.requested_by,
        carrier_surface=envelope.carrier_surface,
        authority_notice_ref=envelope.authority_notice_ref,
        refusal_reason=reason,
        refused_effect_set=tuple(output.value for output in output_set),
        safe_next_route=safe_next_route_for_reason(reason),
        evidence_ref_set=evidence_ref_set_for_validation(envelope, validation),
        refusal_output_set=output_set,
    )


def sop_first_interrupt_context_from_refusal(
    refusal: OperationRefusalRecord,
    *,
    required_route_set: Iterable[str] = (),
) -> SOPFirstInterruptContext:
    """Create a SOP-first interrupt context from refusal evidence."""

    route_set = tuple(required_route_set) or (refusal.safe_next_route,)
    return SOPFirstInterruptContext(
        interrupt_id=f"{refusal.refusal_id}:interrupt",
        operation_request_ref=refusal.operation_request_ref,
        interrupt_reason=refusal.refusal_reason,
        evidence_ref_set=refusal.evidence_ref_set,
        required_route_set=route_set,
    )


def validate_operation_refusal_record(record: OperationRefusalRecord) -> OperationRefusalValidation:
    """Validate refusal record non-authority and no-live-effect constraints."""

    issues: list[OperationRefusalValidationIssue] = []
    for field_name in REQUIRED_REFUSAL_RECORD_FIELD_SET:
        if not _field_has_value(record, field_name):
            issues.append(
                OperationRefusalValidationIssue(
                    OperationRefusalValidationIssueKind.MISSING_FIELD,
                    OperationRefusalValidationSeverity.FAULT,
                    f"{field_name} is required",
                    field_name,
                )
            )

    if record.non_authority_notice != REFUSAL_NON_AUTHORITY_NOTICE:
        issues.append(
            OperationRefusalValidationIssue(
                OperationRefusalValidationIssueKind.MISSING_NON_AUTHORITY_NOTICE,
                OperationRefusalValidationSeverity.FAULT,
                "refusal record must carry the accepted non-authority notice",
                "non_authority_notice",
            )
        )

    if record.live_effect_performed or record.command_generated:
        issues.append(
            OperationRefusalValidationIssue(
                OperationRefusalValidationIssueKind.COMMAND_OR_LIVE_EFFECT_CLAIMED,
                OperationRefusalValidationSeverity.REFUSED,
                "refusal records must remain records and cannot become commands",
                "live_effect_performed",
            )
        )

    return OperationRefusalValidation(not issues, tuple(issues))


def refusal_reason_for_issue(issue: OperationRequestValidationIssue | None) -> OperationRefusalReason:
    """Map request validation issue vocabulary to accepted refusal reasons."""

    if issue is None:
        return OperationRefusalReason.LIVE_EFFECT_REQUESTED

    mapping: dict[OperationRequestIssueKind, OperationRefusalReason] = {
        OperationRequestIssueKind.MISSING_FIELD: OperationRefusalReason.MISSING_REQUIRED_IDENTITY_FIELD,
        OperationRequestIssueKind.MISSING_AUTHORITY_NOTICE: OperationRefusalReason.MISSING_REQUIRED_IDENTITY_FIELD,
        OperationRequestIssueKind.STALE_AUTHORITY_NOTICE: OperationRefusalReason.STALE_AUTHORITY_NOTICE,
        OperationRequestIssueKind.MISSING_SOURCE_REF: OperationRefusalReason.MISSING_REQUIRED_IDENTITY_FIELD,
        OperationRequestIssueKind.MISSING_COMPLETION_REVIEW: OperationRefusalReason.MISSING_REQUIRED_IDENTITY_FIELD,
        OperationRequestIssueKind.MISSING_SAFETY_FIELD: OperationRefusalReason.MISSING_REQUIRED_SAFETY_FIELD,
        OperationRequestIssueKind.AMBIGUOUS_RESOURCE_TARGET: OperationRefusalReason.AMBIGUOUS_RESOURCE_TARGET,
        OperationRequestIssueKind.LIVE_EFFECT_REQUESTED: OperationRefusalReason.LIVE_EFFECT_REQUESTED,
        OperationRequestIssueKind.HIGH_RISK_REVIEW_REQUIRED: OperationRefusalReason.HIGH_RISK_TARGET_WITHOUT_IR7_S03_REVIEW,
        OperationRequestIssueKind.MISSING_ROLLBACK_OR_ABORT_ROUTE: OperationRefusalReason.MISSING_ROLLBACK_OR_ABORT_ROUTE,
        OperationRequestIssueKind.CREDENTIAL_BOUNDARY_TOUCHED: OperationRefusalReason.CREDENTIAL_BOUNDARY_TOUCHED,
        OperationRequestIssueKind.NETWORK_EXPOSURE_REQUESTED: OperationRefusalReason.NETWORK_EXPOSURE_REQUESTED,
        OperationRequestIssueKind.DESTRUCTIVE_ACTION_POSSIBLE: OperationRefusalReason.DESTRUCTIVE_ACTION_POSSIBLE,
        OperationRequestIssueKind.COORDINATION_CLAIM_PROMOTED_TO_DISPATCH: OperationRefusalReason.COORDINATION_CLAIM_PROMOTED_TO_DISPATCH,
        OperationRequestIssueKind.MAILBOX_CARRIER_PROMOTED_TO_DISPATCH: OperationRefusalReason.MAILBOX_CARRIER_PROMOTED_TO_DISPATCH,
        OperationRequestIssueKind.GENERATED_PROJECTION_PROMOTED_TO_AUTHORITY: OperationRefusalReason.GENERATED_PROJECTION_PROMOTED_TO_AUTHORITY,
        OperationRequestIssueKind.FORBIDDEN_AUTHORITY_TIER: OperationRefusalReason.GENERATED_PROJECTION_PROMOTED_TO_AUTHORITY,
        OperationRequestIssueKind.DRY_RUN_NOT_REQUIRED: OperationRefusalReason.LIVE_EFFECT_REQUESTED,
    }
    return mapping[issue.issue_kind]


def refusal_output_set_for_request(
    envelope: OperationRequestEnvelope,
    reason: OperationRefusalReason,
    validation: OperationRequestValidationResult,
) -> tuple[OperationRefusalOutput, ...]:
    """Classify refusal outputs for a request and reason."""

    outputs: set[OperationRefusalOutput] = {
        OperationRefusalOutput.REFUSED_OPERATION_REQUEST,
        OperationRefusalOutput.SOP_FIRST_INTERRUPT_CONTEXT,
    }

    if validation.requires_review:
        outputs.add(OperationRefusalOutput.REQUIRED_RESOURCE_SAFETY_REVIEW)
        outputs.add(OperationRefusalOutput.REQUIRED_HUMAN_REVIEW)

    if reason in {
        OperationRefusalReason.MISSING_REQUIRED_IDENTITY_FIELD,
        OperationRefusalReason.MISSING_REQUIRED_SAFETY_FIELD,
        OperationRefusalReason.STALE_AUTHORITY_NOTICE,
        OperationRefusalReason.AMBIGUOUS_RESOURCE_TARGET,
        OperationRefusalReason.MISSING_ROLLBACK_OR_ABORT_ROUTE,
    }:
        outputs.add(OperationRefusalOutput.BLOCKED_OPERATION_REQUEST)

    effect = envelope.intended_effect
    target = envelope.resource_target
    if target == "gpu" or effect.startswith("gpu_"):
        outputs.add(OperationRefusalOutput.REFUSED_GPU_CONTROL)
    elif target == "model_runtime" or effect.startswith("model_runtime_"):
        outputs.add(OperationRefusalOutput.REFUSED_MODEL_RUNTIME_CONTROL)
    elif target == "job_queue" or effect in {"job_dispatch", "job_cancellation", "job_dispatch_or_cancellation"}:
        outputs.add(OperationRefusalOutput.REFUSED_JOB_CONTROL)
    elif target == "credential_or_secret" or effect == "credential_access_or_mutation":
        outputs.add(OperationRefusalOutput.REFUSED_CREDENTIAL_CONTROL)
    elif target == "network_service" or effect == "network_exposure_mutation":
        outputs.add(OperationRefusalOutput.REFUSED_NETWORK_CONTROL)
    elif target == "filesystem_destructive_target" or effect == "destructive_filesystem_action":
        outputs.add(OperationRefusalOutput.REFUSED_DESTRUCTIVE_FILESYSTEM_CONTROL)
    elif reason in {
        OperationRefusalReason.LIVE_EFFECT_REQUESTED,
        OperationRefusalReason.GENERATED_PROJECTION_PROMOTED_TO_AUTHORITY,
    }:
        outputs.add(OperationRefusalOutput.REFUSED_LIVE_CONTROL)

    return tuple(sorted(outputs, key=lambda item: item.value))


def safe_next_route_for_reason(reason: OperationRefusalReason) -> str:
    """Return the safe route that preserves SOP-first review."""

    if reason in {
        OperationRefusalReason.HIGH_RISK_TARGET_WITHOUT_IR7_S03_REVIEW,
        OperationRefusalReason.CREDENTIAL_BOUNDARY_TOUCHED,
        OperationRefusalReason.NETWORK_EXPOSURE_REQUESTED,
        OperationRefusalReason.DESTRUCTIVE_ACTION_POSSIBLE,
    }:
        return "IR7-S03_resource_safety_review"
    if reason in {
        OperationRefusalReason.MISSING_REQUIRED_IDENTITY_FIELD,
        OperationRefusalReason.MISSING_REQUIRED_SAFETY_FIELD,
        OperationRefusalReason.MISSING_ROLLBACK_OR_ABORT_ROUTE,
    }:
        return "repair_operation_request"
    if reason == OperationRefusalReason.STALE_AUTHORITY_NOTICE:
        return "refresh_authority_notice_or_rebake"
    return "SOP_first_interrupt_and_completion_review"


def evidence_ref_set_for_validation(
    envelope: OperationRequestEnvelope,
    validation: OperationRequestValidationResult,
) -> tuple[str, ...]:
    """Collect stable evidence refs for refusal review."""

    refs = set(envelope.source_ref_set)
    refs.add(envelope.operation_request_id)
    refs.update(issue.issue_kind.value for issue in validation.issues)
    return tuple(sorted(refs))


def _primary_issue(
    issues: Iterable[OperationRequestValidationIssue],
) -> OperationRequestValidationIssue | None:
    priority = {
        OperationRequestIssueSeverity.FAULT: 0,
        OperationRequestIssueSeverity.REFUSED: 1,
        OperationRequestIssueSeverity.INTERRUPT: 2,
        OperationRequestIssueSeverity.STALE: 3,
        OperationRequestIssueSeverity.REVIEW_REQUIRED: 4,
        OperationRequestIssueSeverity.BLOCKED: 5,
    }
    issue_tuple = tuple(issues)
    if not issue_tuple:
        return None
    return sorted(issue_tuple, key=lambda item: priority[item.severity])[0]


def _field_has_value(record: object, field_name: str) -> bool:
    value = getattr(record, field_name)
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value)
    if isinstance(value, tuple):
        return True
    return True


def _as_string_sequence(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,) if value else ()
    return tuple(str(item) for item in value)  # type: ignore[operator]


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes"}
    return bool(value)
