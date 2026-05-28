"""P6 inbound surface action classification.

Action classification creates request, refusal, interrupt, or review evidence
only. It does not mutate source authority, accept claims, dispatch work,
execute commands, operate resources, or authorize live machine control.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Mapping

from .envelope import P6FreshnessState, P6SurfaceFamily


LOW_AUTHORITY_ACTION_SET: frozenset[str] = frozenset(
    {"observation", "comment", "clarification", "proposal"}
)
AUTHORITY_SENSITIVE_ACTION_SET: frozenset[str] = frozenset(
    {
        "work_request",
        "claim_request",
        "review_request",
        "rebake_request",
        "interrupt_resolution_request",
        "human_override_request",
    }
)
OPERATION_LIKE_ACTION_SET: frozenset[str] = frozenset({"dry_run_request", "operation_request"})
FORBIDDEN_ACTION_SET: frozenset[str] = frozenset(
    {
        "edit_canonical_source",
        "direct_source_write",
        "direct_canonical_write",
        "direct_claim_activation",
        "direct_completion_acceptance",
        "direct_assignment",
        "direct_dispatch",
        "direct_command_execution",
        "direct_operations_control",
        "direct_live_machine_control",
        "command_execution",
        "process_control",
        "gpu_control",
        "model_runtime_mutation",
        "job_dispatch",
        "credential_access",
        "network_mutation",
        "destructive_filesystem_action",
        "operations_control",
        "live_machine_control",
    }
)


class P6InboundActionClassification(str, Enum):
    """Accepted P6 inbound action classifications."""

    LOW_AUTHORITY_CONTEXT = "low_authority_context"
    PROPOSAL_RECORD_REQUIRED = "proposal_record_required"
    WORK_REQUEST_RECORD_REQUIRED = "work_request_record_required"
    COORDINATION_REVIEW_REQUIRED = "coordination_review_required"
    COMPLETION_REVIEW_REQUIRED = "completion_review_required"
    SOP_FIRST_INTERRUPT_REQUIRED = "SOP_first_interrupt_required"
    HUMAN_OVERRIDE_REVIEW_REQUIRED = "human_override_review_required"
    DRY_RUN_OR_SAFETY_REVIEW_REQUIRED = "dry_run_or_safety_review_required"
    REFUSED = "refused"


class P6InboundActionIssueKind(str, Enum):
    """Issue vocabulary for inbound action classification."""

    MISSING_ACTION = "missing_action"
    MISSING_ACTOR = "missing_actor"
    MISSING_CARRIER = "missing_carrier"
    MISSING_AUTHORITY_NOTICE = "missing_authority_notice"
    STALE_OR_STOPPED_PROJECTION = "stale_or_stopped_projection"
    UNSUPPORTED_ACTION = "unsupported_action"
    DIRECT_MUTATION_REQUESTED = "direct_mutation_requested"
    ASSIGNMENT_REQUESTED = "assignment_requested"
    DISPATCH_REQUESTED = "dispatch_requested"
    OPERATIONS_CONTROL_REQUESTED = "operations_control_requested"
    LIVE_CONTROL_REQUESTED = "live_control_requested"


class P6InboundActionIssueSeverity(str, Enum):
    """How P6 should treat an inbound action issue."""

    BLOCKED = "blocked"
    INTERRUPT = "interrupt"
    REFUSED = "refused"


@dataclass(frozen=True)
class P6InboundActionIssue:
    """One blocked, interrupted, or refused classification reason."""

    issue_kind: P6InboundActionIssueKind
    severity: P6InboundActionIssueSeverity
    reason: str
    field_name: str | None = None


@dataclass(frozen=True)
class P6InboundActionPacket:
    """Decision-facing inbound action request from a P6 surface."""

    inbound_action_id: str
    inbound_action_uuid: str
    carrier_surface: str
    surface_family: P6SurfaceFamily
    actor_ref: str
    conversation_ref: str
    source_message_or_event_ref: str
    projected_subject_ref: str
    requested_action_kind: str
    requested_effect_class: str
    claimed_authority_basis_ref_set: tuple[str, ...]
    authority_notice_seen: bool
    freshness_state_seen: P6FreshnessState
    projection_ref: str
    mutation_boundary_ref: str
    evidence_ref_set: tuple[str, ...] = ()
    stop_state_ref_set: tuple[str, ...] = ()
    direct_mutation_requested: bool = False
    assignment_requested: bool = False
    dispatch_requested: bool = False
    operations_control_requested: bool = False
    live_control_requested: bool = False


@dataclass(frozen=True)
class P6InboundActionClassificationResult:
    """Pure classification result for one inbound surface action."""

    packet: P6InboundActionPacket
    classification: P6InboundActionClassification
    required_route_set: tuple[str, ...]
    forbidden_effect_set: tuple[str, ...]
    issue_set: tuple[P6InboundActionIssue, ...] = ()
    authority_mutation_authorized: bool = False
    assignment_authorized: bool = False
    dispatch_authorized: bool = False
    operations_control_authorized: bool = False
    live_control_authorized: bool = False

    @property
    def accepted(self) -> bool:
        return not self.issue_set and self.classification != P6InboundActionClassification.REFUSED


def p6_inbound_action_packet_from_mapping(data: Mapping[str, object]) -> P6InboundActionPacket:
    """Build a P6 inbound action packet from mapping data."""

    action_id = str(data.get("inbound_action_id", data.get("action_id", "")))
    return P6InboundActionPacket(
        inbound_action_id=action_id,
        inbound_action_uuid=str(data.get("inbound_action_uuid", action_id)),
        carrier_surface=str(data.get("carrier_surface", data.get("surface_kind", ""))),
        surface_family=P6SurfaceFamily(str(data.get("surface_family", data.get("surface_kind", "chat")))),
        actor_ref=str(data.get("actor_ref", data.get("requested_by", ""))),
        conversation_ref=str(data.get("conversation_ref", "")),
        source_message_or_event_ref=str(data.get("source_message_or_event_ref", "")),
        projected_subject_ref=str(data.get("projected_subject_ref", data.get("fixture_case", ""))),
        requested_action_kind=str(data.get("requested_action_kind", data.get("inbound_action_kind", ""))),
        requested_effect_class=str(data.get("requested_effect_class", "")),
        claimed_authority_basis_ref_set=_as_string_sequence(data.get("claimed_authority_basis_ref_set", ())),
        authority_notice_seen=_as_bool(data.get("authority_notice_seen", data.get("required_notice", ""))),
        freshness_state_seen=_freshness_state(data.get("freshness_state_seen", data.get("freshness_state", "unknown"))),
        projection_ref=str(data.get("projection_ref", "")),
        mutation_boundary_ref=str(data.get("mutation_boundary_ref", "projection_only_no_source_mutation")),
        evidence_ref_set=_as_string_sequence(data.get("evidence_ref_set", ())),
        stop_state_ref_set=_as_string_sequence(data.get("stop_state_ref_set", ())),
        direct_mutation_requested=_as_bool(data.get("direct_mutation_requested", False)),
        assignment_requested=_as_bool(data.get("assignment_requested", False)),
        dispatch_requested=_as_bool(data.get("dispatch_requested", data.get("dispatch_authority", False))),
        operations_control_requested=_as_bool(data.get("operations_control_requested", False)),
        live_control_requested=_as_bool(data.get("live_control_requested", False)),
    )


def classify_p6_inbound_action(
    action_packet: P6InboundActionPacket | Mapping[str, object],
) -> P6InboundActionClassificationResult:
    """Classify a P6 inbound action without mutating authority or effects."""

    packet = (
        action_packet
        if isinstance(action_packet, P6InboundActionPacket)
        else p6_inbound_action_packet_from_mapping(action_packet)
    )
    issues = list(_identity_issues(packet))
    action_kind = packet.requested_action_kind

    if action_kind in FORBIDDEN_ACTION_SET or packet.direct_mutation_requested:
        issues.append(_refusal_issue(P6InboundActionIssueKind.DIRECT_MUTATION_REQUESTED, "direct mutation"))
    if packet.assignment_requested or action_kind == "direct_assignment":
        issues.append(_refusal_issue(P6InboundActionIssueKind.ASSIGNMENT_REQUESTED, "assignment"))
    if packet.dispatch_requested or action_kind in {"direct_dispatch", "job_dispatch"}:
        issues.append(_refusal_issue(P6InboundActionIssueKind.DISPATCH_REQUESTED, "dispatch"))
    if packet.operations_control_requested or action_kind in {"direct_operations_control", "operations_control"}:
        issues.append(_refusal_issue(P6InboundActionIssueKind.OPERATIONS_CONTROL_REQUESTED, "operations control"))
    if packet.live_control_requested or action_kind in {"direct_live_machine_control", "live_machine_control"}:
        issues.append(_refusal_issue(P6InboundActionIssueKind.LIVE_CONTROL_REQUESTED, "live machine control"))

    if _stale_or_stopped(packet) and action_kind not in {"rebake_request", "interrupt_resolution_request"}:
        issues.append(
            P6InboundActionIssue(
                P6InboundActionIssueKind.STALE_OR_STOPPED_PROJECTION,
                P6InboundActionIssueSeverity.INTERRUPT,
                "stale or stopped projections require rebake or interrupt resolution first",
                "freshness_state_seen",
            )
        )

    classification = _classification_for_action(action_kind, tuple(issues))
    return P6InboundActionClassificationResult(
        packet=packet,
        classification=classification,
        required_route_set=_required_routes_for_classification(classification),
        forbidden_effect_set=tuple(sorted(FORBIDDEN_ACTION_SET)),
        issue_set=tuple(issues),
    )


def p6_inbound_action_fact_set(result: P6InboundActionClassificationResult) -> frozenset[str]:
    """Return reviewable facts for future fixture comparison."""

    facts = {
        f"classification_result is {result.classification.value}",
        f"accepted is {_bool_text(result.accepted)}",
        f"authority_mutation_authorized is {_bool_text(result.authority_mutation_authorized)}",
        f"assignment_authorized is {_bool_text(result.assignment_authorized)}",
        f"dispatch_authorized is {_bool_text(result.dispatch_authorized)}",
        f"operations_control_authorized is {_bool_text(result.operations_control_authorized)}",
        f"live_control_authorized is {_bool_text(result.live_control_authorized)}",
    }
    for issue in result.issue_set:
        facts.add(f"issue_kind is {issue.issue_kind.value}")
        facts.add(f"issue_severity is {issue.severity.value}")
    return frozenset(facts)


def _identity_issues(packet: P6InboundActionPacket) -> tuple[P6InboundActionIssue, ...]:
    issues: list[P6InboundActionIssue] = []
    if not packet.requested_action_kind:
        issues.append(_blocked_issue(P6InboundActionIssueKind.MISSING_ACTION, "requested_action_kind"))
    if not packet.actor_ref:
        issues.append(_blocked_issue(P6InboundActionIssueKind.MISSING_ACTOR, "actor_ref"))
    if not packet.carrier_surface:
        issues.append(_blocked_issue(P6InboundActionIssueKind.MISSING_CARRIER, "carrier_surface"))
    if not packet.authority_notice_seen:
        issues.append(_blocked_issue(P6InboundActionIssueKind.MISSING_AUTHORITY_NOTICE, "authority_notice_seen"))
    return tuple(issues)


def _classification_for_action(
    action_kind: str,
    issues: tuple[P6InboundActionIssue, ...],
) -> P6InboundActionClassification:
    if any(issue.severity == P6InboundActionIssueSeverity.REFUSED for issue in issues):
        return P6InboundActionClassification.REFUSED
    if any(issue.severity == P6InboundActionIssueSeverity.INTERRUPT for issue in issues):
        return P6InboundActionClassification.SOP_FIRST_INTERRUPT_REQUIRED
    if action_kind in LOW_AUTHORITY_ACTION_SET:
        return P6InboundActionClassification.LOW_AUTHORITY_CONTEXT
    if action_kind == "proposal":
        return P6InboundActionClassification.PROPOSAL_RECORD_REQUIRED
    if action_kind == "work_request":
        return P6InboundActionClassification.WORK_REQUEST_RECORD_REQUIRED
    if action_kind == "claim_request":
        return P6InboundActionClassification.COORDINATION_REVIEW_REQUIRED
    if action_kind in {"review_request", "rebake_request"}:
        return P6InboundActionClassification.COMPLETION_REVIEW_REQUIRED
    if action_kind in {"interrupt_resolution_request"}:
        return P6InboundActionClassification.SOP_FIRST_INTERRUPT_REQUIRED
    if action_kind == "human_override_request":
        return P6InboundActionClassification.HUMAN_OVERRIDE_REVIEW_REQUIRED
    if action_kind in OPERATION_LIKE_ACTION_SET:
        return P6InboundActionClassification.DRY_RUN_OR_SAFETY_REVIEW_REQUIRED
    return P6InboundActionClassification.SOP_FIRST_INTERRUPT_REQUIRED


def _required_routes_for_classification(classification: P6InboundActionClassification) -> tuple[str, ...]:
    return {
        P6InboundActionClassification.LOW_AUTHORITY_CONTEXT: ("carrier_context_record",),
        P6InboundActionClassification.PROPOSAL_RECORD_REQUIRED: ("proposal_record",),
        P6InboundActionClassification.WORK_REQUEST_RECORD_REQUIRED: ("work_packet_generation_or_manager_review",),
        P6InboundActionClassification.COORDINATION_REVIEW_REQUIRED: ("coordination_review",),
        P6InboundActionClassification.COMPLETION_REVIEW_REQUIRED: ("completion_review_delta_gate",),
        P6InboundActionClassification.SOP_FIRST_INTERRUPT_REQUIRED: ("SOP_first_interrupt",),
        P6InboundActionClassification.HUMAN_OVERRIDE_REVIEW_REQUIRED: ("scoped_human_override_review",),
        P6InboundActionClassification.DRY_RUN_OR_SAFETY_REVIEW_REQUIRED: ("dry_run_or_resource_safety_review",),
        P6InboundActionClassification.REFUSED: ("refused_action_record",),
    }[classification]


def _stale_or_stopped(packet: P6InboundActionPacket) -> bool:
    return bool(packet.stop_state_ref_set or packet.freshness_state_seen != P6FreshnessState.FRESH)


def _blocked_issue(issue_kind: P6InboundActionIssueKind, field_name: str) -> P6InboundActionIssue:
    return P6InboundActionIssue(
        issue_kind,
        P6InboundActionIssueSeverity.BLOCKED,
        f"{field_name} is required before inbound action classification",
        field_name,
    )


def _refusal_issue(issue_kind: P6InboundActionIssueKind, effect_name: str) -> P6InboundActionIssue:
    return P6InboundActionIssue(
        issue_kind,
        P6InboundActionIssueSeverity.REFUSED,
        f"{effect_name} is not authorized by P6 surface action classification",
    )


def _freshness_state(value: object) -> P6FreshnessState:
    text = str(value)
    return P6FreshnessState({"current": "fresh", "accepted": "fresh", "present": "fresh"}.get(text, text))


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
        if not value:
            return False
        return value.strip().lower() not in {"false", "no", "0", "missing"}
    return bool(value)


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


__all__ = (
    "AUTHORITY_SENSITIVE_ACTION_SET",
    "FORBIDDEN_ACTION_SET",
    "LOW_AUTHORITY_ACTION_SET",
    "OPERATION_LIKE_ACTION_SET",
    "P6InboundActionClassification",
    "P6InboundActionClassificationResult",
    "P6InboundActionIssue",
    "P6InboundActionIssueKind",
    "P6InboundActionIssueSeverity",
    "P6InboundActionPacket",
    "classify_p6_inbound_action",
    "p6_inbound_action_fact_set",
    "p6_inbound_action_packet_from_mapping",
)
