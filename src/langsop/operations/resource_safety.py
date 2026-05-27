"""Resource safety, approval freshness, and rollback models for IR7.

The records in this module are planning evidence only. They classify risk,
approval freshness, rollback support, and refusal routes without accessing
credentials, mutating networks, dispatching jobs, or controlling live systems.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .requests import (
    BLOCKED_LIVE_EFFECT_SET,
    HIGH_RISK_TARGET_SET,
    OperationFreshnessState,
    OperationRequestEnvelope,
    classify_intended_effect,
)


class ResourceRiskLevel(str, Enum):
    """Accepted resource risk levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class ResourceTargetSafetyClass(str, Enum):
    """Safety classification for resource target kinds."""

    LOW_RISK = "low_risk"
    MEDIUM_RISK = "medium_risk"
    HIGH_RISK = "high_risk"
    CRITICAL_RISK = "critical_risk"
    UNKNOWN_OR_AMBIGUOUS = "unknown_or_ambiguous"


class HumanApprovalState(str, Enum):
    """Accepted human approval states."""

    ABSENT = "absent"
    REQUESTED = "requested"
    FRESH_SCOPED = "fresh_scoped"
    STALE = "stale"
    REVOKED = "revoked"
    MISMATCHED = "mismatched"
    BROAD_INVALID = "broad_invalid"


class ResourceSafetyIssueKind(str, Enum):
    """Issue vocabulary for resource safety review."""

    BROAD_STANDING_APPROVAL = "broad_standing_approval"
    STALE_APPROVAL = "stale_approval"
    REVOKED_APPROVAL = "revoked_approval"
    MISMATCHED_INTENDED_EFFECT = "mismatched_intended_effect"
    MISMATCHED_RESOURCE_TARGET = "mismatched_resource_target"
    MISSING_BLAST_RADIUS = "missing_blast_radius"
    UNKNOWN_BLAST_RADIUS = "unknown_blast_radius"
    MISSING_ROLLBACK_OR_ABORT_ROUTE = "missing_rollback_or_abort_route"
    MISSING_AUTHORITY_NOTICE = "missing_authority_notice"
    CREDENTIAL_BOUNDARY_UNREVIEWED = "credential_boundary_unreviewed"
    NETWORK_BOUNDARY_UNREVIEWED = "network_boundary_unreviewed"
    DESTRUCTIVE_ACTION_POSSIBLE = "destructive_action_possible"
    LIVE_CONTROL_IMPLICATION = "live_control_implication"
    SECRET_VALUE_PRESENT = "secret_value_present"
    MONITORING_SIGNAL_MISSING = "monitoring_signal_missing"


class ResourceSafetyIssueSeverity(str, Enum):
    """How a resource safety issue should be treated."""

    BLOCKED = "blocked"
    CRITICAL = "critical"
    INTERRUPT = "interrupt"
    REFUSED = "refused"
    REVIEW_REQUIRED = "review_required"


REQUIRED_BLAST_RADIUS_FIELD_SET: tuple[str, ...] = (
    "affected_resource_set",
    "expected_duration",
    "cost_or_utilization_estimate",
    "possible_side_effect_set",
    "rollback_or_abort_route_ref",
    "monitoring_signal_set",
    "owner_or_human_contact_ref",
    "stale_after",
    "authority_notice_ref",
)

REQUIRED_ROLLBACK_ROUTE_FIELD_SET: tuple[str, ...] = (
    "rollback_or_abort_route_id",
    "abort_condition_set",
    "rollback_step_set",
    "safe_shutdown_condition",
    "monitoring_signal_set",
    "owner_or_human_contact_ref",
    "stale_after",
    "authority_notice_ref",
    "affected_resource_set",
)

REQUIRED_HUMAN_APPROVAL_FIELD_SET: tuple[str, ...] = (
    "human_approval_id",
    "approved_by",
    "approved_at",
    "approved_operation_request_ref",
    "approved_intended_effect",
    "approved_resource_target",
    "authority_notice_ref",
    "risk_classification",
    "blast_radius_ref",
    "rollback_or_abort_route_ref",
    "expiration_or_stale_after",
    "explicit_limit_set",
    "revocation_route",
)

CRITICAL_TARGET_SET: frozenset[str] = frozenset(
    {"credential_or_secret", "network_service", "filesystem_destructive_target"}
)


@dataclass(frozen=True)
class ResourceSafetyIssue:
    """One resource safety blocker, critical condition, refusal, or review need."""

    issue_kind: ResourceSafetyIssueKind
    severity: ResourceSafetyIssueSeverity
    reason: str
    evidence_ref_set: tuple[str, ...] = ()


@dataclass(frozen=True)
class BlastRadiusEnvelope:
    """Blast-radius evidence for resource safety review."""

    affected_resource_set: tuple[str, ...]
    expected_duration: str
    cost_or_utilization_estimate: str
    possible_side_effect_set: tuple[str, ...]
    rollback_or_abort_route_ref: str
    monitoring_signal_set: tuple[str, ...]
    owner_or_human_contact_ref: str
    stale_after: str
    authority_notice_ref: str
    blast_radius_state: str = "known"


@dataclass(frozen=True)
class RollbackAbortRouteEnvelope:
    """Rollback, abort, and monitoring route evidence."""

    rollback_or_abort_route_id: str
    abort_condition_set: tuple[str, ...]
    rollback_step_set: tuple[str, ...]
    safe_shutdown_condition: str
    monitoring_signal_set: tuple[str, ...]
    owner_or_human_contact_ref: str
    stale_after: str
    authority_notice_ref: str
    affected_resource_set: tuple[str, ...]
    route_state: str = "fresh"


@dataclass(frozen=True)
class HumanApprovalEnvelope:
    """Scoped human approval evidence for a concrete operation request."""

    human_approval_id: str
    approved_by: str
    approved_at: str
    approved_operation_request_ref: str
    approved_intended_effect: str
    approved_resource_target: str
    authority_notice_ref: str
    risk_classification: str
    blast_radius_ref: str
    rollback_or_abort_route_ref: str
    expiration_or_stale_after: str
    explicit_limit_set: tuple[str, ...]
    revocation_route: str
    approval_state: HumanApprovalState = HumanApprovalState.ABSENT
    broad_approval_requested: bool = False
    live_control_authority_claimed: bool = False


@dataclass(frozen=True)
class ResourceSafetyReview:
    """Pure resource safety review result for an operation request."""

    operation_request_ref: str
    target_safety_class: ResourceTargetSafetyClass
    risk_level: ResourceRiskLevel
    required_human_review: bool
    live_control_authorized: bool
    issues: tuple[ResourceSafetyIssue, ...] = ()
    safe_next_route_set: tuple[str, ...] = ()

    @property
    def accepted(self) -> bool:
        return not self.issues and not self.live_control_authorized

    @property
    def has_refusal(self) -> bool:
        return any(issue.severity == ResourceSafetyIssueSeverity.REFUSED for issue in self.issues)

    @property
    def has_critical(self) -> bool:
        return any(issue.severity == ResourceSafetyIssueSeverity.CRITICAL for issue in self.issues)


def blast_radius_envelope_from_parts(
    *,
    affected_resource_set: Iterable[str],
    expected_duration: str,
    cost_or_utilization_estimate: str,
    possible_side_effect_set: Iterable[str],
    rollback_or_abort_route_ref: str,
    monitoring_signal_set: Iterable[str],
    owner_or_human_contact_ref: str,
    stale_after: str,
    authority_notice_ref: str,
    blast_radius_state: str = "known",
) -> BlastRadiusEnvelope:
    """Build blast-radius evidence while normalizing sets."""

    return BlastRadiusEnvelope(
        affected_resource_set=tuple(affected_resource_set),
        expected_duration=expected_duration,
        cost_or_utilization_estimate=cost_or_utilization_estimate,
        possible_side_effect_set=tuple(possible_side_effect_set),
        rollback_or_abort_route_ref=rollback_or_abort_route_ref,
        monitoring_signal_set=tuple(monitoring_signal_set),
        owner_or_human_contact_ref=owner_or_human_contact_ref,
        stale_after=stale_after,
        authority_notice_ref=authority_notice_ref,
        blast_radius_state=blast_radius_state,
    )


def rollback_abort_route_envelope_from_parts(
    *,
    rollback_or_abort_route_id: str,
    abort_condition_set: Iterable[str],
    rollback_step_set: Iterable[str],
    safe_shutdown_condition: str,
    monitoring_signal_set: Iterable[str],
    owner_or_human_contact_ref: str,
    stale_after: str,
    authority_notice_ref: str,
    affected_resource_set: Iterable[str],
    route_state: str = "fresh",
) -> RollbackAbortRouteEnvelope:
    """Build rollback route evidence while normalizing sets."""

    return RollbackAbortRouteEnvelope(
        rollback_or_abort_route_id=rollback_or_abort_route_id,
        abort_condition_set=tuple(abort_condition_set),
        rollback_step_set=tuple(rollback_step_set),
        safe_shutdown_condition=safe_shutdown_condition,
        monitoring_signal_set=tuple(monitoring_signal_set),
        owner_or_human_contact_ref=owner_or_human_contact_ref,
        stale_after=stale_after,
        authority_notice_ref=authority_notice_ref,
        affected_resource_set=tuple(affected_resource_set),
        route_state=route_state,
    )


def human_approval_envelope_from_parts(
    *,
    human_approval_id: str,
    approved_by: str,
    approved_at: str,
    approved_operation_request_ref: str,
    approved_intended_effect: str,
    approved_resource_target: str,
    authority_notice_ref: str,
    risk_classification: str,
    blast_radius_ref: str,
    rollback_or_abort_route_ref: str,
    expiration_or_stale_after: str,
    explicit_limit_set: Iterable[str],
    revocation_route: str,
    approval_state: str | HumanApprovalState = HumanApprovalState.ABSENT,
    broad_approval_requested: bool = False,
    live_control_authority_claimed: bool = False,
) -> HumanApprovalEnvelope:
    """Build scoped human approval evidence while normalizing sets and enums."""

    return HumanApprovalEnvelope(
        human_approval_id=human_approval_id,
        approved_by=approved_by,
        approved_at=approved_at,
        approved_operation_request_ref=approved_operation_request_ref,
        approved_intended_effect=approved_intended_effect,
        approved_resource_target=approved_resource_target,
        authority_notice_ref=authority_notice_ref,
        risk_classification=risk_classification,
        blast_radius_ref=blast_radius_ref,
        rollback_or_abort_route_ref=rollback_or_abort_route_ref,
        expiration_or_stale_after=expiration_or_stale_after,
        explicit_limit_set=tuple(explicit_limit_set),
        revocation_route=revocation_route,
        approval_state=HumanApprovalState(approval_state),
        broad_approval_requested=broad_approval_requested,
        live_control_authority_claimed=live_control_authority_claimed,
    )


def classify_resource_target_safety(resource_target_kind: str) -> ResourceTargetSafetyClass:
    """Classify a resource target for planning-only safety review."""

    if resource_target_kind in {"workspace_file", "tracked_fixture_source"}:
        return ResourceTargetSafetyClass.LOW_RISK
    if resource_target_kind == "generated_projection_root":
        return ResourceTargetSafetyClass.MEDIUM_RISK
    if resource_target_kind in CRITICAL_TARGET_SET:
        return ResourceTargetSafetyClass.CRITICAL_RISK
    if resource_target_kind in HIGH_RISK_TARGET_SET or resource_target_kind in {
        "coordination_claim",
        "mailbox_carrier_context",
    }:
        return ResourceTargetSafetyClass.HIGH_RISK
    return ResourceTargetSafetyClass.UNKNOWN_OR_AMBIGUOUS


def risk_level_for_request(
    request: OperationRequestEnvelope,
    blast_radius: BlastRadiusEnvelope | None = None,
) -> ResourceRiskLevel:
    """Classify request risk without authorizing operation effects."""

    if _has_critical_boundary(request):
        return ResourceRiskLevel.CRITICAL
    if request.freshness_state != OperationFreshnessState.FRESH or not request.authority_notice_ref:
        return ResourceRiskLevel.CRITICAL
    if not request.rollback_or_abort_route:
        return ResourceRiskLevel.CRITICAL
    if request.blast_radius in {"unknown", "uncertain"}:
        return ResourceRiskLevel.CRITICAL
    if blast_radius is None and request.resource_target in HIGH_RISK_TARGET_SET:
        return ResourceRiskLevel.HIGH
    if blast_radius is not None and blast_radius.blast_radius_state in {"unknown", "uncertain"}:
        return ResourceRiskLevel.CRITICAL

    target_class = classify_resource_target_safety(request.resource_target)
    if target_class == ResourceTargetSafetyClass.CRITICAL_RISK:
        return ResourceRiskLevel.CRITICAL
    if target_class == ResourceTargetSafetyClass.HIGH_RISK:
        return ResourceRiskLevel.HIGH
    if target_class == ResourceTargetSafetyClass.MEDIUM_RISK:
        return ResourceRiskLevel.MEDIUM
    if target_class == ResourceTargetSafetyClass.LOW_RISK:
        return ResourceRiskLevel.LOW
    return ResourceRiskLevel.UNKNOWN


def review_resource_safety(
    request: OperationRequestEnvelope,
    *,
    blast_radius: BlastRadiusEnvelope | None = None,
    rollback_route: RollbackAbortRouteEnvelope | None = None,
    human_approval: HumanApprovalEnvelope | None = None,
) -> ResourceSafetyReview:
    """Review resource safety evidence without performing live effects."""

    issues: list[ResourceSafetyIssue] = []
    issues.extend(_request_safety_issues(request, blast_radius))
    if blast_radius is None and request.resource_target in HIGH_RISK_TARGET_SET:
        issues.append(
            ResourceSafetyIssue(
                ResourceSafetyIssueKind.MISSING_BLAST_RADIUS,
                ResourceSafetyIssueSeverity.REVIEW_REQUIRED,
                "high-risk requests require blast-radius evidence",
                (request.operation_request_id,),
            )
        )
    elif blast_radius is not None:
        issues.extend(validate_blast_radius(blast_radius))

    if rollback_route is None and request.resource_target in HIGH_RISK_TARGET_SET:
        issues.append(
            ResourceSafetyIssue(
                ResourceSafetyIssueKind.MISSING_ROLLBACK_OR_ABORT_ROUTE,
                ResourceSafetyIssueSeverity.BLOCKED,
                "high-risk requests require rollback or abort route evidence",
                (request.operation_request_id,),
            )
        )
    elif rollback_route is not None:
        issues.extend(validate_rollback_abort_route(rollback_route))

    if human_approval is None and _requires_human_review(request, blast_radius):
        issues.append(
            ResourceSafetyIssue(
                ResourceSafetyIssueKind.STALE_APPROVAL,
                ResourceSafetyIssueSeverity.REVIEW_REQUIRED,
                "fresh scoped human approval is required for high or critical risk",
                (request.operation_request_id,),
            )
        )
    elif human_approval is not None:
        issues.extend(validate_human_approval_for_request(human_approval, request))

    risk_level = risk_level_for_request(request, blast_radius)
    return ResourceSafetyReview(
        operation_request_ref=request.operation_request_id,
        target_safety_class=classify_resource_target_safety(request.resource_target),
        risk_level=risk_level,
        required_human_review=_requires_human_review(request, blast_radius) or bool(issues),
        live_control_authorized=False,
        issues=tuple(issues),
        safe_next_route_set=_safe_routes_for_issues(issues),
    )


def validate_blast_radius(blast_radius: BlastRadiusEnvelope) -> tuple[ResourceSafetyIssue, ...]:
    """Validate blast-radius evidence for resource safety review."""

    issues: list[ResourceSafetyIssue] = []
    for field_name in REQUIRED_BLAST_RADIUS_FIELD_SET:
        if not _field_has_value(blast_radius, field_name):
            issues.append(
                ResourceSafetyIssue(
                    ResourceSafetyIssueKind.MISSING_BLAST_RADIUS,
                    ResourceSafetyIssueSeverity.BLOCKED,
                    f"{field_name} is required for blast-radius evidence",
                    (field_name,),
                )
            )
    if blast_radius.blast_radius_state in {"unknown", "uncertain"}:
        issues.append(
            ResourceSafetyIssue(
                ResourceSafetyIssueKind.UNKNOWN_BLAST_RADIUS,
                ResourceSafetyIssueSeverity.CRITICAL,
                "unknown or uncertain blast radius blocks operation planning",
                (blast_radius.rollback_or_abort_route_ref,),
            )
        )
    if not blast_radius.monitoring_signal_set:
        issues.append(
            ResourceSafetyIssue(
                ResourceSafetyIssueKind.MONITORING_SIGNAL_MISSING,
                ResourceSafetyIssueSeverity.BLOCKED,
                "monitoring signals are required for resource safety review",
                (blast_radius.rollback_or_abort_route_ref,),
            )
        )
    return tuple(issues)


def validate_rollback_abort_route(route: RollbackAbortRouteEnvelope) -> tuple[ResourceSafetyIssue, ...]:
    """Validate rollback and abort route evidence."""

    issues: list[ResourceSafetyIssue] = []
    for field_name in REQUIRED_ROLLBACK_ROUTE_FIELD_SET:
        if not _field_has_value(route, field_name):
            issues.append(
                ResourceSafetyIssue(
                    ResourceSafetyIssueKind.MISSING_ROLLBACK_OR_ABORT_ROUTE,
                    ResourceSafetyIssueSeverity.BLOCKED,
                    f"{field_name} is required for rollback or abort route evidence",
                    (field_name,),
                )
            )
    if route.route_state != "fresh":
        issues.append(
            ResourceSafetyIssue(
                ResourceSafetyIssueKind.MISSING_ROLLBACK_OR_ABORT_ROUTE,
                ResourceSafetyIssueSeverity.BLOCKED,
                "rollback or abort route must be fresh",
                (route.rollback_or_abort_route_id,),
            )
        )
    return tuple(issues)


def validate_human_approval_for_request(
    approval: HumanApprovalEnvelope,
    request: OperationRequestEnvelope,
) -> tuple[ResourceSafetyIssue, ...]:
    """Validate scoped human approval evidence against a request."""

    issues: list[ResourceSafetyIssue] = []
    for field_name in REQUIRED_HUMAN_APPROVAL_FIELD_SET:
        if not _field_has_value(approval, field_name):
            issues.append(
                ResourceSafetyIssue(
                    ResourceSafetyIssueKind.STALE_APPROVAL,
                    ResourceSafetyIssueSeverity.BLOCKED,
                    f"{field_name} is required for human approval evidence",
                    (field_name,),
                )
            )

    if approval.broad_approval_requested or approval.approval_state == HumanApprovalState.BROAD_INVALID:
        issues.append(
            ResourceSafetyIssue(
                ResourceSafetyIssueKind.BROAD_STANDING_APPROVAL,
                ResourceSafetyIssueSeverity.REFUSED,
                "broad standing approval cannot authorize operation control",
                (approval.human_approval_id,),
            )
        )
    if approval.approval_state == HumanApprovalState.STALE:
        issues.append(_approval_issue(ResourceSafetyIssueKind.STALE_APPROVAL, approval, "human approval is stale"))
    if approval.approval_state == HumanApprovalState.REVOKED:
        issues.append(_approval_issue(ResourceSafetyIssueKind.REVOKED_APPROVAL, approval, "human approval is revoked"))
    if approval.approval_state == HumanApprovalState.MISMATCHED:
        issues.append(
            _approval_issue(ResourceSafetyIssueKind.MISMATCHED_RESOURCE_TARGET, approval, "human approval is mismatched")
        )
    if approval.approved_operation_request_ref != request.operation_request_id:
        issues.append(
            _approval_issue(
                ResourceSafetyIssueKind.MISMATCHED_RESOURCE_TARGET,
                approval,
                "approval operation request ref does not match request",
            )
        )
    if approval.approved_intended_effect != request.intended_effect:
        issues.append(
            _approval_issue(
                ResourceSafetyIssueKind.MISMATCHED_INTENDED_EFFECT,
                approval,
                "approval intended effect does not match request",
            )
        )
    if approval.approved_resource_target != request.resource_target:
        issues.append(
            _approval_issue(
                ResourceSafetyIssueKind.MISMATCHED_RESOURCE_TARGET,
                approval,
                "approval resource target does not match request",
            )
        )
    if approval.live_control_authority_claimed:
        issues.append(
            ResourceSafetyIssue(
                ResourceSafetyIssueKind.LIVE_CONTROL_IMPLICATION,
                ResourceSafetyIssueSeverity.REFUSED,
                "human approval evidence cannot claim live-control authority",
                (approval.human_approval_id,),
            )
        )
    return tuple(issues)


def _request_safety_issues(
    request: OperationRequestEnvelope,
    blast_radius: BlastRadiusEnvelope | None,
) -> tuple[ResourceSafetyIssue, ...]:
    issues: list[ResourceSafetyIssue] = []
    if not request.authority_notice_ref or request.freshness_state != OperationFreshnessState.FRESH:
        issues.append(
            ResourceSafetyIssue(
                ResourceSafetyIssueKind.MISSING_AUTHORITY_NOTICE,
                ResourceSafetyIssueSeverity.CRITICAL,
                "fresh authority notice is required for resource safety review",
                (request.operation_request_id,),
            )
        )
    if request.resource_target == "credential_or_secret":
        issues.append(
            ResourceSafetyIssue(
                ResourceSafetyIssueKind.CREDENTIAL_BOUNDARY_UNREVIEWED,
                ResourceSafetyIssueSeverity.CRITICAL,
                "credential references remain opaque and unreviewed",
                (request.operation_request_id,),
            )
        )
    if request.resource_target == "network_service" or request.intended_effect == "network_exposure_mutation":
        issues.append(
            ResourceSafetyIssue(
                ResourceSafetyIssueKind.NETWORK_BOUNDARY_UNREVIEWED,
                ResourceSafetyIssueSeverity.CRITICAL,
                "network exposure mutation is not authorized",
                (request.operation_request_id,),
            )
        )
    if (
        request.resource_target == "filesystem_destructive_target"
        or request.intended_effect == "destructive_filesystem_action"
    ):
        issues.append(
            ResourceSafetyIssue(
                ResourceSafetyIssueKind.DESTRUCTIVE_ACTION_POSSIBLE,
                ResourceSafetyIssueSeverity.CRITICAL,
                "destructive filesystem action is not authorized",
                (request.operation_request_id,),
            )
        )
    if classify_intended_effect(request.intended_effect).value == "blocked_live_effect":
        issues.append(
            ResourceSafetyIssue(
                ResourceSafetyIssueKind.LIVE_CONTROL_IMPLICATION,
                ResourceSafetyIssueSeverity.REFUSED,
                "live-control implication must be refused before execution paths exist",
                (request.operation_request_id,),
            )
        )
    if blast_radius is not None and blast_radius.blast_radius_state in {"unknown", "uncertain"}:
        issues.append(
            ResourceSafetyIssue(
                ResourceSafetyIssueKind.UNKNOWN_BLAST_RADIUS,
                ResourceSafetyIssueSeverity.CRITICAL,
                "uncertain blast radius requires review and blocks operation planning",
                (request.operation_request_id,),
            )
        )
    if request.blast_radius in {"unknown", "uncertain"}:
        issues.append(
            ResourceSafetyIssue(
                ResourceSafetyIssueKind.UNKNOWN_BLAST_RADIUS,
                ResourceSafetyIssueSeverity.CRITICAL,
                "request blast radius is unknown or uncertain",
                (request.operation_request_id,),
            )
        )
    return tuple(issues)


def _has_critical_boundary(request: OperationRequestEnvelope) -> bool:
    return (
        request.resource_target in CRITICAL_TARGET_SET
        or request.intended_effect in BLOCKED_LIVE_EFFECT_SET
        or "secret_value_present" in request.predicted_side_effect_set
    )


def _requires_human_review(
    request: OperationRequestEnvelope,
    blast_radius: BlastRadiusEnvelope | None,
) -> bool:
    risk = risk_level_for_request(request, blast_radius)
    return risk in {ResourceRiskLevel.HIGH, ResourceRiskLevel.CRITICAL, ResourceRiskLevel.UNKNOWN}


def _approval_issue(
    issue_kind: ResourceSafetyIssueKind,
    approval: HumanApprovalEnvelope,
    reason: str,
) -> ResourceSafetyIssue:
    return ResourceSafetyIssue(
        issue_kind,
        ResourceSafetyIssueSeverity.REFUSED,
        reason,
        (approval.human_approval_id,),
    )


def _safe_routes_for_issues(issues: Iterable[ResourceSafetyIssue]) -> tuple[str, ...]:
    routes: set[str] = set()
    for issue in issues:
        if issue.issue_kind in {
            ResourceSafetyIssueKind.MISSING_BLAST_RADIUS,
            ResourceSafetyIssueKind.UNKNOWN_BLAST_RADIUS,
        }:
            routes.add("collect_blast_radius_evidence")
        elif issue.issue_kind == ResourceSafetyIssueKind.MISSING_ROLLBACK_OR_ABORT_ROUTE:
            routes.add("define_rollback_abort_route")
        elif issue.issue_kind in {
            ResourceSafetyIssueKind.STALE_APPROVAL,
            ResourceSafetyIssueKind.REVOKED_APPROVAL,
            ResourceSafetyIssueKind.MISMATCHED_INTENDED_EFFECT,
            ResourceSafetyIssueKind.MISMATCHED_RESOURCE_TARGET,
            ResourceSafetyIssueKind.BROAD_STANDING_APPROVAL,
        }:
            routes.add("request_fresh_scoped_human_approval")
        elif issue.issue_kind in {
            ResourceSafetyIssueKind.MISSING_AUTHORITY_NOTICE,
            ResourceSafetyIssueKind.LIVE_CONTROL_IMPLICATION,
        }:
            routes.add("rebake_authority_boundary")
        else:
            routes.add("stop_without_live_effect")
    return tuple(sorted(routes))


def _field_has_value(record: object, field_name: str) -> bool:
    value = getattr(record, field_name)
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value)
    if isinstance(value, tuple):
        return bool(value)
    return True
