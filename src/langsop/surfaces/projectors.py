"""Pure IR5 surface projectors.

Projectors build validated projection records from explicit input data. They
do not read files, write generated output, call adapters, or mutate authority.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from .action_routes import ActionRouteDecision, classify_surface_action
from .authority import (
    AuthorityDisplayEnvelope,
    AuthorityDisplayValidationResult,
    AuthorityTier,
    authority_display_envelope_from_parts,
    validate_authority_display_envelope,
)
from .projection_state import (
    FreshnessState,
    ProjectionStateEnvelope,
    ProjectionStateValidationResult,
    ProjectionStatus,
    projected_status_for_evidence,
    projection_state_envelope_from_parts,
    validate_projection_state_envelope,
)


DEFAULT_AUTHORITY_NOTICE_REF = "authority_notice_ref"
DEFAULT_MUTATION_BOUNDARY_REF = "projection_only_no_source_mutation"


@dataclass(frozen=True)
class SurfaceProjectionPolicy:
    """Defaults used by first-pass IR5 surface projectors."""

    generated_at: str = "projection_time_unset"
    authority_notice_ref: str = DEFAULT_AUTHORITY_NOTICE_REF
    mutation_boundary_ref: str = DEFAULT_MUTATION_BOUNDARY_REF
    default_source_authority_ref_set: tuple[str, ...] = (
        "docs/surfaces/IR5_Authority_Display_And_Projection_State_Contract.v1.sop",
    )


@dataclass(frozen=True)
class SurfaceProjectionRecord:
    """A projection-only record with authority and state validation."""

    projection_kind: str
    projected_subject_ref: str
    authority_display: AuthorityDisplayEnvelope
    projection_state: ProjectionStateEnvelope
    authority_validation: AuthorityDisplayValidationResult
    state_validation: ProjectionStateValidationResult
    action_route_decision: ActionRouteDecision | None = None
    projection_payload: Mapping[str, object] = field(default_factory=dict)
    source_mutation_requested: bool = False

    @property
    def accepted(self) -> bool:
        action_accepted = self.action_route_decision is None or self.action_route_decision.accepted
        return (
            self.authority_validation.accepted
            and self.state_validation.accepted
            and action_accepted
            and not self.source_mutation_requested
        )


def project_manager_summary(
    input_packet: Mapping[str, object],
    projection_policy: SurfaceProjectionPolicy | None = None,
) -> SurfaceProjectionRecord:
    """Project a manager summary without assigning or dispatching work."""

    return _build_surface_projection(
        input_packet,
        projection_policy,
        projection_kind="manager_summary_projection",
        carrier_surface="manager_dashboard",
        authority_tier=AuthorityTier.SOURCE_AUTHORITY,
        trust_limit="accepted IR5 work state and completion reviews only",
        projected_status=ProjectionStatus.READY,
        freshness_state=FreshnessState.FRESH,
        permitted_action_set=("request_work_packet", "request_review"),
        forbidden_action_set=(
            "direct_agent_dispatch",
            "direct_completion_review_acceptance",
            "direct_source_authority_write",
        ),
        required_route_set=("completion_review_delta_gate",),
        payload_extra={"projection_family": "manager"},
    )


def project_worker_packet(
    input_packet: Mapping[str, object],
    projection_policy: SurfaceProjectionPolicy | None = None,
) -> SurfaceProjectionRecord:
    """Project a blocked worker packet with visible blocker evidence."""

    return _build_surface_projection(
        input_packet,
        projection_policy,
        projection_kind="worker_packet_projection",
        carrier_surface="worker_packet_surface",
        authority_tier=AuthorityTier.SOURCE_AUTHORITY,
        trust_limit="accepted work packet evidence only",
        projected_status=ProjectionStatus.BLOCKED,
        freshness_state=FreshnessState.BLOCKED,
        blocker_ref_set=_tuple_or_default(input_packet, "blocker_ref_set", ("unresolved_support_gap",)),
        permitted_action_set=("request_rebake", "request_interrupt_resolution"),
        forbidden_action_set=("completion_claim", "false_ready_display"),
        required_route_set=("support_repair_or_rebake",),
        payload_extra={"projection_family": "worker"},
    )


def project_stale_projection(
    input_packet: Mapping[str, object],
    projection_policy: SurfaceProjectionPolicy | None = None,
) -> SurfaceProjectionRecord:
    """Project stale evidence with refresh or rebake routes visible."""

    return _build_surface_projection(
        input_packet,
        projection_policy,
        projection_kind="stale_projection",
        carrier_surface="stale_projection_surface",
        authority_tier=AuthorityTier.GENERATED_PROJECTION_EVIDENCE,
        trust_limit="stale display evidence only",
        projected_status=ProjectionStatus.STALE,
        freshness_state=FreshnessState.STALE,
        stale_source_ref_set=_tuple_or_default(input_packet, "stale_source_ref_set", ("accepted_contract_hash_changed",)),
        invalidation_ref_set=_tuple_or_default(input_packet, "invalidation_ref_set", ("accepted_contract_hash_changed",)),
        permitted_action_set=("request_rebake",),
        forbidden_action_set=("authority_sensitive_action_without_refresh",),
        required_route_set=("refresh_accepted_input_or_rebake_affected_slice",),
        payload_extra={"projection_family": "stale"},
    )


def project_narrative(
    input_packet: Mapping[str, object],
    projection_policy: SurfaceProjectionPolicy | None = None,
) -> SurfaceProjectionRecord:
    """Project narrative lineage without rewriting source narrative."""

    return _build_surface_projection(
        input_packet,
        projection_policy,
        projection_kind="narrative_projection",
        carrier_surface="narrative_surface",
        authority_tier=AuthorityTier.SOURCE_AUTHORITY,
        trust_limit="accepted narrative and completion review refs only",
        projected_status=ProjectionStatus.READY,
        freshness_state=FreshnessState.FRESH,
        permitted_action_set=("request_review",),
        forbidden_action_set=("source_narrative_rewrite", "canonical_specification_rewrite"),
        required_route_set=("completion_review_delta_gate",),
        payload_extra={"projection_family": "narrative"},
    )


def project_debug_trace(
    input_packet: Mapping[str, object],
    projection_policy: SurfaceProjectionPolicy | None = None,
) -> SurfaceProjectionRecord:
    """Project debug trace evidence without promoting checkpoints."""

    return _build_surface_projection(
        input_packet,
        projection_policy,
        projection_kind="debug_trace_projection",
        carrier_surface="debug_surface",
        authority_tier=AuthorityTier.GENERATED_PROJECTION_EVIDENCE,
        trust_limit="debug evidence display only",
        projected_status=ProjectionStatus.FAULTED,
        freshness_state=FreshnessState.FAULTED,
        fault_record_ref_set=_tuple_or_default(input_packet, "fault_record_ref_set", ("hidden_write_evidence",)),
        permitted_action_set=("request_review",),
        forbidden_action_set=("fault_repair_from_projection", "checkpoint_authority_promotion"),
        required_route_set=("debug_review",),
        payload_extra={"projection_family": "debug"},
    )


def project_conversation(
    input_packet: Mapping[str, object],
    projection_policy: SurfaceProjectionPolicy | None = None,
) -> SurfaceProjectionRecord:
    """Project conversation context as carrier context only."""

    return _build_surface_projection(
        input_packet,
        projection_policy,
        projection_kind="conversation_projection",
        carrier_surface="conversation_surface",
        authority_tier=AuthorityTier.CARRIER_CONTEXT,
        trust_limit="preserved conversation context only",
        projected_status=ProjectionStatus.INTERRUPTED,
        freshness_state=FreshnessState.INTERRUPTED,
        interrupt_context_ref_set=_tuple_or_default(
            input_packet,
            "interrupt_context_ref_set",
            ("ambiguous_authority_sensitive_user_action",),
        ),
        permitted_action_set=("request_interrupt_resolution",),
        forbidden_action_set=("participant_identity_collapse", "direct_authority_mutation"),
        required_route_set=("SOP-first interrupt",),
        payload_extra={"projection_family": "conversation"},
    )


def project_adapter_event(
    input_packet: Mapping[str, object],
    projection_policy: SurfaceProjectionPolicy | None = None,
) -> SurfaceProjectionRecord:
    """Project adapter-originated events without accepting mutation."""

    return _build_surface_projection(
        input_packet,
        projection_policy,
        projection_kind="adapter_event_projection",
        carrier_surface="adapter_event_surface",
        authority_tier=AuthorityTier.CARRIER_CONTEXT,
        trust_limit="inbound carrier context only",
        projected_status=ProjectionStatus.BLOCKED,
        freshness_state=FreshnessState.BLOCKED,
        blocker_ref_set=_tuple_or_default(input_packet, "blocker_ref_set", ("mutation_gate_ref",)),
        permitted_action_set=("action_request", "coordination_request", "completion_review_request"),
        forbidden_action_set=(
            "direct_source_write",
            "direct_accepted_pack_write",
            "direct_agent_dispatch",
            "direct_command_execution",
            "operations_command",
        ),
        required_route_set=("action_route_display_contract",),
        payload_extra={"projection_family": "adapter"},
    )


def project_langflow_view(
    input_packet: Mapping[str, object],
    projection_policy: SurfaceProjectionPolicy | None = None,
) -> SurfaceProjectionRecord:
    """Project a Langflow-style view as explanatory projection only."""

    return _build_surface_projection(
        input_packet,
        projection_policy,
        projection_kind="langflow_graph_projection",
        carrier_surface="langflow_diagram_surface",
        authority_tier=AuthorityTier.GENERATED_PROJECTION_EVIDENCE,
        trust_limit="explanatory projection only",
        projected_status=ProjectionStatus.READY,
        freshness_state=FreshnessState.FRESH,
        permitted_action_set=("observe",),
        forbidden_action_set=("Langflow_installation", "Langflow_export_implementation", "runtime_execution"),
        required_route_set=("blocked_direct_execution_route",),
        payload_extra={"projection_family": "langflow", "explanatory_projection_only": True},
    )


def project_divergence_notice(
    input_packet: Mapping[str, object],
    projection_policy: SurfaceProjectionPolicy | None = None,
) -> SurfaceProjectionRecord:
    """Project multi-surface divergence as a stopped comparison notice."""

    return _build_surface_projection(
        input_packet,
        projection_policy,
        projection_kind="divergence_notice",
        carrier_surface="multi_surface_comparison",
        authority_tier=AuthorityTier.CARRIER_CONTEXT,
        trust_limit="divergent carrier evidence only",
        projected_status=ProjectionStatus.STALE,
        freshness_state=FreshnessState.STALE,
        stale_source_ref_set=_tuple_or_default(input_packet, "stale_source_ref_set", ("authority_notice_mismatch",)),
        invalidation_ref_set=_tuple_or_default(input_packet, "invalidation_ref_set", ("carrier_ordering_conflict",)),
        permitted_action_set=("request_interrupt_resolution", "request_rebake"),
        forbidden_action_set=("authority_sensitive_action_before_reconciliation",),
        required_route_set=("reconcile_source_freshness_claim_state_lineage_or_authority_notice",),
        payload_extra={"projection_family": "divergence"},
    )


def project_completion_gate_refusal(
    input_packet: Mapping[str, object],
    projection_policy: SurfaceProjectionPolicy | None = None,
) -> SurfaceProjectionRecord:
    """Project a completion gate refusal without opening the next gate."""

    return _build_surface_projection(
        input_packet,
        projection_policy,
        projection_kind="blocked_projection",
        carrier_surface="gate_projection_surface",
        authority_tier=AuthorityTier.GENERATED_PROJECTION_EVIDENCE,
        trust_limit="gate display only",
        projected_status=ProjectionStatus.BLOCKED,
        freshness_state=FreshnessState.BLOCKED,
        blocker_ref_set=_tuple_or_default(input_packet, "blocker_ref_set", ("completion_review_ref_missing",)),
        permitted_action_set=("request_completion_review",),
        forbidden_action_set=("open_IR5-IA03", "accept_completion_from_projection"),
        required_route_set=("accepted_completion_review_required",),
        payload_extra={"projection_family": "completion_gate"},
    )


def project_ir4_runtime_graph_proof_handoff(
    input_packet: Mapping[str, object],
    projection_policy: SurfaceProjectionPolicy | None = None,
) -> SurfaceProjectionRecord:
    """Project accepted IR4 runtime proof without promoting checkpoints."""

    return _build_surface_projection(
        input_packet,
        projection_policy,
        projection_kind="debug_trace_projection",
        carrier_surface="runtime_proof_handoff_surface",
        authority_tier=AuthorityTier.ACCEPTED_EXECUTION_EVIDENCE,
        trust_limit="accepted IR4 completion evidence only",
        projected_status=ProjectionStatus.READY,
        freshness_state=FreshnessState.FRESH,
        permitted_action_set=("request_review",),
        forbidden_action_set=("checkpoint_readiness_authority", "generated_trace_authority"),
        required_route_set=("completion_review_delta_gate",),
        payload_extra={"projection_family": "runtime_handoff", "checkpoint_display": "execution_state_only"},
    )


def project_operation_request(
    input_packet: Mapping[str, object],
    projection_policy: SurfaceProjectionPolicy | None = None,
) -> SurfaceProjectionRecord:
    """Project an operation-like request as non-live and blocked."""

    return _build_surface_projection(
        input_packet,
        projection_policy,
        projection_kind="operation_projection",
        carrier_surface="operations_preview_surface",
        authority_tier=AuthorityTier.GENERATED_PROJECTION_EVIDENCE,
        trust_limit="non-live dry-run evidence only",
        projected_status=ProjectionStatus.BLOCKED,
        freshness_state=FreshnessState.BLOCKED,
        blocker_ref_set=_tuple_or_default(input_packet, "blocker_ref_set", ("live_control_not_authorized",)),
        permitted_action_set=("request_completion_review",),
        forbidden_action_set=(
            "command_execution",
            "process_control",
            "gpu_control",
            "job_dispatch",
            "operations_control",
            "live_machine_control",
        ),
        required_route_set=("completion_review_required",),
        payload_extra={
            "projection_family": "operation",
            "dry_run_display": "non_live_simulation_only",
            "live_machine_control_authorized": False,
        },
    )


def _build_surface_projection(
    input_packet: Mapping[str, object],
    projection_policy: SurfaceProjectionPolicy | None,
    *,
    projection_kind: str,
    carrier_surface: str,
    authority_tier: AuthorityTier,
    trust_limit: str,
    projected_status: ProjectionStatus,
    freshness_state: FreshnessState,
    permitted_action_set: tuple[str, ...],
    forbidden_action_set: tuple[str, ...],
    required_route_set: tuple[str, ...],
    blocker_ref_set: tuple[str, ...] = (),
    stale_source_ref_set: tuple[str, ...] = (),
    fault_record_ref_set: tuple[str, ...] = (),
    interrupt_context_ref_set: tuple[str, ...] = (),
    invalidation_ref_set: tuple[str, ...] = (),
    contested_claim_ref_set: tuple[str, ...] = (),
    pending_review_ref_set: tuple[str, ...] = (),
    refusal_reason_set: tuple[str, ...] = (),
    payload_extra: Mapping[str, object] | None = None,
) -> SurfaceProjectionRecord:
    policy = projection_policy or SurfaceProjectionPolicy()
    projected_subject_ref = str(input_packet.get("projected_subject_ref", input_packet.get("fixture_case", projection_kind)))
    source_authority_ref_set = _tuple_or_default(
        input_packet,
        "source_authority_ref_set",
        policy.default_source_authority_ref_set,
    )
    source_record_ref_set = _tuple_or_default(input_packet, "source_record_ref_set", source_authority_ref_set)
    lineage_edge_set = _tuple_or_default(input_packet, "lineage_edge_set", (f"{projected_subject_ref}->{projection_kind}",))
    projection_id = str(input_packet.get("projection_id", f"{projection_kind}:{projected_subject_ref}"))
    display_projection_id = str(input_packet.get("display_projection_id", projection_id))
    resolved_status = projected_status_for_evidence(
        blocker_ref_set=blocker_ref_set,
        stale_source_ref_set=stale_source_ref_set,
        fault_record_ref_set=fault_record_ref_set,
        interrupt_context_ref_set=interrupt_context_ref_set,
        contested_claim_ref_set=contested_claim_ref_set,
        pending_review_ref_set=pending_review_ref_set,
        refusal_reason_set=refusal_reason_set,
    )
    if resolved_status == ProjectionStatus.READY:
        resolved_status = projected_status

    authority_display = authority_display_envelope_from_parts(
        display_projection_id=display_projection_id,
        projected_subject_ref=projected_subject_ref,
        carrier_surface=carrier_surface,
        authority_tier=authority_tier,
        trust_limit=trust_limit,
        source_authority_ref_set=source_authority_ref_set,
        derived_from_ref_set=_tuple_or_default(input_packet, "derived_from_ref_set", ()),
        authority_notice_ref=str(input_packet.get("authority_notice_ref", policy.authority_notice_ref)),
        freshness_state=freshness_state.value,
        risk_reason=str(input_packet.get("risk_reason", projection_kind)),
        permitted_action_set=permitted_action_set,
        forbidden_action_set=forbidden_action_set,
        required_route_set=required_route_set,
        mutation_boundary_ref=policy.mutation_boundary_ref,
        source_authority_mutation_requested=_as_bool(input_packet.get("source_authority_mutation_requested", False)),
    )
    projection_state = projection_state_envelope_from_parts(
        projection_id=projection_id,
        projection_kind=projection_kind,
        projected_subject_ref=projected_subject_ref,
        source_record_ref_set=source_record_ref_set,
        lineage_edge_set=lineage_edge_set,
        generated_at=str(input_packet.get("generated_at", policy.generated_at)),
        projected_status=resolved_status,
        freshness_state=freshness_state,
        invalidation_ref_set=invalidation_ref_set,
        blocker_ref_set=blocker_ref_set,
        stale_source_ref_set=stale_source_ref_set,
        fault_record_ref_set=fault_record_ref_set,
        interrupt_context_ref_set=interrupt_context_ref_set,
        contested_claim_ref_set=contested_claim_ref_set,
        pending_review_ref_set=pending_review_ref_set,
        supported_action_route_set=permitted_action_set,
        refusal_reason_set=refusal_reason_set,
        authority_notice_ref=authority_display.authority_notice_ref,
        generated_projection_claimed_as_authority=_as_bool(
            input_packet.get("generated_projection_claimed_as_authority", False)
        ),
        source_authority_mutation_requested=authority_display.source_authority_mutation_requested,
    )
    action_route_decision = None
    requested_action = str(input_packet.get("requested_action", ""))
    if requested_action:
        action_route_decision = classify_surface_action(
            {
                "action_id": str(input_packet.get("action_id", f"{projection_id}:action")),
                "action_kind": requested_action,
                "projected_subject_ref": projected_subject_ref,
                "authority_notice_ref": authority_display.authority_notice_ref,
                "freshness_state": projection_state.freshness_state.value,
                "supported_action_route_set": projection_state.supported_action_route_set,
                "required_route_set": authority_display.required_route_set,
                "forbidden_action_set": authority_display.forbidden_action_set,
                "stop_state_ref_set": _stop_state_ref_set(projection_state),
                "interrupt_context_ref_set": projection_state.interrupt_context_ref_set,
                "direct_mutation_requested": authority_display.source_authority_mutation_requested,
                "live_control_requested": _as_bool(input_packet.get("live_control_requested", False)),
            }
        )
    payload = {
        "carrier_surface": carrier_surface,
        "authority_tier": authority_tier.value,
        "trust_limit": trust_limit,
        "source_mutation_requested": authority_display.source_authority_mutation_requested,
    }
    if payload_extra:
        payload.update(payload_extra)
    return SurfaceProjectionRecord(
        projection_kind=projection_kind,
        projected_subject_ref=projected_subject_ref,
        authority_display=authority_display,
        projection_state=projection_state,
        authority_validation=validate_authority_display_envelope(authority_display),
        state_validation=validate_projection_state_envelope(projection_state),
        action_route_decision=action_route_decision,
        projection_payload=payload,
        source_mutation_requested=authority_display.source_authority_mutation_requested,
    )


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


def _stop_state_ref_set(state: ProjectionStateEnvelope) -> tuple[str, ...]:
    return (
        state.invalidation_ref_set
        + state.blocker_ref_set
        + state.stale_source_ref_set
        + state.fault_record_ref_set
        + state.contested_claim_ref_set
        + state.pending_review_ref_set
        + state.refusal_reason_set
    )


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes"}
    return bool(value)
