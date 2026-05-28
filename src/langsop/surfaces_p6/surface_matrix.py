"""P6 multi-surface projection matrix.

This module projects surface records from explicit inputs only. It does not
read or write files, call adapters, create UI, dispatch work, or control live
machine state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .envelope import (
    DEFAULT_MUTATION_BOUNDARY_REF,
    NON_AUTHORITY_WARNING,
    P6AuthorityTier,
    P6FreshnessState,
    P6ProjectionEnvelope,
    P6ProjectionStatus,
    P6ProjectionValidationResult,
    P6SurfaceFamily,
    p6_projection_envelope_from_parts,
    validate_p6_projection_envelope,
)
from .nonpromotion import evaluate_p6_nonpromotion_fields


COMMON_FORBIDDEN_EFFECT_SET: tuple[str, ...] = (
    "direct_source_write",
    "direct_canonical_write",
    "direct_claim_activation",
    "direct_completion_acceptance",
    "direct_assignment",
    "direct_dispatch",
    "direct_command_execution",
    "direct_operations_control",
    "direct_live_machine_control",
)


@dataclass(frozen=True)
class P6SurfaceCapability:
    """Declared capability boundary for one surface family."""

    surface_family: P6SurfaceFamily
    carrier_surface: str
    may_show_set: tuple[str, ...]
    may_request_set: tuple[str, ...]
    forbidden_effect_set: tuple[str, ...]
    required_route_set: tuple[str, ...]
    compact_rendering_supported: bool = True
    carrier_context_only: bool = False
    langflow_execution_blocked: bool = False


@dataclass(frozen=True)
class P6SurfaceProjectionResult:
    """Projection result with validation and capability evidence."""

    envelope: P6ProjectionEnvelope
    capability: P6SurfaceCapability
    validation: P6ProjectionValidationResult
    projection_payload: Mapping[str, object]

    @property
    def accepted(self) -> bool:
        return self.validation.accepted


SURFACE_CAPABILITY_MAP: dict[P6SurfaceFamily, P6SurfaceCapability] = {
    P6SurfaceFamily.MANAGER: P6SurfaceCapability(
        P6SurfaceFamily.MANAGER,
        "manager_surface",
        (
            "current_ready_slice_or_chunk",
            "blocked_item_set",
            "stale_item_set",
            "contested_claim_set",
            "fault_item_set",
            "pending_review_set",
            "support_delta_set",
            "requirement_delta_set",
        ),
        ("packet_proposal", "review_request", "rebake_request"),
        COMMON_FORBIDDEN_EFFECT_SET,
        ("completion_review_delta_gate", "manager_review"),
    ),
    P6SurfaceFamily.WORKER: P6SurfaceCapability(
        P6SurfaceFamily.WORKER,
        "worker_surface",
        (
            "accepted_input_ref_set",
            "expected_output_ref_set",
            "forbidden_scope_set",
            "verification_oracle_summary",
            "model_route",
            "completion_review_required",
        ),
        ("claim_request", "scope_question", "completion_review_request"),
        COMMON_FORBIDDEN_EFFECT_SET + ("claim_acceptance", "scope_expansion"),
        ("completion_review_required", "scope_review"),
    ),
    P6SurfaceFamily.NARRATIVE: P6SurfaceCapability(
        P6SurfaceFamily.NARRATIVE,
        "narrative_surface",
        (
            "narrative_summary",
            "source_lineage_ref_set",
            "open_frontier_set",
            "blocked_or_stale_context_set",
            "reentry_packet_ref_set",
        ),
        ("reentry_packet_request", "source_reconsideration_request"),
        COMMON_FORBIDDEN_EFFECT_SET + ("source_narrative_rewrite", "canonical_specification_rewrite"),
        ("project_narrative_review", "source_reconsideration_route"),
    ),
    P6SurfaceFamily.DEBUG: P6SurfaceCapability(
        P6SurfaceFamily.DEBUG,
        "debug_surface",
        (
            "trace_path_summary",
            "checkpoint_context_ref_set",
            "fault_summary_set",
            "hidden_write_check_summary",
            "unresolved_debug_question_set",
        ),
        ("fault_review_request", "trace_review_request"),
        COMMON_FORBIDDEN_EFFECT_SET + ("fault_repair", "checkpoint_authority_promotion"),
        ("debug_review", "completion_review_required"),
    ),
    P6SurfaceFamily.CHAT: P6SurfaceCapability(
        P6SurfaceFamily.CHAT,
        "chat_surface",
        ("conversation_lineage_ref_set", "visible_authority_notice", "visible_freshness_state"),
        ("observation", "comment", "proposal", "work_request", "review_request"),
        COMMON_FORBIDDEN_EFFECT_SET + ("transcript_as_source_authority",),
        ("surface_action_classification",),
        carrier_context_only=True,
    ),
    P6SurfaceFamily.CODEX: P6SurfaceCapability(
        P6SurfaceFamily.CODEX,
        "Codex_thread_surface",
        ("thread_context_ref", "visible_authority_notice", "visible_freshness_state"),
        ("observation", "comment", "proposal", "work_request", "review_request"),
        COMMON_FORBIDDEN_EFFECT_SET + ("Codex_thread_state_as_authority",),
        ("surface_action_classification",),
        carrier_context_only=True,
    ),
    P6SurfaceFamily.TERMINAL: P6SurfaceCapability(
        P6SurfaceFamily.TERMINAL,
        "terminal_surface",
        ("terminal_output_projection", "visible_authority_notice", "visible_freshness_state"),
        ("observation", "comment", "proposal"),
        COMMON_FORBIDDEN_EFFECT_SET + ("terminal_output_as_authority",),
        ("surface_action_classification",),
        carrier_context_only=True,
    ),
    P6SurfaceFamily.IRC: P6SurfaceCapability(
        P6SurfaceFamily.IRC,
        "IRC_channel_surface",
        ("channel_context_ref", "participant_ref_set", "visible_authority_notice"),
        ("observation", "comment", "proposal", "work_request", "claim_request", "review_request"),
        COMMON_FORBIDDEN_EFFECT_SET + ("IRC_event_as_authority",),
        ("surface_action_classification", "coordination_review"),
        carrier_context_only=True,
    ),
    P6SurfaceFamily.MATRIX: P6SurfaceCapability(
        P6SurfaceFamily.MATRIX,
        "Matrix_room_surface",
        ("room_context_ref", "participant_ref_set", "visible_authority_notice"),
        ("observation", "comment", "proposal", "work_request", "claim_request", "review_request"),
        COMMON_FORBIDDEN_EFFECT_SET + ("Matrix_event_as_authority",),
        ("surface_action_classification", "coordination_review"),
        carrier_context_only=True,
    ),
    P6SurfaceFamily.WEB: P6SurfaceCapability(
        P6SurfaceFamily.WEB,
        "web_surface",
        ("web_state_projection", "visible_authority_notice", "visible_freshness_state"),
        ("observation", "comment", "proposal", "work_request", "review_request"),
        COMMON_FORBIDDEN_EFFECT_SET + ("web_UI_state_as_authority",),
        ("surface_action_classification",),
        carrier_context_only=True,
    ),
    P6SurfaceFamily.LANGFLOW: P6SurfaceCapability(
        P6SurfaceFamily.LANGFLOW,
        "Langflow_diagram_surface",
        ("explanatory_graph_projection", "authority_notice", "freshness_state", "blocked_direct_execution_route"),
        ("diagram_review_request", "export_reconsideration_request"),
        COMMON_FORBIDDEN_EFFECT_SET + ("Langflow_flow_execution", "Langflow_node_success_to_completion_acceptance"),
        ("blocked_direct_execution_route", "surface_action_classification"),
        carrier_context_only=True,
        langflow_execution_blocked=True,
    ),
}


def surface_capability_for(surface_family: str | P6SurfaceFamily) -> P6SurfaceCapability:
    """Return the accepted capability boundary for a P6 surface family."""

    return SURFACE_CAPABILITY_MAP[P6SurfaceFamily(surface_family)]


def project_p6_surface(
    input_packet: Mapping[str, object],
    *,
    surface_family: str | P6SurfaceFamily | None = None,
) -> P6SurfaceProjectionResult:
    """Project one P6 surface envelope from explicit input data."""

    family = P6SurfaceFamily(surface_family or input_packet.get("surface_family", input_packet.get("surface_kind", "chat")))
    capability = surface_capability_for(family)
    nonpromotion_fields = dict(_sequence_map(input_packet))
    nonpromotion_fields.setdefault("projection_record_kind", ("surface_snapshot",))
    nonpromotion_fields.setdefault("required_notice", (NON_AUTHORITY_WARNING,))
    nonpromotion = evaluate_p6_nonpromotion_fields(nonpromotion_fields)
    freshness_state = _freshness_state(input_packet)
    status = _projection_status(input_packet, freshness_state, bool(nonpromotion.issue_kind))
    authority_tier = _authority_tier(input_packet, capability)
    subject = str(input_packet.get("projected_subject_ref", input_packet.get("fixture_case", family.value)))
    envelope = p6_projection_envelope_from_parts(
        projection_id=str(input_packet.get("projection_id", f"p6:{family.value}:{subject}")),
        projection_uuid=str(input_packet.get("projection_uuid", input_packet.get("projection_id", subject))),
        projection_kind=str(input_packet.get("projection_kind", f"{family.value}_projection")),
        surface_family=family,
        carrier_surface=str(input_packet.get("carrier_surface", capability.carrier_surface)),
        projected_subject_ref=subject,
        source_record_ref_set=_tuple_or_default(input_packet, "source_record_ref_set", _default_source_refs(input_packet)),
        source_authority_sha256_set=_tuple_or_default(
            input_packet,
            "source_authority_sha256_set",
            _default_source_hashes(input_packet),
        ),
        lineage_edge_set=_tuple_or_default(input_packet, "lineage_edge_set", (f"{subject}->{family.value}",)),
        authority_notice_ref=str(input_packet.get("authority_notice_ref", input_packet.get("required_notice", ""))),
        authority_tier=authority_tier,
        freshness_state=freshness_state,
        projected_status=status,
        nonpromotion_notice_set=(NON_AUTHORITY_WARNING,),
        forbidden_action_set=capability.forbidden_effect_set,
        required_route_set=capability.required_route_set,
        generated_at=str(input_packet.get("generated_at", "projection_time_unset")),
        permitted_action_set=capability.may_request_set,
        stop_state_ref_set=_stop_state_refs(input_packet, status, nonpromotion.issue_kind.value if nonpromotion.issue_kind else ""),
        stale_trigger_set=_tuple_or_default(input_packet, "stale_trigger_set", ()),
        invalidation_ref_set=_tuple_or_default(input_packet, "invalidation_ref_set", ()),
        carrier_context_ref=str(input_packet.get("carrier_context_ref", capability.carrier_surface)),
        risk_reason=str(input_packet.get("risk_reason", "P6 surface projection boundary")),
        lower_authority_tier_claimed_as_source=bool(nonpromotion.issue_kind),
        source_authority_mutation_requested=_source_mutation_requested(input_packet),
        assignment_requested=_bool(input_packet.get("assignment_requested", False)),
        dispatch_requested=_bool(input_packet.get("dispatch_authority", input_packet.get("dispatch_requested", False))),
        operations_control_requested=_bool(input_packet.get("operations_control_requested", False)),
        live_control_requested=_bool(input_packet.get("live_control_requested", input_packet.get("live_effect", False))),
    )
    validation = validate_p6_projection_envelope(envelope)
    return P6SurfaceProjectionResult(
        envelope=envelope,
        capability=capability,
        validation=validation,
        projection_payload={
            "surface_family": family.value,
            "carrier_surface": capability.carrier_surface,
            "carrier_context_only": capability.carrier_context_only,
            "langflow_execution_blocked": capability.langflow_execution_blocked,
            "nonpromotion_state": nonpromotion.state.value,
            "nonpromotion_issue_kind": nonpromotion.issue_kind.value if nonpromotion.issue_kind else "",
        },
    )


def _authority_tier(
    input_packet: Mapping[str, object],
    capability: P6SurfaceCapability,
) -> P6AuthorityTier:
    if "authority_tier" in input_packet:
        return P6AuthorityTier(str(input_packet["authority_tier"]))
    if capability.carrier_context_only:
        return P6AuthorityTier.CARRIER_CONTEXT
    if str(input_packet.get("source_authority_state", "")) in {"accepted", "accepted_and_fresh"}:
        return P6AuthorityTier.SOURCE_AUTHORITY
    return P6AuthorityTier.GENERATED_PROJECTION_EVIDENCE


def _freshness_state(input_packet: Mapping[str, object]) -> P6FreshnessState:
    value = str(input_packet.get("freshness_state", "unknown"))
    return P6FreshnessState({"current": "fresh", "accepted": "fresh", "present": "fresh"}.get(value, value))


def _projection_status(
    input_packet: Mapping[str, object],
    freshness_state: P6FreshnessState,
    nonpromotion_issue: bool,
) -> P6ProjectionStatus:
    if "projected_status" in input_packet:
        return P6ProjectionStatus(str(input_packet["projected_status"]))
    if nonpromotion_issue:
        return P6ProjectionStatus.FAULTED
    if _source_mutation_requested(input_packet):
        return P6ProjectionStatus.REFUSED
    if freshness_state == P6FreshnessState.STALE:
        return P6ProjectionStatus.STALE
    if freshness_state == P6FreshnessState.FAULTED:
        return P6ProjectionStatus.FAULTED
    if freshness_state == P6FreshnessState.INTERRUPTED:
        return P6ProjectionStatus.INTERRUPTED
    if freshness_state == P6FreshnessState.FRESH:
        return P6ProjectionStatus.READY
    return P6ProjectionStatus.BLOCKED


def _stop_state_refs(
    input_packet: Mapping[str, object],
    status: P6ProjectionStatus,
    nonpromotion_issue: str,
) -> tuple[str, ...]:
    explicit = _tuple_or_default(input_packet, "stop_state_ref_set", ())
    if explicit:
        return explicit
    if nonpromotion_issue:
        return (nonpromotion_issue,)
    if status in {P6ProjectionStatus.READY}:
        return ()
    return (status.value,)


def _source_mutation_requested(input_packet: Mapping[str, object]) -> bool:
    action = str(input_packet.get("inbound_action_kind", input_packet.get("requested_action_kind", "")))
    return _bool(input_packet.get("source_authority_mutation_requested", False)) or action in {
        "edit_canonical_source",
        "direct_source_write",
        "direct_canonical_write",
    }


def _default_source_refs(input_packet: Mapping[str, object]) -> tuple[str, ...]:
    ref = str(input_packet.get("source_ref", "docs/surfaces/P6_Authority_Notice_Freshness_And_Nonpromotion_Rendering_Contract.v1.sop"))
    return (ref,)


def _default_source_hashes(input_packet: Mapping[str, object]) -> tuple[str, ...]:
    value = input_packet.get("source_authority_sha256", "hash_pending_review")
    return (str(value),)


def _tuple_or_default(
    data: Mapping[str, object],
    field_name: str,
    default: tuple[str, ...],
) -> tuple[str, ...]:
    value = data.get(field_name, default)
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,) if value else ()
    return tuple(str(item) for item in value)  # type: ignore[operator]


def _sequence_map(data: Mapping[str, object]) -> Mapping[str, Sequence[str]]:
    return {str(key): _tuple_or_default(data, str(key), ()) for key in data}


def _bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1"}
    return bool(value)


__all__ = (
    "COMMON_FORBIDDEN_EFFECT_SET",
    "SURFACE_CAPABILITY_MAP",
    "P6SurfaceCapability",
    "P6SurfaceProjectionResult",
    "project_p6_surface",
    "surface_capability_for",
)
