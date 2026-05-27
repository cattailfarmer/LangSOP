"""Operation request identity, safety, and classification models for IR7.

These helpers produce planning records only. They do not execute commands,
control processes, touch GPU state, mutate model runtimes, dispatch jobs,
access credentials, change network exposure, or authorize live operations.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Mapping


class OperationFreshnessState(str, Enum):
    """Accepted freshness states for operation request projection records."""

    FRESH = "fresh"
    PENDING_REVIEW = "pending_review"
    STALE = "stale"
    UNKNOWN = "unknown"
    INTERRUPTED = "interrupted"
    FAULTED = "faulted"


class OperationAuthorityTier(str, Enum):
    """Authority tier vocabulary for operation-shaped planning records."""

    OPERATIONS_PLANNING_RECORD = "operations_planning_record"
    SOURCE_AUTHORITY = "source_authority"
    LIVE_CONTROL_AUTHORITY = "live_control_authority"
    DISPATCH_AUTHORITY = "dispatch_authority"
    CREDENTIAL_AUTHORITY = "credential_authority"
    NETWORK_AUTHORITY = "network_authority"
    DESTRUCTIVE_FILESYSTEM_AUTHORITY = "destructive_filesystem_authority"


class OperationEffectClass(str, Enum):
    """Classification for requested operation effects."""

    SAFE_DRY_RUN = "safe_dry_run"
    BLOCKED_LIVE_EFFECT = "blocked_live_effect"
    UNKNOWN = "unknown"


class OperationTargetRisk(str, Enum):
    """Risk classification for operation target kinds."""

    LOW = "low"
    HIGH = "high"
    AMBIGUOUS = "ambiguous"


class OperationRequestIssueKind(str, Enum):
    """Issue vocabulary for operation request validation."""

    MISSING_FIELD = "missing_field"
    MISSING_AUTHORITY_NOTICE = "missing_authority_notice"
    STALE_AUTHORITY_NOTICE = "stale_authority_notice"
    FORBIDDEN_AUTHORITY_TIER = "forbidden_authority_tier"
    MISSING_SOURCE_REF = "missing_source_ref"
    MISSING_COMPLETION_REVIEW = "missing_completion_review"
    MISSING_SAFETY_FIELD = "missing_required_safety_field"
    AMBIGUOUS_RESOURCE_TARGET = "ambiguous_resource_target"
    LIVE_EFFECT_REQUESTED = "live_effect_requested"
    HIGH_RISK_REVIEW_REQUIRED = "high_risk_target_without_IR7-S03_review"
    MISSING_ROLLBACK_OR_ABORT_ROUTE = "missing_rollback_or_abort_route"
    CREDENTIAL_BOUNDARY_TOUCHED = "credential_boundary_touched"
    NETWORK_EXPOSURE_REQUESTED = "network_exposure_requested"
    DESTRUCTIVE_ACTION_POSSIBLE = "destructive_action_possible"
    COORDINATION_CLAIM_PROMOTED_TO_DISPATCH = "coordination_claim_promoted_to_dispatch"
    MAILBOX_CARRIER_PROMOTED_TO_DISPATCH = "mailbox_carrier_promoted_to_dispatch"
    GENERATED_PROJECTION_PROMOTED_TO_AUTHORITY = "generated_projection_promoted_to_authority"
    DRY_RUN_NOT_REQUIRED = "dry_run_not_required"


class OperationRequestIssueSeverity(str, Enum):
    """How a future operation projector should treat a request issue."""

    BLOCKED = "blocked"
    STALE = "stale"
    FAULT = "fault"
    INTERRUPT = "interrupt"
    REFUSED = "refused"
    REVIEW_REQUIRED = "review_required"


class OperationRequestStatus(str, Enum):
    """Projected status after pure request validation."""

    ACCEPTED = "accepted"
    BLOCKED = "blocked"
    BLOCKED_FOR_LIVE_EFFECT = "blocked_for_live_effect"
    FAULTED = "faulted"
    INTERRUPTED = "interrupted"
    REFUSED = "refused"
    REVIEW_REQUIRED = "review_required"
    STALE = "stale"


SAFE_DRY_RUN_EFFECT_SET: frozenset[str] = frozenset(
    {
        "inspect",
        "simulate",
        "estimate_resource_use",
        "classify_risk",
        "prepare_dry_run",
    }
)

BLOCKED_LIVE_EFFECT_SET: frozenset[str] = frozenset(
    {
        "command_execution",
        "process_control",
        "gpu_control",
        "gpu_workload_launch",
        "gpu_workload_cancel",
        "gpu_scheduler_mutation",
        "live_process_start",
        "live_process_stop",
        "live_process_priority_change",
        "model_runtime_start",
        "model_runtime_stop",
        "model_runtime_install",
        "model_runtime_upgrade",
        "model_runtime_configuration_mutation",
        "model_runtime_mutation",
        "job_dispatch",
        "job_cancellation",
        "job_dispatch_or_cancellation",
        "credential_access_or_mutation",
        "credential_mutation",
        "network_exposure_mutation",
        "network_mutation",
        "destructive_filesystem_action",
        "persistent_operations_automation",
        "agent_dispatch",
        "operations_control",
        "live_machine_control",
    }
)

TARGET_KIND_SET: frozenset[str] = frozenset(
    {
        "workspace_file",
        "process",
        "gpu",
        "model_runtime",
        "job_queue",
        "credential_or_secret",
        "network_service",
        "filesystem_destructive_target",
        "coordination_claim",
        "mailbox_carrier_context",
        "generated_projection",
        "unknown_or_ambiguous",
    }
)

HIGH_RISK_TARGET_SET: frozenset[str] = frozenset(
    {
        "process",
        "gpu",
        "model_runtime",
        "job_queue",
        "credential_or_secret",
        "network_service",
        "filesystem_destructive_target",
        "unknown_or_ambiguous",
    }
)

FORBIDDEN_AUTHORITY_TIER_SET: frozenset[OperationAuthorityTier] = frozenset(
    {
        OperationAuthorityTier.SOURCE_AUTHORITY,
        OperationAuthorityTier.LIVE_CONTROL_AUTHORITY,
        OperationAuthorityTier.DISPATCH_AUTHORITY,
        OperationAuthorityTier.CREDENTIAL_AUTHORITY,
        OperationAuthorityTier.NETWORK_AUTHORITY,
        OperationAuthorityTier.DESTRUCTIVE_FILESYSTEM_AUTHORITY,
    }
)

REQUIRED_OPERATION_REQUEST_IDENTITY_FIELD_SET: tuple[str, ...] = (
    "operation_request_id",
    "operation_request_uuid",
    "request_created_at",
    "requested_by",
    "conversation_uuid",
    "carrier_surface",
    "source_ref_set",
    "authority_notice_ref",
    "authority_tier",
    "freshness_state",
    "parent_request_ref",
    "completion_review_ref",
    "supersedes_request_ref_set",
    "source_projection_boundary_ref",
)

REQUIRED_OPERATION_REQUEST_SAFETY_FIELD_SET: tuple[str, ...] = (
    "intended_effect",
    "resource_target",
    "resource_target_classification",
    "risk_classification",
    "blast_radius",
    "dry_run_required",
    "rollback_or_abort_route",
    "credential_boundary_ref",
    "network_boundary_ref",
    "human_approval_ref",
    "predicted_side_effect_set",
    "stale_after",
    "refusal_policy_ref",
    "no_live_effect_rule_ref",
)


@dataclass(frozen=True)
class OperationRequestValidationIssue:
    """One blocked, stale, fault, interrupt, refusal, or review reason."""

    issue_kind: OperationRequestIssueKind
    severity: OperationRequestIssueSeverity
    reason: str
    field_name: str | None = None


@dataclass(frozen=True)
class OperationRequestValidationResult:
    """Pure validation result for one operation request envelope."""

    accepted: bool
    status: OperationRequestStatus
    issues: tuple[OperationRequestValidationIssue, ...] = ()
    effect_class: OperationEffectClass = OperationEffectClass.UNKNOWN
    target_risk: OperationTargetRisk = OperationTargetRisk.AMBIGUOUS

    @property
    def has_refusal(self) -> bool:
        return any(issue.severity == OperationRequestIssueSeverity.REFUSED for issue in self.issues)

    @property
    def has_fault(self) -> bool:
        return any(issue.severity == OperationRequestIssueSeverity.FAULT for issue in self.issues)

    @property
    def has_interrupt(self) -> bool:
        return any(issue.severity == OperationRequestIssueSeverity.INTERRUPT for issue in self.issues)

    @property
    def requires_review(self) -> bool:
        return any(issue.severity == OperationRequestIssueSeverity.REVIEW_REQUIRED for issue in self.issues)


@dataclass(frozen=True)
class OperationRequestEnvelope:
    """Identity, lineage, and safety envelope for a dry-run operation request."""

    operation_request_id: str
    operation_request_uuid: str
    request_created_at: str
    requested_by: str
    conversation_uuid: str
    carrier_surface: str
    source_ref_set: tuple[str, ...]
    authority_notice_ref: str
    authority_tier: OperationAuthorityTier
    freshness_state: OperationFreshnessState
    parent_request_ref: str
    completion_review_ref: str
    supersedes_request_ref_set: tuple[str, ...]
    source_projection_boundary_ref: str
    intended_effect: str
    resource_target: str
    resource_target_classification: str
    risk_classification: str
    blast_radius: str
    dry_run_required: bool
    rollback_or_abort_route: str
    credential_boundary_ref: str
    network_boundary_ref: str
    human_approval_ref: str
    predicted_side_effect_set: tuple[str, ...]
    stale_after: str
    refusal_policy_ref: str
    no_live_effect_rule_ref: str
    cited_authority_set: tuple[str, ...] = ()
    authority_notice_state: str = "present_and_fresh"
    requested_authority_promotion: bool = False

    @property
    def effect_class(self) -> OperationEffectClass:
        return classify_intended_effect(self.intended_effect)

    @property
    def target_risk(self) -> OperationTargetRisk:
        return classify_resource_target(self.resource_target)


def operation_request_envelope_from_parts(
    *,
    operation_request_id: str,
    operation_request_uuid: str,
    request_created_at: str,
    requested_by: str,
    conversation_uuid: str,
    carrier_surface: str,
    source_ref_set: Iterable[str],
    authority_notice_ref: str,
    authority_tier: str | OperationAuthorityTier,
    freshness_state: str | OperationFreshnessState,
    parent_request_ref: str,
    completion_review_ref: str,
    supersedes_request_ref_set: Iterable[str],
    source_projection_boundary_ref: str,
    intended_effect: str,
    resource_target: str,
    resource_target_classification: str,
    risk_classification: str,
    blast_radius: str,
    dry_run_required: bool,
    rollback_or_abort_route: str,
    credential_boundary_ref: str,
    network_boundary_ref: str,
    human_approval_ref: str,
    predicted_side_effect_set: Iterable[str],
    stale_after: str,
    refusal_policy_ref: str,
    no_live_effect_rule_ref: str,
    cited_authority_set: Iterable[str] = (),
    authority_notice_state: str = "present_and_fresh",
    requested_authority_promotion: bool = False,
) -> OperationRequestEnvelope:
    """Build an operation request envelope while normalizing sets and enums."""

    return OperationRequestEnvelope(
        operation_request_id=operation_request_id,
        operation_request_uuid=operation_request_uuid,
        request_created_at=request_created_at,
        requested_by=requested_by,
        conversation_uuid=conversation_uuid,
        carrier_surface=carrier_surface,
        source_ref_set=tuple(source_ref_set),
        authority_notice_ref=authority_notice_ref,
        authority_tier=OperationAuthorityTier(authority_tier),
        freshness_state=OperationFreshnessState(freshness_state),
        parent_request_ref=parent_request_ref,
        completion_review_ref=completion_review_ref,
        supersedes_request_ref_set=tuple(supersedes_request_ref_set),
        source_projection_boundary_ref=source_projection_boundary_ref,
        intended_effect=intended_effect,
        resource_target=resource_target,
        resource_target_classification=resource_target_classification,
        risk_classification=risk_classification,
        blast_radius=blast_radius,
        dry_run_required=dry_run_required,
        rollback_or_abort_route=rollback_or_abort_route,
        credential_boundary_ref=credential_boundary_ref,
        network_boundary_ref=network_boundary_ref,
        human_approval_ref=human_approval_ref,
        predicted_side_effect_set=tuple(predicted_side_effect_set),
        stale_after=stale_after,
        refusal_policy_ref=refusal_policy_ref,
        no_live_effect_rule_ref=no_live_effect_rule_ref,
        cited_authority_set=tuple(cited_authority_set),
        authority_notice_state=authority_notice_state,
        requested_authority_promotion=requested_authority_promotion,
    )


def operation_request_envelope_from_mapping(data: Mapping[str, object]) -> OperationRequestEnvelope:
    """Build an operation request envelope from mapping data."""

    request_id = str(data.get("operation_request_id", ""))
    return operation_request_envelope_from_parts(
        operation_request_id=request_id,
        operation_request_uuid=str(data.get("operation_request_uuid", request_id)),
        request_created_at=str(data.get("request_created_at", "")),
        requested_by=str(data.get("requested_by", "")),
        conversation_uuid=str(data.get("conversation_uuid", "")),
        carrier_surface=str(data.get("carrier_surface", "")),
        source_ref_set=_as_string_sequence(data.get("source_ref_set", ())),
        authority_notice_ref=str(data.get("authority_notice_ref", "")),
        authority_tier=str(data.get("authority_tier", OperationAuthorityTier.OPERATIONS_PLANNING_RECORD.value)),
        freshness_state=str(data.get("freshness_state", OperationFreshnessState.UNKNOWN.value)),
        parent_request_ref=str(data.get("parent_request_ref", "none")),
        completion_review_ref=str(data.get("completion_review_ref", "")),
        supersedes_request_ref_set=_as_string_sequence(data.get("supersedes_request_ref_set", ())),
        source_projection_boundary_ref=str(data.get("source_projection_boundary_ref", "")),
        intended_effect=str(data.get("intended_effect", "")),
        resource_target=str(data.get("resource_target", "unknown_or_ambiguous")),
        resource_target_classification=str(data.get("resource_target_classification", "")),
        risk_classification=str(data.get("risk_classification", "")),
        blast_radius=str(data.get("blast_radius", "")),
        dry_run_required=_as_bool(data.get("dry_run_required", True)),
        rollback_or_abort_route=str(data.get("rollback_or_abort_route", "")),
        credential_boundary_ref=str(data.get("credential_boundary_ref", "")),
        network_boundary_ref=str(data.get("network_boundary_ref", "")),
        human_approval_ref=str(data.get("human_approval_ref", "empty_until_explicit_fresh_scoped_approval_exists")),
        predicted_side_effect_set=_as_string_sequence(data.get("predicted_side_effect_set", ())),
        stale_after=str(data.get("stale_after", "")),
        refusal_policy_ref=str(data.get("refusal_policy_ref", "")),
        no_live_effect_rule_ref=str(data.get("no_live_effect_rule_ref", "")),
        cited_authority_set=_as_string_sequence(data.get("cited_authority_set", ())),
        authority_notice_state=str(data.get("authority_notice_state", "present_and_fresh")),
        requested_authority_promotion=_as_bool(data.get("requested_authority_promotion", False)),
    )


def classify_intended_effect(intended_effect: str) -> OperationEffectClass:
    """Classify an intended effect without opening an execution path."""

    if intended_effect in SAFE_DRY_RUN_EFFECT_SET:
        return OperationEffectClass.SAFE_DRY_RUN
    if intended_effect in BLOCKED_LIVE_EFFECT_SET:
        return OperationEffectClass.BLOCKED_LIVE_EFFECT
    return OperationEffectClass.UNKNOWN


def classify_resource_target(resource_target: str) -> OperationTargetRisk:
    """Classify an operation target kind without touching the target."""

    if resource_target == "unknown_or_ambiguous" or resource_target not in TARGET_KIND_SET:
        return OperationTargetRisk.AMBIGUOUS
    if resource_target in HIGH_RISK_TARGET_SET:
        return OperationTargetRisk.HIGH
    return OperationTargetRisk.LOW


def validate_operation_request_envelope(
    envelope: OperationRequestEnvelope,
) -> OperationRequestValidationResult:
    """Validate an operation request against IR7 dry-run request constraints."""

    issues: list[OperationRequestValidationIssue] = []

    for field_name in REQUIRED_OPERATION_REQUEST_IDENTITY_FIELD_SET:
        if not _field_has_value(envelope, field_name):
            issues.append(_missing_field_issue(field_name))

    for field_name in REQUIRED_OPERATION_REQUEST_SAFETY_FIELD_SET:
        if not _field_has_value(envelope, field_name):
            issues.append(
                OperationRequestValidationIssue(
                    OperationRequestIssueKind.MISSING_SAFETY_FIELD,
                    OperationRequestIssueSeverity.FAULT,
                    f"{field_name} is required before dry-run operation planning",
                    field_name,
                )
            )

    if not envelope.source_ref_set:
        issues.append(
            OperationRequestValidationIssue(
                OperationRequestIssueKind.MISSING_SOURCE_REF,
                OperationRequestIssueSeverity.FAULT,
                "source_ref_set is required before request projection use",
                "source_ref_set",
            )
        )

    if not envelope.completion_review_ref:
        issues.append(
            OperationRequestValidationIssue(
                OperationRequestIssueKind.MISSING_COMPLETION_REVIEW,
                OperationRequestIssueSeverity.FAULT,
                "completion_review_ref is required before request projection use",
                "completion_review_ref",
            )
        )

    if not envelope.authority_notice_ref:
        issues.append(
            OperationRequestValidationIssue(
                OperationRequestIssueKind.MISSING_AUTHORITY_NOTICE,
                OperationRequestIssueSeverity.FAULT,
                "authority notice ref is required before request projection use",
                "authority_notice_ref",
            )
        )

    if envelope.authority_notice_state in {"missing", "missing_or_stale", "stale"}:
        issues.append(
            OperationRequestValidationIssue(
                OperationRequestIssueKind.STALE_AUTHORITY_NOTICE,
                OperationRequestIssueSeverity.STALE,
                "authority notice must be present and fresh",
                "authority_notice_state",
            )
        )

    if envelope.freshness_state != OperationFreshnessState.FRESH:
        issues.append(
            OperationRequestValidationIssue(
                OperationRequestIssueKind.STALE_AUTHORITY_NOTICE,
                _severity_for_freshness(envelope.freshness_state),
                "freshness state must be fresh before request projection is trusted",
                "freshness_state",
            )
        )

    if envelope.authority_tier in FORBIDDEN_AUTHORITY_TIER_SET:
        issues.append(
            OperationRequestValidationIssue(
                OperationRequestIssueKind.FORBIDDEN_AUTHORITY_TIER,
                OperationRequestIssueSeverity.REFUSED,
                "operation requests may not claim source, dispatch, credential, network, destructive, or live-control authority",
                "authority_tier",
            )
        )

    if not envelope.dry_run_required:
        issues.append(
            OperationRequestValidationIssue(
                OperationRequestIssueKind.DRY_RUN_NOT_REQUIRED,
                OperationRequestIssueSeverity.REFUSED,
                "IR7 operation requests must remain dry-run-required",
                "dry_run_required",
            )
        )

    if classify_intended_effect(envelope.intended_effect) == OperationEffectClass.BLOCKED_LIVE_EFFECT:
        issues.append(
            OperationRequestValidationIssue(
                OperationRequestIssueKind.LIVE_EFFECT_REQUESTED,
                OperationRequestIssueSeverity.REFUSED,
                "requested effect is a blocked live effect",
                "intended_effect",
            )
        )

    target_risk = classify_resource_target(envelope.resource_target)
    if target_risk == OperationTargetRisk.AMBIGUOUS:
        issues.append(
            OperationRequestValidationIssue(
                OperationRequestIssueKind.AMBIGUOUS_RESOURCE_TARGET,
                OperationRequestIssueSeverity.INTERRUPT,
                "resource target is unknown or ambiguous",
                "resource_target",
            )
        )

    if not envelope.rollback_or_abort_route:
        issues.append(
            OperationRequestValidationIssue(
                OperationRequestIssueKind.MISSING_ROLLBACK_OR_ABORT_ROUTE,
                OperationRequestIssueSeverity.BLOCKED,
                "rollback or abort route is required before operation planning",
                "rollback_or_abort_route",
            )
        )

    issues.extend(_target_specific_issues(envelope))
    issues.extend(_authority_promotion_issues(envelope))

    if _requires_resource_safety_review(envelope):
        issues.append(
            OperationRequestValidationIssue(
                OperationRequestIssueKind.HIGH_RISK_REVIEW_REQUIRED,
                OperationRequestIssueSeverity.REVIEW_REQUIRED,
                "uncertain high-risk request requires IR7-S03 resource safety review",
                "resource_target",
            )
        )

    status = operation_request_status_for_issues(issues, envelope.effect_class)
    return OperationRequestValidationResult(
        status == OperationRequestStatus.ACCEPTED,
        status,
        tuple(issues),
        envelope.effect_class,
        target_risk,
    )


def operation_request_status_for_issues(
    issues: Iterable[OperationRequestValidationIssue],
    effect_class: OperationEffectClass = OperationEffectClass.UNKNOWN,
) -> OperationRequestStatus:
    """Map validation issues to the stable request status priority."""

    issue_tuple = tuple(issues)
    if any(issue.severity == OperationRequestIssueSeverity.FAULT for issue in issue_tuple):
        return OperationRequestStatus.FAULTED
    if any(issue.issue_kind == OperationRequestIssueKind.LIVE_EFFECT_REQUESTED for issue in issue_tuple):
        return OperationRequestStatus.BLOCKED_FOR_LIVE_EFFECT
    if any(issue.severity == OperationRequestIssueSeverity.REFUSED for issue in issue_tuple):
        return OperationRequestStatus.REFUSED
    if any(issue.severity == OperationRequestIssueSeverity.INTERRUPT for issue in issue_tuple):
        return OperationRequestStatus.INTERRUPTED
    if any(issue.severity == OperationRequestIssueSeverity.STALE for issue in issue_tuple):
        return OperationRequestStatus.STALE
    if any(issue.severity == OperationRequestIssueSeverity.REVIEW_REQUIRED for issue in issue_tuple):
        return OperationRequestStatus.REVIEW_REQUIRED
    if any(issue.severity == OperationRequestIssueSeverity.BLOCKED for issue in issue_tuple):
        return OperationRequestStatus.BLOCKED
    if effect_class == OperationEffectClass.UNKNOWN:
        return OperationRequestStatus.INTERRUPTED
    return OperationRequestStatus.ACCEPTED


def _missing_field_issue(field_name: str) -> OperationRequestValidationIssue:
    return OperationRequestValidationIssue(
        OperationRequestIssueKind.MISSING_FIELD,
        OperationRequestIssueSeverity.FAULT,
        f"{field_name} is required",
        field_name,
    )


def _field_has_value(envelope: object, field_name: str) -> bool:
    value = getattr(envelope, field_name)
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value)
    if isinstance(value, tuple):
        return True
    return True


def _severity_for_freshness(freshness_state: OperationFreshnessState) -> OperationRequestIssueSeverity:
    if freshness_state == OperationFreshnessState.FAULTED:
        return OperationRequestIssueSeverity.FAULT
    if freshness_state == OperationFreshnessState.INTERRUPTED:
        return OperationRequestIssueSeverity.INTERRUPT
    if freshness_state == OperationFreshnessState.STALE:
        return OperationRequestIssueSeverity.STALE
    return OperationRequestIssueSeverity.BLOCKED


def _target_specific_issues(envelope: OperationRequestEnvelope) -> tuple[OperationRequestValidationIssue, ...]:
    issues: list[OperationRequestValidationIssue] = []
    if envelope.resource_target == "credential_or_secret" or envelope.intended_effect == "credential_access_or_mutation":
        issues.append(
            OperationRequestValidationIssue(
                OperationRequestIssueKind.CREDENTIAL_BOUNDARY_TOUCHED,
                OperationRequestIssueSeverity.REFUSED,
                "credential targets remain opaque references and cannot be accessed",
                "resource_target",
            )
        )
    if envelope.resource_target == "network_service" or envelope.intended_effect == "network_exposure_mutation":
        issues.append(
            OperationRequestValidationIssue(
                OperationRequestIssueKind.NETWORK_EXPOSURE_REQUESTED,
                OperationRequestIssueSeverity.REFUSED,
                "network exposure mutation is not authorized",
                "resource_target",
            )
        )
    if (
        envelope.resource_target == "filesystem_destructive_target"
        or envelope.intended_effect == "destructive_filesystem_action"
    ):
        issues.append(
            OperationRequestValidationIssue(
                OperationRequestIssueKind.DESTRUCTIVE_ACTION_POSSIBLE,
                OperationRequestIssueSeverity.REFUSED,
                "destructive filesystem action is not authorized",
                "resource_target",
            )
        )
    return tuple(issues)


def _authority_promotion_issues(
    envelope: OperationRequestEnvelope,
) -> tuple[OperationRequestValidationIssue, ...]:
    cited = set(envelope.cited_authority_set)
    issues: list[OperationRequestValidationIssue] = []
    if envelope.intended_effect in {"job_dispatch", "job_cancellation"}:
        if "coordination_claim" in cited:
            issues.append(
                OperationRequestValidationIssue(
                    OperationRequestIssueKind.COORDINATION_CLAIM_PROMOTED_TO_DISPATCH,
                    OperationRequestIssueSeverity.REFUSED,
                    "coordination claims cannot become dispatch authority",
                    "cited_authority_set",
                )
            )
        if "mailbox_carrier_context" in cited:
            issues.append(
                OperationRequestValidationIssue(
                    OperationRequestIssueKind.MAILBOX_CARRIER_PROMOTED_TO_DISPATCH,
                    OperationRequestIssueSeverity.REFUSED,
                    "mailbox carriers cannot become dispatch authority",
                    "cited_authority_set",
                )
            )
        if "successful_dry_run_record" in cited or "dry_run_result" in cited:
            issues.append(
                OperationRequestValidationIssue(
                    OperationRequestIssueKind.LIVE_EFFECT_REQUESTED,
                    OperationRequestIssueSeverity.REFUSED,
                    "dry-run success cannot become dispatch permission",
                    "cited_authority_set",
                )
            )
    if envelope.requested_authority_promotion or cited & {"generated_projection", "fixture_success"}:
        issues.append(
            OperationRequestValidationIssue(
                OperationRequestIssueKind.GENERATED_PROJECTION_PROMOTED_TO_AUTHORITY,
                OperationRequestIssueSeverity.REFUSED,
                "generated projections and fixture success cannot become source or live-control authority",
                "cited_authority_set",
            )
        )
    return tuple(issues)


def _requires_resource_safety_review(envelope: OperationRequestEnvelope) -> bool:
    if envelope.effect_class != OperationEffectClass.SAFE_DRY_RUN:
        return False
    if envelope.target_risk != OperationTargetRisk.HIGH:
        return False
    return bool(
        envelope.predicted_side_effect_set
        or envelope.blast_radius in {"uncertain", "wide", "critical", "unknown"}
        or envelope.risk_classification in {"critical", "high", "unknown"}
    )


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
