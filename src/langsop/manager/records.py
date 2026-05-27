"""Core manager projection records for IR8 integrated orchestration.

These records are planning artifacts only. They do not dispatch agents, run
commands, control processes or GPUs, mutate model runtimes, access
credentials, change networks, or authorize live machine control.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Mapping


NO_DISPATCH_NOTICE = "manager_output_is_record_not_dispatch"
NO_LIVE_EFFECT_NOTICE = "manager_projection_has_no_live_effect"
SOP_INTERRUPT_NOTICE = "sop_first_interrupt_context_is_review_evidence_not_authority"


class ManagerAuthorityClass(str, Enum):
    """Authority classes accepted by the IR8 manager boundary."""

    SOURCE_AUTHORITY = "source_authority"
    MANAGER_PLANNING_RECORD = "manager_planning_record"
    ACCEPTED_EXECUTION_EVIDENCE = "accepted_execution_evidence"
    COORDINATION_RECORD = "coordination_record"
    OPERATIONS_DRY_RUN_RECORD = "operations_dry_run_record"
    GENERATED_PROJECTION = "generated_projection"
    GRAPH_CHECKPOINT = "graph_checkpoint"
    CARRIER_CONTEXT = "carrier_context"
    HUMAN_OVERRIDE_CONTEXT = "human_override_context"
    UNKNOWN = "unknown"


class ManagerFreshnessState(str, Enum):
    """Freshness vocabulary used by manager readiness recomputation."""

    FRESH = "fresh"
    STALE = "stale"
    UNKNOWN = "unknown"
    CONTESTED = "contested"
    BLOCKED = "blocked"
    INTERRUPTED = "interrupted"
    FAULTED = "faulted"
    PENDING_REVIEW = "pending_review"


class ManagerReadinessState(str, Enum):
    """Stable readiness projection vocabulary for work packet decisions."""

    READY_FOR_CLAIM = "ready_for_claim"
    BLOCKED_STALE = "blocked_stale"
    BLOCKED_UNSUPPORTED = "blocked_unsupported"
    INTERRUPTED_CONTESTED = "interrupted_contested"
    CONTEXT_RECORDED_NO_PROMOTION = "context_recorded_no_promotion"
    INTERRUPTED_UNCLASSIFIED = "interrupted_unclassified"
    EVIDENCE_RECORDED = "evidence_recorded"
    CONTEXTUAL_OVERRIDE_RECORDED = "contextual_override_recorded"
    SOURCE_AUTHORITY_REQUIRED = "source_authority_required"
    BLOCKED_UNTIL_KERNEL_REFERENCE_CHECKED = "blocked_until_kernel_reference_checked"
    REFUSED_FORBIDDEN_SCOPE = "refused_forbidden_scope"
    REFUSED_UNTIL_MODEL_ROUTE_DECLARED = "refused_until_model_route_declared"
    BLOCKED = "blocked"
    NOT_READY = "not_ready"


class ManagerWorkPacketState(str, Enum):
    """Projected work-packet candidate states."""

    READY_FOR_CLAIM = "ready_for_claim"
    NOT_READY = "not_ready"
    NOT_DISPATCHED = "not_dispatched"
    UNCHANGED_WITHOUT_SOURCE_AUTHORITY = "unchanged_without_source_authority"
    BOUNDED_BY_OVERRIDE_SCOPE = "bounded_by_override_scope"
    NOT_READY_FROM_PROJECTION_ALONE = "not_ready_from_projection_alone"
    NOT_READY_FROM_CHECKPOINT_ALONE = "not_ready_from_checkpoint_alone"


class ManagerModelRoute(str, Enum):
    """Model-route declarations required by manager work packets."""

    GPT_5_3_CODEX_SPARK_SUITABLE = "GPT-5.3-Codex-Spark-suitable"
    REQUIRES_DEEPER_REASONING = "requires deeper reasoning"
    MISSING = "missing"


class ManagerIssueKind(str, Enum):
    """Issue vocabulary for IR8 manager readiness and packet projection."""

    MISSING_FIELD = "missing_field"
    MISSING_SOURCE_AUTHORITY = "missing_source_authority"
    MISSING_AUTHORITY_NOTICE = "missing_authority_notice"
    STALE_BOUNDARY_INPUT = "stale_boundary_input"
    UNSUPPORTED_REQUIREMENT = "unsupported_requirement"
    CONTESTED_COORDINATION_CLAIM = "contested_coordination_claim"
    UNCLASSIFIED_AUTHORITY_SENSITIVE_RECORD = "unclassified_authority_sensitive_record"
    GENERATED_OUTPUT_AUTHORITY_PROMOTION = "generated_output_authority_promotion"
    GRAPH_CHECKPOINT_AUTHORITY_PROMOTION = "graph_checkpoint_authority_promotion"
    DRY_RUN_TO_LIVE_CONTROL_PROMOTION = "dry_run_to_live_control_promotion"
    HUMAN_OVERRIDE_REQUIRED = "human_override_required"
    REQUESTED_FORBIDDEN_SCOPE = "requested_forbidden_scope"
    MODEL_ROUTE_AMBIGUITY = "model_route_ambiguity"
    COMPLETION_GATE_BYPASS = "completion_gate_bypass"
    PROOF_OBLIGATION_BYPASS = "proof_obligation_bypass"
    DISPATCH_REQUESTED = "dispatch_requested"
    LIVE_EFFECT_REQUESTED = "live_effect_requested"


class ManagerIssueSeverity(str, Enum):
    """How manager projection should treat a detected issue."""

    BLOCKED = "blocked"
    STALE = "stale"
    FAULT = "fault"
    INTERRUPT = "interrupt"
    REFUSED = "refused"


@dataclass(frozen=True)
class ManagerIssue:
    """One blocked, stale, interrupt, fault, or refusal reason."""

    issue_kind: ManagerIssueKind
    severity: ManagerIssueSeverity
    reason: str
    field_name: str | None = None


@dataclass(frozen=True)
class ProofObligation:
    """Proof obligation attached to a manager work-packet candidate."""

    obligation_id: str
    required_evidence_ref_set: tuple[str, ...]
    satisfied: bool = False


@dataclass(frozen=True)
class CompletionGate:
    """Completion gate that keeps packet output tied to review evidence."""

    gate_id: str
    required_review_ref: str
    opened: bool = False


@dataclass(frozen=True)
class SOPFirstManagerInterruptContext:
    """Review context for stale, contested, ambiguous, or unsafe manager input."""

    interrupt_id: str
    interrupt_kind: ManagerIssueKind
    active_work_ref: str
    evidence_ref_set: tuple[str, ...]
    required_route_set: tuple[str, ...]
    non_authority_notice: str = SOP_INTERRUPT_NOTICE


@dataclass(frozen=True)
class ManagerCycleInput:
    """Input envelope for one pure manager readiness cycle."""

    cycle_id: str
    work_ref: str
    source_ref_set: tuple[str, ...]
    authority_notice_ref: str
    source_authority_state: str = "accepted_and_fresh"
    support_state: str = "complete"
    coordination_state: str = "uncontested"
    operations_dry_run_state: str = "not_required"
    carrier_context_kind: str = ""
    carrier_context_state: str = ""
    surface_kind: str = ""
    requested_effect_classification_state: str = "classified"
    requested_effect_kind: str = ""
    requested_promotion: str = ""
    live_authority_state: str = "missing"
    human_override_state: str = ""
    override_scope: str = ""
    risk_context_state: str = ""
    revocation_route_state: str = ""
    generated_projection_state: str = ""
    graph_checkpoint_state: str = ""
    kernel_reference_state: str = "present"
    model_route: ManagerModelRoute = ManagerModelRoute.REQUIRES_DEEPER_REASONING
    model_route_state: str = "declared"
    completion_review_ref: str = ""
    proof_obligation_ref_set: tuple[str, ...] = ()
    freshness_state: ManagerFreshnessState = ManagerFreshnessState.FRESH
    authority_class: ManagerAuthorityClass = ManagerAuthorityClass.MANAGER_PLANNING_RECORD


@dataclass(frozen=True)
class ManagerReadinessResult:
    """Pure readiness projection for one manager cycle."""

    accepted: bool
    readiness_state: ManagerReadinessState
    work_packet_state: ManagerWorkPacketState
    issues: tuple[ManagerIssue, ...] = ()
    proof_obligation_set: tuple[ProofObligation, ...] = ()
    completion_gate: CompletionGate | None = None
    interrupt_context: SOPFirstManagerInterruptContext | None = None
    authority_notice_set: tuple[str, ...] = ()
    dispatch_authorized: bool = False
    live_effect_performed: bool = False
    non_authority_notice: str = NO_DISPATCH_NOTICE

    @property
    def has_fault(self) -> bool:
        return any(issue.severity == ManagerIssueSeverity.FAULT for issue in self.issues)

    @property
    def has_interrupt(self) -> bool:
        return any(issue.severity == ManagerIssueSeverity.INTERRUPT for issue in self.issues)

    @property
    def has_refusal(self) -> bool:
        return any(issue.severity == ManagerIssueSeverity.REFUSED for issue in self.issues)

    @property
    def has_blocker(self) -> bool:
        return any(issue.severity == ManagerIssueSeverity.BLOCKED for issue in self.issues)


@dataclass(frozen=True)
class WorkPacketCandidate:
    """Manager work packet candidate without dispatch authority."""

    packet_id: str
    work_ref: str
    readiness_state: ManagerReadinessState
    packet_state: ManagerWorkPacketState
    model_route: ManagerModelRoute
    proof_obligation_set: tuple[ProofObligation, ...]
    completion_gate: CompletionGate | None
    issue_set: tuple[ManagerIssue, ...] = ()
    source_ref_set: tuple[str, ...] = ()
    authority_notice_ref: str = ""
    dispatch_authorized: bool = False
    live_effect_performed: bool = False
    non_authority_notice: str = NO_DISPATCH_NOTICE

    @property
    def ready_for_claim(self) -> bool:
        return (
            self.packet_state == ManagerWorkPacketState.READY_FOR_CLAIM
            and not self.dispatch_authorized
            and not self.live_effect_performed
        )


def manager_cycle_input_from_parts(
    *,
    cycle_id: str,
    work_ref: str,
    source_ref_set: Iterable[str],
    authority_notice_ref: str,
    source_authority_state: str = "accepted_and_fresh",
    support_state: str = "complete",
    coordination_state: str = "uncontested",
    operations_dry_run_state: str = "not_required",
    carrier_context_kind: str = "",
    carrier_context_state: str = "",
    surface_kind: str = "",
    requested_effect_classification_state: str = "classified",
    requested_effect_kind: str = "",
    requested_promotion: str = "",
    live_authority_state: str = "missing",
    human_override_state: str = "",
    override_scope: str = "",
    risk_context_state: str = "",
    revocation_route_state: str = "",
    generated_projection_state: str = "",
    graph_checkpoint_state: str = "",
    kernel_reference_state: str = "present",
    model_route: str | ManagerModelRoute = ManagerModelRoute.REQUIRES_DEEPER_REASONING,
    model_route_state: str = "declared",
    completion_review_ref: str = "",
    proof_obligation_ref_set: Iterable[str] = (),
    freshness_state: str | ManagerFreshnessState = ManagerFreshnessState.FRESH,
    authority_class: str | ManagerAuthorityClass = ManagerAuthorityClass.MANAGER_PLANNING_RECORD,
) -> ManagerCycleInput:
    """Build a manager cycle input while normalizing iterables and enums."""

    return ManagerCycleInput(
        cycle_id=cycle_id,
        work_ref=work_ref,
        source_ref_set=tuple(source_ref_set),
        authority_notice_ref=authority_notice_ref,
        source_authority_state=source_authority_state,
        support_state=support_state,
        coordination_state=coordination_state,
        operations_dry_run_state=operations_dry_run_state,
        carrier_context_kind=carrier_context_kind,
        carrier_context_state=carrier_context_state,
        surface_kind=surface_kind,
        requested_effect_classification_state=requested_effect_classification_state,
        requested_effect_kind=requested_effect_kind,
        requested_promotion=requested_promotion,
        live_authority_state=live_authority_state,
        human_override_state=human_override_state,
        override_scope=override_scope,
        risk_context_state=risk_context_state,
        revocation_route_state=revocation_route_state,
        generated_projection_state=generated_projection_state,
        graph_checkpoint_state=graph_checkpoint_state,
        kernel_reference_state=kernel_reference_state,
        model_route=ManagerModelRoute(model_route),
        model_route_state=model_route_state,
        completion_review_ref=completion_review_ref,
        proof_obligation_ref_set=tuple(proof_obligation_ref_set),
        freshness_state=ManagerFreshnessState(freshness_state),
        authority_class=ManagerAuthorityClass(authority_class),
    )


def manager_cycle_input_from_mapping(data: Mapping[str, object]) -> ManagerCycleInput:
    """Build a manager cycle input from mapping data."""

    cycle_id = str(data.get("cycle_id", data.get("fixture_case_id", "")))
    return manager_cycle_input_from_parts(
        cycle_id=cycle_id,
        work_ref=str(data.get("work_ref", cycle_id)),
        source_ref_set=_as_string_sequence(data.get("source_ref_set", ())),
        authority_notice_ref=str(data.get("authority_notice_ref", "authority_notice")),
        source_authority_state=str(data.get("source_authority_state", "accepted_and_fresh")),
        support_state=str(data.get("support_state", "complete")),
        coordination_state=str(data.get("coordination_state", "uncontested")),
        operations_dry_run_state=str(data.get("operations_dry_run_state", "not_required")),
        carrier_context_kind=str(data.get("carrier_context_kind", "")),
        carrier_context_state=str(data.get("carrier_context_state", "")),
        surface_kind=str(data.get("surface_kind", "")),
        requested_effect_classification_state=str(data.get("requested_effect_classification_state", "classified")),
        requested_effect_kind=str(data.get("requested_effect_kind", "")),
        requested_promotion=str(data.get("requested_promotion", "")),
        live_authority_state=str(data.get("live_authority_state", "missing")),
        human_override_state=str(data.get("human_override_state", "")),
        override_scope=str(data.get("override_scope", "")),
        risk_context_state=str(data.get("risk_context_state", "")),
        revocation_route_state=str(data.get("revocation_route_state", "")),
        generated_projection_state=str(data.get("generated_projection_state", "")),
        graph_checkpoint_state=str(data.get("graph_checkpoint_state", "")),
        kernel_reference_state=str(data.get("kernel_reference_state", "present")),
        model_route=str(data.get("model_route", ManagerModelRoute.REQUIRES_DEEPER_REASONING.value)),
        model_route_state=str(data.get("model_route_state", "declared")),
        completion_review_ref=str(data.get("completion_review_ref", "")),
        proof_obligation_ref_set=_as_string_sequence(data.get("proof_obligation_ref_set", ())),
        freshness_state=str(data.get("freshness_state", ManagerFreshnessState.FRESH.value)),
        authority_class=str(data.get("authority_class", ManagerAuthorityClass.MANAGER_PLANNING_RECORD.value)),
    )


def proof_obligations_for_cycle(cycle: ManagerCycleInput) -> tuple[ProofObligation, ...]:
    """Return default proof obligations for a cycle input."""

    if cycle.proof_obligation_ref_set:
        return tuple(
            ProofObligation(
                obligation_id=ref,
                required_evidence_ref_set=cycle.source_ref_set or (cycle.work_ref,),
                satisfied=False,
            )
            for ref in cycle.proof_obligation_ref_set
        )
    return (
        ProofObligation(
            obligation_id=f"{cycle.work_ref}:source_authority",
            required_evidence_ref_set=cycle.source_ref_set or (cycle.work_ref,),
            satisfied=cycle.source_authority_state == "accepted_and_fresh",
        ),
        ProofObligation(
            obligation_id=f"{cycle.work_ref}:completion_review",
            required_evidence_ref_set=(cycle.completion_review_ref,) if cycle.completion_review_ref else (),
            satisfied=bool(cycle.completion_review_ref),
        ),
    )


def completion_gate_for_cycle(cycle: ManagerCycleInput) -> CompletionGate:
    """Return the deterministic completion gate for a cycle input."""

    return CompletionGate(
        gate_id=f"{cycle.work_ref}:completion_gate",
        required_review_ref=cycle.completion_review_ref or "completion_review_required",
        opened=bool(cycle.completion_review_ref),
    )


def _as_string_sequence(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,) if value else ()
    return tuple(str(item) for item in value)  # type: ignore[operator]
