"""Dry-run result models for IR7 operation planning.

Dry-run results are planning evidence only. This module never performs live
effects and never promotes dry-run success into dispatch or live-control
authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Mapping

from .requests import (
    OperationAuthorityTier,
    OperationRequestEnvelope,
    OperationRequestValidationResult,
)


NON_AUTHORITY_NOTICE = "dry_run_result_is_planning_evidence_not_live_approval"


class DryRunResultIssueKind(str, Enum):
    """Issue vocabulary for dry-run result validation."""

    MISSING_FIELD = "missing_field"
    LIVE_EFFECT_PERFORMED = "live_effect_performed"
    MISSING_NON_AUTHORITY_NOTICE = "missing_non_authority_notice"
    MISSING_COMPLETION_REVIEW = "missing_completion_review"
    AUTHORITY_PROMOTION = "authority_promotion"


class DryRunResultIssueSeverity(str, Enum):
    """How a dry-run result issue should be treated."""

    FAULT = "fault"
    REFUSED = "refused"
    BLOCKED = "blocked"


class DryRunResultStatus(str, Enum):
    """Projected dry-run result status."""

    ACCEPTED = "accepted"
    BLOCKED = "blocked"
    FAULTED = "faulted"
    REFUSED = "refused"
    REVIEW_REQUIRED = "review_required"


REQUIRED_DRY_RUN_RESULT_FIELD_SET: tuple[str, ...] = (
    "dry_run_result_id",
    "dry_run_result_uuid",
    "operation_request_ref",
    "source_ref_set",
    "authority_notice_ref",
    "simulated_effect_summary",
    "resource_target_ref",
    "risk_classification",
    "estimated_resource_use",
    "predicted_side_effect_set",
    "refused_effect_set",
    "required_human_approval",
    "rollback_or_abort_route",
    "live_effect_performed",
    "generated_output_ref",
    "completion_review_required",
    "non_authority_notice",
    "stale_after",
)

FORBIDDEN_RESULT_AUTHORITY_TIER_SET: frozenset[OperationAuthorityTier] = frozenset(
    {
        OperationAuthorityTier.SOURCE_AUTHORITY,
        OperationAuthorityTier.LIVE_CONTROL_AUTHORITY,
        OperationAuthorityTier.DISPATCH_AUTHORITY,
        OperationAuthorityTier.CREDENTIAL_AUTHORITY,
        OperationAuthorityTier.NETWORK_AUTHORITY,
        OperationAuthorityTier.DESTRUCTIVE_FILESYSTEM_AUTHORITY,
    }
)


@dataclass(frozen=True)
class DryRunResultIssue:
    """One dry-run result fault, refusal, or blocker."""

    issue_kind: DryRunResultIssueKind
    severity: DryRunResultIssueSeverity
    reason: str
    field_name: str | None = None


@dataclass(frozen=True)
class DryRunResultValidation:
    """Pure validation result for a dry-run result record."""

    accepted: bool
    status: DryRunResultStatus
    issues: tuple[DryRunResultIssue, ...] = ()

    @property
    def has_refusal(self) -> bool:
        return any(issue.severity == DryRunResultIssueSeverity.REFUSED for issue in self.issues)

    @property
    def has_fault(self) -> bool:
        return any(issue.severity == DryRunResultIssueSeverity.FAULT for issue in self.issues)


@dataclass(frozen=True)
class DryRunResultRecord:
    """Planning-only result for a simulated operation request."""

    dry_run_result_id: str
    dry_run_result_uuid: str
    operation_request_ref: str
    source_ref_set: tuple[str, ...]
    authority_notice_ref: str
    simulated_effect_summary: str
    resource_target_ref: str
    risk_classification: str
    estimated_resource_use: str
    predicted_side_effect_set: tuple[str, ...]
    refused_effect_set: tuple[str, ...]
    required_human_approval: bool
    rollback_or_abort_route: str
    live_effect_performed: bool
    generated_output_ref: str
    completion_review_required: bool
    non_authority_notice: str
    stale_after: str
    authority_tier: OperationAuthorityTier = OperationAuthorityTier.OPERATIONS_PLANNING_RECORD
    review_status: DryRunResultStatus = DryRunResultStatus.ACCEPTED
    authority_promotion_claimed: bool = False

    @property
    def is_non_authoritative(self) -> bool:
        return (
            not self.live_effect_performed
            and self.completion_review_required
            and self.non_authority_notice == NON_AUTHORITY_NOTICE
            and self.authority_tier == OperationAuthorityTier.OPERATIONS_PLANNING_RECORD
        )


def dry_run_result_record_from_parts(
    *,
    dry_run_result_id: str,
    dry_run_result_uuid: str,
    operation_request_ref: str,
    source_ref_set: Iterable[str],
    authority_notice_ref: str,
    simulated_effect_summary: str,
    resource_target_ref: str,
    risk_classification: str,
    estimated_resource_use: str,
    predicted_side_effect_set: Iterable[str],
    refused_effect_set: Iterable[str],
    required_human_approval: bool,
    rollback_or_abort_route: str,
    stale_after: str,
    live_effect_performed: bool = False,
    generated_output_ref: str = "",
    completion_review_required: bool = True,
    non_authority_notice: str = NON_AUTHORITY_NOTICE,
    authority_tier: str | OperationAuthorityTier = OperationAuthorityTier.OPERATIONS_PLANNING_RECORD,
    review_status: str | DryRunResultStatus = DryRunResultStatus.ACCEPTED,
    authority_promotion_claimed: bool = False,
) -> DryRunResultRecord:
    """Build a dry-run result record while normalizing sets and enums."""

    return DryRunResultRecord(
        dry_run_result_id=dry_run_result_id,
        dry_run_result_uuid=dry_run_result_uuid,
        operation_request_ref=operation_request_ref,
        source_ref_set=tuple(source_ref_set),
        authority_notice_ref=authority_notice_ref,
        simulated_effect_summary=simulated_effect_summary,
        resource_target_ref=resource_target_ref,
        risk_classification=risk_classification,
        estimated_resource_use=estimated_resource_use,
        predicted_side_effect_set=tuple(predicted_side_effect_set),
        refused_effect_set=tuple(refused_effect_set),
        required_human_approval=required_human_approval,
        rollback_or_abort_route=rollback_or_abort_route,
        live_effect_performed=live_effect_performed,
        generated_output_ref=generated_output_ref,
        completion_review_required=completion_review_required,
        non_authority_notice=non_authority_notice,
        stale_after=stale_after,
        authority_tier=OperationAuthorityTier(authority_tier),
        review_status=DryRunResultStatus(review_status),
        authority_promotion_claimed=authority_promotion_claimed,
    )


def dry_run_result_record_from_mapping(data: Mapping[str, object]) -> DryRunResultRecord:
    """Build a dry-run result record from mapping data."""

    return dry_run_result_record_from_parts(
        dry_run_result_id=str(data.get("dry_run_result_id", "")),
        dry_run_result_uuid=str(data.get("dry_run_result_uuid", "")),
        operation_request_ref=str(data.get("operation_request_ref", "")),
        source_ref_set=_as_string_sequence(data.get("source_ref_set", ())),
        authority_notice_ref=str(data.get("authority_notice_ref", "")),
        simulated_effect_summary=str(data.get("simulated_effect_summary", "")),
        resource_target_ref=str(data.get("resource_target_ref", "")),
        risk_classification=str(data.get("risk_classification", "")),
        estimated_resource_use=str(data.get("estimated_resource_use", "")),
        predicted_side_effect_set=_as_string_sequence(data.get("predicted_side_effect_set", ())),
        refused_effect_set=_as_string_sequence(data.get("refused_effect_set", ())),
        required_human_approval=_as_bool(data.get("required_human_approval", False)),
        rollback_or_abort_route=str(data.get("rollback_or_abort_route", "")),
        live_effect_performed=_as_bool(data.get("live_effect_performed", False)),
        generated_output_ref=str(data.get("generated_output_ref", "")),
        completion_review_required=_as_bool(data.get("completion_review_required", True)),
        non_authority_notice=str(data.get("non_authority_notice", "")),
        stale_after=str(data.get("stale_after", "")),
        authority_tier=str(data.get("authority_tier", OperationAuthorityTier.OPERATIONS_PLANNING_RECORD.value)),
        review_status=str(data.get("review_status", DryRunResultStatus.ACCEPTED.value)),
        authority_promotion_claimed=_as_bool(data.get("authority_promotion_claimed", False)),
    )


def dry_run_result_from_operation_request(
    envelope: OperationRequestEnvelope,
    validation: OperationRequestValidationResult | None = None,
    *,
    simulated_effect_summary: str = "dry-run projection only",
    estimated_resource_use: str = "not_estimated",
    generated_output_ref: str = "",
) -> DryRunResultRecord:
    """Project a dry-run result record from a request without live effects."""

    refused_effect_set = ()
    status = DryRunResultStatus.ACCEPTED
    if validation is not None and not validation.accepted:
        refused_effect_set = tuple(sorted({issue.issue_kind.value for issue in validation.issues}))
        status = _result_status_for_request_validation(validation)

    return dry_run_result_record_from_parts(
        dry_run_result_id=f"{envelope.operation_request_id}:dry-run",
        dry_run_result_uuid=f"{envelope.operation_request_uuid}:dry-run",
        operation_request_ref=envelope.operation_request_id,
        source_ref_set=envelope.source_ref_set,
        authority_notice_ref=envelope.authority_notice_ref,
        simulated_effect_summary=simulated_effect_summary,
        resource_target_ref=envelope.resource_target,
        risk_classification=envelope.risk_classification,
        estimated_resource_use=estimated_resource_use,
        predicted_side_effect_set=envelope.predicted_side_effect_set,
        refused_effect_set=refused_effect_set,
        required_human_approval=_requires_human_approval(envelope, validation),
        rollback_or_abort_route=envelope.rollback_or_abort_route,
        live_effect_performed=False,
        generated_output_ref=generated_output_ref,
        completion_review_required=True,
        non_authority_notice=NON_AUTHORITY_NOTICE,
        stale_after=envelope.stale_after,
        review_status=status,
    )


def validate_dry_run_result_record(record: DryRunResultRecord) -> DryRunResultValidation:
    """Validate dry-run result non-authority and no-live-effect constraints."""

    issues: list[DryRunResultIssue] = []
    for field_name in REQUIRED_DRY_RUN_RESULT_FIELD_SET:
        if field_name == "generated_output_ref":
            continue
        if not _field_has_value(record, field_name):
            issues.append(
                DryRunResultIssue(
                    DryRunResultIssueKind.MISSING_FIELD,
                    DryRunResultIssueSeverity.FAULT,
                    f"{field_name} is required",
                    field_name,
                )
            )

    if record.live_effect_performed:
        issues.append(
            DryRunResultIssue(
                DryRunResultIssueKind.LIVE_EFFECT_PERFORMED,
                DryRunResultIssueSeverity.REFUSED,
                "dry-run results must never report a live effect",
                "live_effect_performed",
            )
        )

    if not record.completion_review_required:
        issues.append(
            DryRunResultIssue(
                DryRunResultIssueKind.MISSING_COMPLETION_REVIEW,
                DryRunResultIssueSeverity.BLOCKED,
                "completion review is required before dry-run records can support planning",
                "completion_review_required",
            )
        )

    if record.non_authority_notice != NON_AUTHORITY_NOTICE:
        issues.append(
            DryRunResultIssue(
                DryRunResultIssueKind.MISSING_NON_AUTHORITY_NOTICE,
                DryRunResultIssueSeverity.FAULT,
                "dry-run result must carry the accepted non-authority notice",
                "non_authority_notice",
            )
        )

    if record.authority_tier in FORBIDDEN_RESULT_AUTHORITY_TIER_SET or record.authority_promotion_claimed:
        issues.append(
            DryRunResultIssue(
                DryRunResultIssueKind.AUTHORITY_PROMOTION,
                DryRunResultIssueSeverity.REFUSED,
                "dry-run result may not claim source, dispatch, credential, network, destructive, or live-control authority",
                "authority_tier",
            )
        )

    status = _validation_status_for_issues(issues, record.review_status)
    return DryRunResultValidation(status == DryRunResultStatus.ACCEPTED, status, tuple(issues))


def _result_status_for_request_validation(validation: OperationRequestValidationResult) -> DryRunResultStatus:
    if validation.has_fault:
        return DryRunResultStatus.FAULTED
    if validation.has_refusal:
        return DryRunResultStatus.REFUSED
    if validation.requires_review:
        return DryRunResultStatus.REVIEW_REQUIRED
    return DryRunResultStatus.BLOCKED


def _validation_status_for_issues(
    issues: Iterable[DryRunResultIssue],
    current_status: DryRunResultStatus,
) -> DryRunResultStatus:
    issue_tuple = tuple(issues)
    if any(issue.severity == DryRunResultIssueSeverity.FAULT for issue in issue_tuple):
        return DryRunResultStatus.FAULTED
    if any(issue.severity == DryRunResultIssueSeverity.REFUSED for issue in issue_tuple):
        return DryRunResultStatus.REFUSED
    if any(issue.severity == DryRunResultIssueSeverity.BLOCKED for issue in issue_tuple):
        return DryRunResultStatus.BLOCKED
    return current_status


def _requires_human_approval(
    envelope: OperationRequestEnvelope,
    validation: OperationRequestValidationResult | None,
) -> bool:
    if validation is not None and validation.requires_review:
        return True
    return envelope.risk_classification in {"critical", "high"} or envelope.blast_radius in {
        "uncertain",
        "wide",
        "critical",
        "unknown",
    }


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
