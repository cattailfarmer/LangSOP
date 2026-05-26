"""Action route classification for IR5 surface projections.

This module produces route decisions only. It does not accept claims, open
gates, dispatch work, execute commands, or control operations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Mapping

from .authority import (
    AUTHORITY_SENSITIVE_ACTION_SET,
    DIRECT_MUTATION_ACTION_SET,
    LOW_AUTHORITY_ACTION_SET,
)


class ActionRouteDecisionStatus(str, Enum):
    """Accepted surface action decision classes."""

    ALLOWED = "allowed"
    BLOCKED = "blocked"
    REFUSED = "refused"
    INTERRUPT = "interrupt"


class ActionRouteIssueKind(str, Enum):
    """Issue vocabulary for action route classification."""

    MISSING_ACTION = "missing_action"
    MISSING_AUTHORITY_NOTICE = "missing_authority_notice"
    STALE_OR_STOPPED_PROJECTION = "stale_or_stopped_projection"
    UNSUPPORTED_ACTION_ROUTE = "unsupported_action_route"
    DIRECT_MUTATION_REQUESTED = "direct_mutation_requested"
    LIVE_CONTROL_REQUESTED = "live_control_requested"


class ActionRouteIssueSeverity(str, Enum):
    """How a route issue should be treated by a surface."""

    BLOCKED = "blocked"
    REFUSED = "refused"
    INTERRUPT = "interrupt"


LIVE_CONTROL_ACTION_SET: frozenset[str] = frozenset(
    {
        "command_execution",
        "credential_mutation",
        "destructive_filesystem_action",
        "gpu_control",
        "job_dispatch",
        "model_runtime_mutation",
        "network_mutation",
        "operations_automation",
        "operations_command",
        "operations_control",
        "process_control",
        "live_machine_control",
    }
)


@dataclass(frozen=True)
class ActionRouteIssue:
    """One blocked, refused, or interrupt reason for an action route."""

    issue_kind: ActionRouteIssueKind
    severity: ActionRouteIssueSeverity
    reason: str
    field_name: str | None = None


@dataclass(frozen=True)
class SurfaceActionPacket:
    """Decision-facing action request from a projection surface."""

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
    live_control_requested: bool = False


@dataclass(frozen=True)
class ActionRoutePolicy:
    """Policy vocabulary for classifying surface action requests."""

    low_authority_action_set: frozenset[str] = field(default_factory=lambda: LOW_AUTHORITY_ACTION_SET)
    authority_sensitive_action_set: frozenset[str] = field(
        default_factory=lambda: AUTHORITY_SENSITIVE_ACTION_SET
    )
    direct_mutation_action_set: frozenset[str] = field(default_factory=lambda: DIRECT_MUTATION_ACTION_SET)
    live_control_action_set: frozenset[str] = field(default_factory=lambda: LIVE_CONTROL_ACTION_SET)
    fresh_state: str = "fresh"


@dataclass(frozen=True)
class ActionRouteDecision:
    """Projection-only route decision for a surface action."""

    action_id: str
    action_kind: str
    decision_status: ActionRouteDecisionStatus
    allowed_route_set: tuple[str, ...] = ()
    blocked_route_set: tuple[str, ...] = ()
    refusal_reason_set: tuple[str, ...] = ()
    interrupt_context_ref_set: tuple[str, ...] = ()
    issue_set: tuple[ActionRouteIssue, ...] = ()
    authority_notice_ref: str = ""
    mutation_boundary_ref: str = "projection_only_no_source_mutation"

    @property
    def accepted(self) -> bool:
        return self.decision_status == ActionRouteDecisionStatus.ALLOWED


def surface_action_packet_from_mapping(data: Mapping[str, object]) -> SurfaceActionPacket:
    """Build a surface action packet from mapping data."""

    return SurfaceActionPacket(
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
        live_control_requested=_as_bool(data.get("live_control_requested", False)),
    )


def classify_surface_action(
    action_packet: SurfaceActionPacket | Mapping[str, object],
    projection_policy: ActionRoutePolicy | None = None,
) -> ActionRouteDecision:
    """Classify a surface action without mutating authority or runtime state."""

    packet = (
        action_packet
        if isinstance(action_packet, SurfaceActionPacket)
        else surface_action_packet_from_mapping(action_packet)
    )
    policy = projection_policy or ActionRoutePolicy()
    issues: list[ActionRouteIssue] = []

    if not packet.action_kind:
        issues.append(
            ActionRouteIssue(
                ActionRouteIssueKind.MISSING_ACTION,
                ActionRouteIssueSeverity.BLOCKED,
                "action kind is required",
                "action_kind",
            )
        )

    if not packet.authority_notice_ref:
        issues.append(
            ActionRouteIssue(
                ActionRouteIssueKind.MISSING_AUTHORITY_NOTICE,
                ActionRouteIssueSeverity.REFUSED,
                "authority notice is required before action classification",
                "authority_notice_ref",
            )
        )

    if packet.action_kind in policy.direct_mutation_action_set or packet.direct_mutation_requested:
        issues.append(
            ActionRouteIssue(
                ActionRouteIssueKind.DIRECT_MUTATION_REQUESTED,
                ActionRouteIssueSeverity.REFUSED,
                "surface actions may not directly mutate source authority",
                "action_kind",
            )
        )

    if packet.action_kind in policy.live_control_action_set or packet.live_control_requested:
        issues.append(
            ActionRouteIssue(
                ActionRouteIssueKind.LIVE_CONTROL_REQUESTED,
                ActionRouteIssueSeverity.REFUSED,
                "surface actions may not authorize live control",
                "action_kind",
            )
        )

    if _is_stopped_or_stale(packet, policy) and packet.action_kind not in {
        "request_rebake",
        "request_interrupt_resolution",
        "request_completion_review",
    }:
        issues.append(
            ActionRouteIssue(
                ActionRouteIssueKind.STALE_OR_STOPPED_PROJECTION,
                _stopped_or_stale_severity(packet),
                "stale, blocked, faulted, interrupted, or pending projection state must be resolved first",
                "freshness_state",
            )
        )

    if _is_unsupported_authority_sensitive_action(packet, policy):
        issues.append(
            ActionRouteIssue(
                ActionRouteIssueKind.UNSUPPORTED_ACTION_ROUTE,
                ActionRouteIssueSeverity.BLOCKED,
                "authority-sensitive action is not supported by this projection route set",
                "action_kind",
            )
        )

    decision_status = _decision_status_for_issues(issues, packet)
    return ActionRouteDecision(
        action_id=packet.action_id,
        action_kind=packet.action_kind,
        decision_status=decision_status,
        allowed_route_set=_allowed_route_set(packet, policy, decision_status),
        blocked_route_set=tuple(sorted(set(packet.forbidden_action_set) | (policy.direct_mutation_action_set & {packet.action_kind}))),
        refusal_reason_set=tuple(issue.issue_kind.value for issue in issues if issue.severity == ActionRouteIssueSeverity.REFUSED),
        interrupt_context_ref_set=packet.interrupt_context_ref_set,
        issue_set=tuple(issues),
        authority_notice_ref=packet.authority_notice_ref,
    )


def _is_stopped_or_stale(packet: SurfaceActionPacket, policy: ActionRoutePolicy) -> bool:
    return bool(packet.stop_state_ref_set or packet.interrupt_context_ref_set or packet.freshness_state != policy.fresh_state)


def _is_unsupported_authority_sensitive_action(
    packet: SurfaceActionPacket,
    policy: ActionRoutePolicy,
) -> bool:
    if packet.action_kind not in policy.authority_sensitive_action_set:
        return False
    supported = set(packet.supported_action_route_set)
    required = set(packet.required_route_set)
    return packet.action_kind not in supported and packet.action_kind not in required


def _stopped_or_stale_severity(packet: SurfaceActionPacket) -> ActionRouteIssueSeverity:
    if packet.interrupt_context_ref_set or packet.freshness_state == "interrupted":
        return ActionRouteIssueSeverity.INTERRUPT
    return ActionRouteIssueSeverity.BLOCKED


def _decision_status_for_issues(
    issues: Iterable[ActionRouteIssue],
    packet: SurfaceActionPacket,
) -> ActionRouteDecisionStatus:
    issue_tuple = tuple(issues)
    if any(issue.severity == ActionRouteIssueSeverity.REFUSED for issue in issue_tuple):
        return ActionRouteDecisionStatus.REFUSED
    if any(issue.severity == ActionRouteIssueSeverity.INTERRUPT for issue in issue_tuple):
        return ActionRouteDecisionStatus.INTERRUPT
    if any(issue.severity == ActionRouteIssueSeverity.BLOCKED for issue in issue_tuple):
        return ActionRouteDecisionStatus.BLOCKED
    if not packet.authority_notice_ref:
        return ActionRouteDecisionStatus.REFUSED
    return ActionRouteDecisionStatus.ALLOWED


def _allowed_route_set(
    packet: SurfaceActionPacket,
    policy: ActionRoutePolicy,
    decision_status: ActionRouteDecisionStatus,
) -> tuple[str, ...]:
    if decision_status != ActionRouteDecisionStatus.ALLOWED:
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
