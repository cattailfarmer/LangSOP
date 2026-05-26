"""State records for the bounded IR4 runtime graph proof.

Graph state is execution state only. These records are intentionally pure data
models and do not write checkpoints, traces, reports, or authority artifacts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


NON_AUTHORITY_WARNING = (
    "runtime graph state is execution-state-only and does not replace signed SOP authority"
)


class GraphPhase(str, Enum):
    """Accepted phases in the first-pass WholeFieldPlannerGraph proof."""

    PACKET_INTAKE = "packet_intake"
    READINESS_GUARD = "readiness_guard"
    COORDINATION_GUARD = "coordination_guard"
    OPERATOR_CONTRACT_SELECT = "operator_contract_select"
    OPERATOR_INVOCATION = "operator_invocation"
    TRACE_RECORDING = "trace_recording"
    COMPLETION_GATE = "completion_gate"
    SOP_FIRST_INTERRUPT = "sop_first_interrupt"
    TERMINAL_OUTCOME = "terminal_outcome"


class GraphNodeId(str, Enum):
    """Accepted node identifiers from the IR4 graph contract."""

    PACKET_INTAKE = "packet_intake"
    READINESS_GUARD = "readiness_guard"
    COORDINATION_GUARD = "coordination_guard"
    OPERATOR_CONTRACT_SELECT = "operator_contract_select"
    OPERATOR_INVOCATION = "operator_invocation"
    TRACE_RECORDING = "trace_recording"
    COMPLETION_GATE = "completion_gate"
    SOP_FIRST_INTERRUPT = "sop_first_interrupt"
    TERMINAL_OUTCOME = "terminal_outcome"


class TerminalOutcome(str, Enum):
    """Terminal outcomes a graph run may produce without silent retry."""

    SUCCESS = "terminal_success"
    BLOCKED = "terminal_blocked"
    STALE = "terminal_stale"
    FAULT = "terminal_fault"
    INTERRUPT = "terminal_interrupt"


class GraphIssueSeverity(str, Enum):
    """How a graph issue should be classified by contract helpers."""

    BLOCKED = "blocked"
    STALE = "stale"
    FAULT = "fault"
    INTERRUPT = "interrupt"


class GraphIssueKind(str, Enum):
    """Issue vocabulary for graph-state and contract validation."""

    MISSING_FIELD = "missing_field"
    MISSING_AUTHORITY = "missing_authority"
    MISSING_TRACE = "missing_trace"
    MISSING_COMPLETION_REVIEW = "missing_completion_review"
    STALE_PROJECTION = "stale_projection"
    CHECKPOINT_AUTHORITY_CONFUSION = "checkpoint_authority_confusion"
    GENERATED_AUTHORITY = "generated_authority"
    HIDDEN_WRITE_ATTEMPT = "hidden_write_attempt"
    CONTESTED_COORDINATION = "contested_coordination"
    AMBIGUOUS_IDENTITY = "ambiguous_identity"
    UNSUPPORTED_SCOPE = "unsupported_scope"
    INVALID_TRANSITION = "invalid_transition"


@dataclass(frozen=True)
class GraphIssue:
    """One blocked, stale, fault, or interrupt reason."""

    issue_kind: GraphIssueKind
    severity: GraphIssueSeverity
    reason: str
    field_name: str | None = None


@dataclass(frozen=True)
class GraphValidationResult:
    """Pure validation result for graph state or graph contract checks."""

    accepted: bool
    issues: tuple[GraphIssue, ...] = ()

    @property
    def has_fault(self) -> bool:
        return any(issue.severity == GraphIssueSeverity.FAULT for issue in self.issues)

    @property
    def has_interrupt(self) -> bool:
        return any(issue.severity == GraphIssueSeverity.INTERRUPT for issue in self.issues)

    @property
    def has_stale(self) -> bool:
        return any(issue.severity == GraphIssueSeverity.STALE for issue in self.issues)

    @property
    def has_blocker(self) -> bool:
        return any(issue.severity == GraphIssueSeverity.BLOCKED for issue in self.issues)


@dataclass(frozen=True)
class GraphState:
    """Implementation-facing graph state from the accepted IR4 contract."""

    active_work_packet_ref: str
    accepted_boundary_pack_ref_set: tuple[str, ...]
    graph_phase: GraphPhase
    current_node_id: GraphNodeId
    input_record_ref_set: tuple[str, ...] = ()
    output_record_ref_set: tuple[str, ...] = ()
    operator_trace_ref_set: tuple[str, ...] = ()
    proof_result_ref_set: tuple[str, ...] = ()
    stale_projection_ref_set: tuple[str, ...] = ()
    fault_record_ref_set: tuple[str, ...] = ()
    coordination_claim_ref_set: tuple[str, ...] = ()
    source_ref_set: tuple[str, ...] = ()
    lineage_edge_set: tuple[str, ...] = ()
    pending_interrupt_ref: str | None = None
    checkpoint_ref: str | None = None
    completion_review_ref: str | None = None
    no_hidden_write_proof_ref: str | None = None
    authority_limit: str = "execution_state_only"
    non_authority_warning: str = NON_AUTHORITY_WARNING


@dataclass(frozen=True)
class NodeResult:
    """Projection-only result emitted by a graph node."""

    node_id: GraphNodeId
    terminal_outcome: TerminalOutcome | None = None
    output_record_ref_set: tuple[str, ...] = ()
    operator_trace_ref_set: tuple[str, ...] = ()
    proof_result_ref_set: tuple[str, ...] = ()
    stale_projection_ref_set: tuple[str, ...] = ()
    fault_record_ref_set: tuple[str, ...] = ()
    pending_interrupt_ref: str | None = None
    non_authority_warning: str = NON_AUTHORITY_WARNING


@dataclass(frozen=True)
class TerminalOutcomeRecord:
    """Projection-only terminal outcome summary."""

    terminal_outcome: TerminalOutcome
    reason: str
    node_id: GraphNodeId
    graph_phase_sequence: tuple[GraphPhase, ...] = ()
    operator_trace_ref_set: tuple[str, ...] = ()
    output_record_ref_set: tuple[str, ...] = ()
    fault_record_ref_set: tuple[str, ...] = ()
    stale_projection_ref_set: tuple[str, ...] = ()
    pending_interrupt_ref: str | None = None
    no_hidden_write_proof_ref: str | None = None
    non_authority_warning: str = NON_AUTHORITY_WARNING


def terminal_outcome_for_issues(issues: tuple[GraphIssue, ...]) -> TerminalOutcome:
    """Classify issues using the contract priority: fault, interrupt, stale, blocked."""

    if any(issue.severity == GraphIssueSeverity.FAULT for issue in issues):
        return TerminalOutcome.FAULT
    if any(issue.severity == GraphIssueSeverity.INTERRUPT for issue in issues):
        return TerminalOutcome.INTERRUPT
    if any(issue.severity == GraphIssueSeverity.STALE for issue in issues):
        return TerminalOutcome.STALE
    if any(issue.severity == GraphIssueSeverity.BLOCKED for issue in issues):
        return TerminalOutcome.BLOCKED
    return TerminalOutcome.SUCCESS


def merge_validation_results(*results: GraphValidationResult) -> GraphValidationResult:
    """Merge independent pure validation results without changing issue order."""

    issues: list[GraphIssue] = []
    for result in results:
        issues.extend(result.issues)
    return GraphValidationResult(not issues, tuple(issues))


def graph_state_from_parts(
    *,
    active_work_packet_ref: str,
    accepted_boundary_pack_ref_set: tuple[str, ...],
    graph_phase: str | GraphPhase = GraphPhase.PACKET_INTAKE,
    current_node_id: str | GraphNodeId = GraphNodeId.PACKET_INTAKE,
    input_record_ref_set: tuple[str, ...] = (),
    output_record_ref_set: tuple[str, ...] = (),
    operator_trace_ref_set: tuple[str, ...] = (),
    proof_result_ref_set: tuple[str, ...] = (),
    stale_projection_ref_set: tuple[str, ...] = (),
    fault_record_ref_set: tuple[str, ...] = (),
    coordination_claim_ref_set: tuple[str, ...] = (),
    source_ref_set: tuple[str, ...] = (),
    lineage_edge_set: tuple[str, ...] = (),
    pending_interrupt_ref: str | None = None,
    checkpoint_ref: str | None = None,
    completion_review_ref: str | None = None,
    no_hidden_write_proof_ref: str | None = None,
) -> GraphState:
    """Build a GraphState while normalizing enum string values."""

    return GraphState(
        active_work_packet_ref=active_work_packet_ref,
        accepted_boundary_pack_ref_set=tuple(accepted_boundary_pack_ref_set),
        graph_phase=GraphPhase(graph_phase),
        current_node_id=GraphNodeId(current_node_id),
        input_record_ref_set=tuple(input_record_ref_set),
        output_record_ref_set=tuple(output_record_ref_set),
        operator_trace_ref_set=tuple(operator_trace_ref_set),
        proof_result_ref_set=tuple(proof_result_ref_set),
        stale_projection_ref_set=tuple(stale_projection_ref_set),
        fault_record_ref_set=tuple(fault_record_ref_set),
        coordination_claim_ref_set=tuple(coordination_claim_ref_set),
        source_ref_set=tuple(source_ref_set),
        lineage_edge_set=tuple(lineage_edge_set),
        pending_interrupt_ref=pending_interrupt_ref,
        checkpoint_ref=checkpoint_ref,
        completion_review_ref=completion_review_ref,
        no_hidden_write_proof_ref=no_hidden_write_proof_ref,
    )
