"""Action route classification for IR6 coordination projections."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Mapping

from .claims import (
    DISPATCH_ACTION_SET,
    DIRECT_SOURCE_MUTATION_ACTION_SET,
    LIVE_CONTROL_ACTION_SET,
    MAILBOX_IO_ACTION_SET,
)


class CoordinationActionDecisionStatus(str, Enum):
    """Accepted coordination action decision classes."""

    ALLOWED = "allowed"
    BLOCKED = "blocked"
    REFUSED = "refused"
    INTERRUPT = "interrupt"


class CoordinationActionIssueKind(str, Enum):
    """Issue vocabulary for coordination action classification."""

    MISSING_ACTION = "missing_action"
    MISSING_AUTHORITY_NOTICE = "missing_authority_notice"
    STOPPED_OR_STALE_PROJECTION = "stopped_or_stale_projection"
    UNSUPPORTED_ACTION_ROUTE = "unsupported_action_route"
    DIRECT_MUTATION_REQUESTED = "direct_mutation_requested"
    MAILBOX_IO_REQUESTED = "mailbox_io_requested"
    DISPATCH_REQUESTED = "agent_dispatch_requested"
    LIVE_CONTROL_REQUESTED = "live_control_requested"


class CoordinationActionIssueSeverity(str, Enum):
    """How a route issue should be treated."""

    BLOCKED = "blocked"
    REFUSED = "refused"
    INTERRUPT = "interrupt"


LOW_AUTHORITY_COORDINATION_ACTION_SET: frozenset[str] = frozenset({"observe", "comment", "propose"})
AUTHORITY_SENSITIVE_COORDINATION_ACTION_SET: frozenset[str] = frozenset(
    {
        "create_fixture_source",
        "create_expected_ledger",
        "request_claim",
        "release_claim",
        "supersede_claim",
        "refresh_claim",
        "request_review",
        "request_rebake",
        "request_human_override",
        "request_completion_review",
    }
)
RESOLUTION_ACTION_SET: frozenset[str] = frozenset(
    {"request_review", "request_rebake", "request_human_override", "request_completion_review"}
)


@dataclass(frozen=True)
class CoordinationActionIssue:
    """One blocked, refused, or interrupt reason."""

    issue_kind: CoordinationActionIssueKind
    severity: CoordinationActionIssueSeverity
    reason: str
    field_name: str | None = None


@dataclass(frozen=True)
class CoordinationActionPacket:
    """Decision-facing action request from a coordination projection."""

    action_id: str
    action_kind: str
    projected_subject_ref: str
    authority_notice_ref: str
    freshness_state: str
    supported_action_route_set: tuple[str, ...] = ()
    required_route_set: tuple[str, ...] = ()
    forbidden_action_set: tuple[str, ...] = ()
    stop_state_ref_set: tuple[str, ...] = ()
    interrupt_context_ref_set: tuple[str, ...] = ()
    direct_mutation_requested: bool = False
    mailbox_io_requested: bool = False
    dispatch_requested: bool = False
    live_control_requested: bool = False


@dataclass(frozen=True)
class CoordinationActionPolicy:
    """Policy vocabulary for classifying coordination action requests."""

    low_authority_action_set: frozenset[str] = LOW_AUTHORITY_COORDINATION_ACTION_SET
    authority_sensitive_action_set: frozenset[str] = AUTHORITY_SENSITIVE_COORDINATION_ACTION_SET
    resolution_action_set: frozenset[str] = RESOLUTION_ACTION_SET
    fresh_state: str = "fresh"


@dataclass(frozen=True)
class CoordinationActionDecision:
    """Projection-only route decision for a coordination action."""

    action_id: str
    action_kind: str
    decision_status: CoordinationActionDecisionStatus
    allowed_route_set: tuple[str, ...] = ()
    blocked_route_set: tuple[str, ...] = ()
    refusal_reason_set: tuple[str, ...] = ()
    interrupt_context_ref_set: tuple[str, ...] = ()
    issue_set: tuple[CoordinationActionIssue, ...] = ()
    authority_notice_ref: str = ""
    mutation_boundary_ref: str = "projection_only_no_source_or_mailbox_mutation"

    @property
    def accepted(self) -> bool:
        return self.decision_status == CoordinationActionDecisionStatus.ALLOWED


def coordination_action_packet_from_mapping(data: Mapping[str, object]) -> CoordinationActionPacket:
    """Build a coordination action packet from mapping data."""

    return CoordinationActionPacket(
        action_id=str(data.get("action_id", "")),
        action_kind=str(data.get("action_kind", "")),
        projected_subject_ref=str(data.get("projected_subject_ref", "")),
        authority_notice_ref=str(data.get("authority_notice_ref", "")),
        freshness_state=str(data.get("freshness_state", "unknown")),
        supported_action_route_set=tuple(_as_string_sequence(data.get("supported_action_route_set", ()))),
        required_route_set=tuple(_as_string_sequence(data.get("required_route_set", ()))),
        forbidden_action_set=tuple(_as_string_sequence(data.get("forbidden_action_set", ()))),
        stop_state_ref_set=tuple(_as_string_sequence(data.get("stop_state_ref_set", ()))),
        interrupt_context_ref_set=tuple(_as_string_sequence(data.get("interrupt_context_ref_set", ()))),
        direct_mutation_requested=_as_bool(data.get("direct_mutation_requested", False)),
        mailbox_io_requested=_as_bool(data.get("mailbox_io_requested", False)),
        dispatch_requested=_as_bool(data.get("dispatch_requested", False)),
        live_control_requested=_as_bool(data.get("live_control_requested", False)),
    )


def classify_coordination_action(
    action_packet: CoordinationActionPacket | Mapping[str, object],
    policy: CoordinationActionPolicy | None = None,
) -> CoordinationActionDecision:
    """Classify a coordination action without mutating authority or mailbox state."""

    packet = (
        action_packet
        if isinstance(action_packet, CoordinationActionPacket)
        else coordination_action_packet_from_mapping(action_packet)
    )
    route_policy = policy or CoordinationActionPolicy()
    issues: list[CoordinationActionIssue] = []

    if not packet.action_kind:
        issues.append(_issue(CoordinationActionIssueKind.MISSING_ACTION, CoordinationActionIssueSeverity.BLOCKED, "action kind is required", "action_kind"))
    if not packet.authority_notice_ref:
        issues.append(_issue(CoordinationActionIssueKind.MISSING_AUTHORITY_NOTICE, CoordinationActionIssueSeverity.REFUSED, "authority notice is required", "authority_notice_ref"))
    if packet.action_kind in DIRECT_SOURCE_MUTATION_ACTION_SET or packet.direct_mutation_requested:
        issues.append(_issue(CoordinationActionIssueKind.DIRECT_MUTATION_REQUESTED, CoordinationActionIssueSeverity.REFUSED, "coordination action may not mutate source authority", "action_kind"))
    if packet.action_kind in MAILBOX_IO_ACTION_SET or packet.mailbox_io_requested:
        issues.append(_issue(CoordinationActionIssueKind.MAILBOX_IO_REQUESTED, CoordinationActionIssueSeverity.REFUSED, "coordination action may not perform mailbox IO", "action_kind"))
    if packet.action_kind in DISPATCH_ACTION_SET or packet.dispatch_requested:
        issues.append(_issue(CoordinationActionIssueKind.DISPATCH_REQUESTED, CoordinationActionIssueSeverity.REFUSED, "coordination action may not dispatch agents", "action_kind"))
    if packet.action_kind in LIVE_CONTROL_ACTION_SET or packet.live_control_requested:
        issues.append(_issue(CoordinationActionIssueKind.LIVE_CONTROL_REQUESTED, CoordinationActionIssueSeverity.REFUSED, "coordination action may not control operations", "action_kind"))
    if _is_stopped_or_stale(packet, route_policy) and packet.action_kind not in route_policy.resolution_action_set:
        issues.append(_issue(CoordinationActionIssueKind.STOPPED_OR_STALE_PROJECTION, _stopped_or_stale_severity(packet), "stale, blocked, faulted, interrupted, or pending coordination state must be resolved first", "freshness_state"))
    if _is_unsupported_authority_sensitive_action(packet, route_policy):
        issues.append(_issue(CoordinationActionIssueKind.UNSUPPORTED_ACTION_ROUTE, CoordinationActionIssueSeverity.BLOCKED, "authority-sensitive action is not supported by this coordination route set", "action_kind"))

    decision_status = _decision_status_for_issues(issues, packet)
    return CoordinationActionDecision(
        action_id=packet.action_id,
        action_kind=packet.action_kind,
        decision_status=decision_status,
        allowed_route_set=_allowed_route_set(packet, route_policy, decision_status),
        blocked_route_set=tuple(sorted(set(packet.forbidden_action_set))),
        refusal_reason_set=tuple(issue.issue_kind.value for issue in issues if issue.severity == CoordinationActionIssueSeverity.REFUSED),
        interrupt_context_ref_set=packet.interrupt_context_ref_set,
        issue_set=tuple(issues),
        authority_notice_ref=packet.authority_notice_ref,
    )


def _issue(
    issue_kind: CoordinationActionIssueKind,
    severity: CoordinationActionIssueSeverity,
    reason: str,
    field_name: str | None = None,
) -> CoordinationActionIssue:
    return CoordinationActionIssue(issue_kind, severity, reason, field_name)


def _is_stopped_or_stale(packet: CoordinationActionPacket, policy: CoordinationActionPolicy) -> bool:
    return bool(packet.stop_state_ref_set or packet.interrupt_context_ref_set or packet.freshness_state != policy.fresh_state)


def _is_unsupported_authority_sensitive_action(
    packet: CoordinationActionPacket,
    policy: CoordinationActionPolicy,
) -> bool:
    if packet.action_kind not in policy.authority_sensitive_action_set:
        return False
    supported = set(packet.supported_action_route_set)
    required = set(packet.required_route_set)
    return packet.action_kind not in supported and packet.action_kind not in required


def _stopped_or_stale_severity(packet: CoordinationActionPacket) -> CoordinationActionIssueSeverity:
    if packet.interrupt_context_ref_set or packet.freshness_state == "interrupted":
        return CoordinationActionIssueSeverity.INTERRUPT
    return CoordinationActionIssueSeverity.BLOCKED


def _decision_status_for_issues(
    issues: Iterable[CoordinationActionIssue],
    packet: CoordinationActionPacket,
) -> CoordinationActionDecisionStatus:
    issue_tuple = tuple(issues)
    if any(issue.severity == CoordinationActionIssueSeverity.REFUSED for issue in issue_tuple):
        return CoordinationActionDecisionStatus.REFUSED
    if any(issue.severity == CoordinationActionIssueSeverity.INTERRUPT for issue in issue_tuple):
        return CoordinationActionDecisionStatus.INTERRUPT
    if any(issue.severity == CoordinationActionIssueSeverity.BLOCKED for issue in issue_tuple):
        return CoordinationActionDecisionStatus.BLOCKED
    if not packet.authority_notice_ref:
        return CoordinationActionDecisionStatus.REFUSED
    return CoordinationActionDecisionStatus.ALLOWED


def _allowed_route_set(
    packet: CoordinationActionPacket,
    policy: CoordinationActionPolicy,
    decision_status: CoordinationActionDecisionStatus,
) -> tuple[str, ...]:
    if decision_status != CoordinationActionDecisionStatus.ALLOWED:
        return ()
    if packet.action_kind in policy.low_authority_action_set:
        return (packet.action_kind,)
    if packet.action_kind in packet.supported_action_route_set:
        return (packet.action_kind,)
    if packet.action_kind in packet.required_route_set:
        return (packet.action_kind,)
    return ()


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
