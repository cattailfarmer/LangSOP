"""Action route classification for IR7 operation planning.

Action route decisions here are projection-only. They do not dispatch jobs,
start processes, control GPUs, access credentials, mutate networks, or perform
destructive filesystem actions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Mapping

from .requests import BLOCKED_LIVE_EFFECT_SET, SAFE_DRY_RUN_EFFECT_SET
from .resource_safety import ResourceRiskLevel


class OperationActionDecisionStatus(str, Enum):
    """Accepted operation action decision statuses."""

    ALLOWED = "allowed"
    BLOCKED = "blocked"
    REFUSED = "refused"
    INTERRUPT = "interrupt"
    REVIEW_REQUIRED = "review_required"


class OperationActionIssueKind(str, Enum):
    """Issue vocabulary for operation action classification."""

    MISSING_ACTION = "missing_action"
    MISSING_AUTHORITY_NOTICE = "missing_authority_notice"
    STALE_OR_STOPPED_REQUEST = "stale_or_stopped_request"
    UNSUPPORTED_ACTION_ROUTE = "unsupported_action_route"
    LIVE_CONTROL_REQUESTED = "live_control_requested"
    CREDENTIAL_ACCESS_REQUESTED = "credential_access_requested"
    NETWORK_MUTATION_REQUESTED = "network_mutation_requested"
    DESTRUCTIVE_ACTION_REQUESTED = "destructive_action_requested"
    HIGH_RISK_REVIEW_REQUIRED = "high_risk_review_required"
    AUTHORITY_PROMOTION_REQUESTED = "authority_promotion_requested"


class OperationActionIssueSeverity(str, Enum):
    """How an operation action issue should be treated."""

    BLOCKED = "blocked"
    REFUSED = "refused"
    INTERRUPT = "interrupt"
    REVIEW_REQUIRED = "review_required"


LOW_AUTHORITY_REVIEW_ACTION_SET: frozenset[str] = frozenset(
    {
        "request_completion_review",
        "request_human_review",
        "request_resource_safety_review",
        "request_sop_first_interrupt",
        "request_rebake",
        "refresh_authority_notice",
    }
)

CREDENTIAL_ACTION_SET: frozenset[str] = frozenset(
    {"credential_access_or_mutation", "credential_mutation", "reveal_secret", "mutate_secret"}
)
NETWORK_ACTION_SET: frozenset[str] = frozenset({"network_exposure_mutation", "network_mutation", "open_listener"})
DESTRUCTIVE_ACTION_SET: frozenset[str] = frozenset({"destructive_filesystem_action", "delete_path", "format_disk"})


@dataclass(frozen=True)
class OperationActionIssue:
    """One action route blocker, refusal, interrupt, or review requirement."""

    issue_kind: OperationActionIssueKind
    severity: OperationActionIssueSeverity
    reason: str
    field_name: str | None = None


@dataclass(frozen=True)
class OperationActionPacket:
    """Decision-facing operation action request from a projection surface."""

    action_id: str
    action_kind: str
    operation_request_ref: str
    authority_notice_ref: str
    freshness_state: str
    resource_target: str
    risk_classification: str
    supported_action_route_set: tuple[str, ...] = ()
    required_route_set: tuple[str, ...] = ()
    forbidden_action_set: tuple[str, ...] = ()
    stop_state_ref_set: tuple[str, ...] = ()
    interrupt_context_ref_set: tuple[str, ...] = ()
    live_control_requested: bool = False
    credential_access_requested: bool = False
    network_mutation_requested: bool = False
    destructive_action_requested: bool = False
    authority_promotion_requested: bool = False


@dataclass(frozen=True)
class OperationActionPolicy:
    """Policy vocabulary for operation action classification."""

    safe_dry_run_action_set: frozenset[str] = field(default_factory=lambda: SAFE_DRY_RUN_EFFECT_SET)
    low_authority_review_action_set: frozenset[str] = field(default_factory=lambda: LOW_AUTHORITY_REVIEW_ACTION_SET)
    live_control_action_set: frozenset[str] = field(default_factory=lambda: BLOCKED_LIVE_EFFECT_SET)
    credential_action_set: frozenset[str] = field(default_factory=lambda: CREDENTIAL_ACTION_SET)
    network_action_set: frozenset[str] = field(default_factory=lambda: NETWORK_ACTION_SET)
    destructive_action_set: frozenset[str] = field(default_factory=lambda: DESTRUCTIVE_ACTION_SET)
    fresh_state: str = "fresh"


@dataclass(frozen=True)
class OperationActionDecision:
    """Projection-only action decision for operation planning."""

    action_id: str
    action_kind: str
    decision_status: OperationActionDecisionStatus
    allowed_route_set: tuple[str, ...] = ()
    blocked_route_set: tuple[str, ...] = ()
    refusal_reason_set: tuple[str, ...] = ()
    review_route_set: tuple[str, ...] = ()
    interrupt_context_ref_set: tuple[str, ...] = ()
    issue_set: tuple[OperationActionIssue, ...] = ()
    authority_notice_ref: str = ""
    mutation_boundary_ref: str = "operation_projection_only_no_live_effect"

    @property
    def accepted(self) -> bool:
        return self.decision_status == OperationActionDecisionStatus.ALLOWED


def operation_action_packet_from_mapping(data: Mapping[str, object]) -> OperationActionPacket:
    """Build an action packet from mapping data."""

    return OperationActionPacket(
        action_id=str(data.get("action_id", "")),
        action_kind=str(data.get("action_kind", "")),
        operation_request_ref=str(data.get("operation_request_ref", "")),
        authority_notice_ref=str(data.get("authority_notice_ref", "")),
        freshness_state=str(data.get("freshness_state", "unknown")),
        resource_target=str(data.get("resource_target", "unknown_or_ambiguous")),
        risk_classification=str(data.get("risk_classification", "unknown")),
        supported_action_route_set=_as_string_sequence(data.get("supported_action_route_set", ())),
        required_route_set=_as_string_sequence(data.get("required_route_set", ())),
        forbidden_action_set=_as_string_sequence(data.get("forbidden_action_set", ())),
        stop_state_ref_set=_as_string_sequence(data.get("stop_state_ref_set", ())),
        interrupt_context_ref_set=_as_string_sequence(data.get("interrupt_context_ref_set", ())),
        live_control_requested=_as_bool(data.get("live_control_requested", False)),
        credential_access_requested=_as_bool(data.get("credential_access_requested", False)),
        network_mutation_requested=_as_bool(data.get("network_mutation_requested", False)),
        destructive_action_requested=_as_bool(data.get("destructive_action_requested", False)),
        authority_promotion_requested=_as_bool(data.get("authority_promotion_requested", False)),
    )


def classify_operation_action(
    action_packet: OperationActionPacket | Mapping[str, object],
    policy: OperationActionPolicy | None = None,
) -> OperationActionDecision:
    """Classify an operation action without opening a live-effect path."""

    packet = (
        action_packet if isinstance(action_packet, OperationActionPacket) else operation_action_packet_from_mapping(action_packet)
    )
    active_policy = policy or OperationActionPolicy()
    issues: list[OperationActionIssue] = []

    if not packet.action_kind:
        issues.append(
            OperationActionIssue(
                OperationActionIssueKind.MISSING_ACTION,
                OperationActionIssueSeverity.BLOCKED,
                "action kind is required",
                "action_kind",
            )
        )

    if not packet.authority_notice_ref:
        issues.append(
            OperationActionIssue(
                OperationActionIssueKind.MISSING_AUTHORITY_NOTICE,
                OperationActionIssueSeverity.REFUSED,
                "authority notice is required before action classification",
                "authority_notice_ref",
            )
        )

    if _is_stopped_or_stale(packet, active_policy):
        issues.append(
            OperationActionIssue(
                OperationActionIssueKind.STALE_OR_STOPPED_REQUEST,
                _stopped_or_stale_severity(packet),
                "stale, blocked, faulted, interrupted, or pending request state must be resolved first",
                "freshness_state",
            )
        )

    if packet.action_kind in active_policy.live_control_action_set or packet.live_control_requested:
        issues.append(
            OperationActionIssue(
                OperationActionIssueKind.LIVE_CONTROL_REQUESTED,
                OperationActionIssueSeverity.REFUSED,
                "operation actions may not authorize live control",
                "action_kind",
            )
        )

    if packet.action_kind in active_policy.credential_action_set or packet.credential_access_requested:
        issues.append(
            OperationActionIssue(
                OperationActionIssueKind.CREDENTIAL_ACCESS_REQUESTED,
                OperationActionIssueSeverity.REFUSED,
                "credential access is not authorized by IR7 operation projection",
                "action_kind",
            )
        )

    if packet.action_kind in active_policy.network_action_set or packet.network_mutation_requested:
        issues.append(
            OperationActionIssue(
                OperationActionIssueKind.NETWORK_MUTATION_REQUESTED,
                OperationActionIssueSeverity.REFUSED,
                "network mutation is not authorized by IR7 operation projection",
                "action_kind",
            )
        )

    if packet.action_kind in active_policy.destructive_action_set or packet.destructive_action_requested:
        issues.append(
            OperationActionIssue(
                OperationActionIssueKind.DESTRUCTIVE_ACTION_REQUESTED,
                OperationActionIssueSeverity.REFUSED,
                "destructive filesystem action is not authorized by IR7 operation projection",
                "action_kind",
            )
        )

    if packet.authority_promotion_requested:
        issues.append(
            OperationActionIssue(
                OperationActionIssueKind.AUTHORITY_PROMOTION_REQUESTED,
                OperationActionIssueSeverity.REFUSED,
                "operation action records may not promote projections to authority",
                "authority_promotion_requested",
            )
        )

    if _requires_resource_review(packet) and packet.action_kind not in active_policy.low_authority_review_action_set:
        issues.append(
            OperationActionIssue(
                OperationActionIssueKind.HIGH_RISK_REVIEW_REQUIRED,
                OperationActionIssueSeverity.REVIEW_REQUIRED,
                "high or critical risk operation actions require resource safety review first",
                "risk_classification",
            )
        )

    if _is_unsupported_action(packet, active_policy):
        issues.append(
            OperationActionIssue(
                OperationActionIssueKind.UNSUPPORTED_ACTION_ROUTE,
                OperationActionIssueSeverity.BLOCKED,
                "action kind is not supported by this operation projection route set",
                "action_kind",
            )
        )

    decision_status = _decision_status_for_issues(issues, packet, active_policy)
    return OperationActionDecision(
        action_id=packet.action_id,
        action_kind=packet.action_kind,
        decision_status=decision_status,
        allowed_route_set=_allowed_route_set(packet, active_policy, decision_status),
        blocked_route_set=tuple(sorted(set(packet.forbidden_action_set) | _blocked_policy_actions(packet, active_policy))),
        refusal_reason_set=tuple(issue.issue_kind.value for issue in issues if issue.severity == OperationActionIssueSeverity.REFUSED),
        review_route_set=_review_routes_for_issues(issues),
        interrupt_context_ref_set=packet.interrupt_context_ref_set,
        issue_set=tuple(issues),
        authority_notice_ref=packet.authority_notice_ref,
    )


def _is_stopped_or_stale(packet: OperationActionPacket, policy: OperationActionPolicy) -> bool:
    return bool(packet.stop_state_ref_set or packet.interrupt_context_ref_set or packet.freshness_state != policy.fresh_state)


def _stopped_or_stale_severity(packet: OperationActionPacket) -> OperationActionIssueSeverity:
    if packet.interrupt_context_ref_set or packet.freshness_state == "interrupted":
        return OperationActionIssueSeverity.INTERRUPT
    return OperationActionIssueSeverity.BLOCKED


def _requires_resource_review(packet: OperationActionPacket) -> bool:
    return packet.risk_classification in {
        ResourceRiskLevel.HIGH.value,
        ResourceRiskLevel.CRITICAL.value,
        ResourceRiskLevel.UNKNOWN.value,
    }


def _is_unsupported_action(packet: OperationActionPacket, policy: OperationActionPolicy) -> bool:
    if packet.action_kind in policy.safe_dry_run_action_set:
        return False
    if packet.action_kind in policy.low_authority_review_action_set:
        return False
    if packet.action_kind in packet.supported_action_route_set:
        return False
    if packet.action_kind in packet.required_route_set:
        return False
    if packet.action_kind in packet.forbidden_action_set:
        return False
    return bool(packet.action_kind)


def _decision_status_for_issues(
    issues: Iterable[OperationActionIssue],
    packet: OperationActionPacket,
    policy: OperationActionPolicy,
) -> OperationActionDecisionStatus:
    issue_tuple = tuple(issues)
    if any(issue.severity == OperationActionIssueSeverity.REFUSED for issue in issue_tuple):
        return OperationActionDecisionStatus.REFUSED
    if any(issue.severity == OperationActionIssueSeverity.INTERRUPT for issue in issue_tuple):
        return OperationActionDecisionStatus.INTERRUPT
    if any(issue.severity == OperationActionIssueSeverity.REVIEW_REQUIRED for issue in issue_tuple):
        return OperationActionDecisionStatus.REVIEW_REQUIRED
    if any(issue.severity == OperationActionIssueSeverity.BLOCKED for issue in issue_tuple):
        return OperationActionDecisionStatus.BLOCKED
    if packet.action_kind in policy.safe_dry_run_action_set or packet.action_kind in policy.low_authority_review_action_set:
        return OperationActionDecisionStatus.ALLOWED
    return OperationActionDecisionStatus.BLOCKED


def _allowed_route_set(
    packet: OperationActionPacket,
    policy: OperationActionPolicy,
    decision_status: OperationActionDecisionStatus,
) -> tuple[str, ...]:
    if decision_status != OperationActionDecisionStatus.ALLOWED:
        return ()
    if packet.action_kind in policy.safe_dry_run_action_set:
        return (packet.action_kind,)
    if packet.action_kind in policy.low_authority_review_action_set:
        return (packet.action_kind,)
    if packet.action_kind in packet.supported_action_route_set:
        return (packet.action_kind,)
    if packet.action_kind in packet.required_route_set:
        return (packet.action_kind,)
    return ()


def _blocked_policy_actions(packet: OperationActionPacket, policy: OperationActionPolicy) -> set[str]:
    blocked: set[str] = set()
    for action_set in (
        policy.live_control_action_set,
        policy.credential_action_set,
        policy.network_action_set,
        policy.destructive_action_set,
    ):
        if packet.action_kind in action_set:
            blocked.add(packet.action_kind)
    return blocked


def _review_routes_for_issues(issues: Iterable[OperationActionIssue]) -> tuple[str, ...]:
    routes: set[str] = set()
    for issue in issues:
        if issue.issue_kind == OperationActionIssueKind.HIGH_RISK_REVIEW_REQUIRED:
            routes.add("request_resource_safety_review")
            routes.add("request_human_review")
        elif issue.issue_kind == OperationActionIssueKind.STALE_OR_STOPPED_REQUEST:
            routes.add("request_sop_first_interrupt")
        elif issue.issue_kind == OperationActionIssueKind.MISSING_AUTHORITY_NOTICE:
            routes.add("refresh_authority_notice")
    return tuple(sorted(routes))


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
