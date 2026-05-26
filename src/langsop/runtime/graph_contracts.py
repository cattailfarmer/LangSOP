"""Pure graph contract helpers for the bounded IR4 runtime graph proof."""

from __future__ import annotations

from dataclasses import dataclass, field

from .graph_state import (
    GraphIssue,
    GraphIssueKind,
    GraphIssueSeverity,
    GraphNodeId,
    GraphPhase,
    GraphState,
    GraphValidationResult,
    TerminalOutcome,
    terminal_outcome_for_issues,
)


@dataclass(frozen=True)
class GraphNodeContract:
    """Precondition and output obligations for one graph node."""

    node_id: GraphNodeId
    graph_phase: GraphPhase
    required_state_field_set: tuple[str, ...] = ()
    required_ref_field_set: tuple[str, ...] = ()
    required_for_success_field_set: tuple[str, ...] = ()
    terminal_on_issue: bool = True


@dataclass(frozen=True)
class GraphEdgeContract:
    """Allowed transition between graph nodes for one outcome class."""

    from_node_id: GraphNodeId
    outcome: TerminalOutcome | str
    to_node_id: GraphNodeId


@dataclass(frozen=True)
class WholeFieldPlannerGraphContract:
    """The first-pass contract model for the accepted WholeFieldPlannerGraph."""

    node_contract_set: tuple[GraphNodeContract, ...]
    edge_contract_set: tuple[GraphEdgeContract, ...]
    authority_limit: str = "execution_state_only"
    external_dependency_set: frozenset[str] = field(default_factory=frozenset)

    def node_contract(self, node_id: GraphNodeId | str) -> GraphNodeContract | None:
        resolved_node_id = GraphNodeId(node_id)
        return next((contract for contract in self.node_contract_set if contract.node_id == resolved_node_id), None)

    def next_node_for(self, node_id: GraphNodeId | str, outcome: TerminalOutcome | str) -> GraphNodeId | None:
        resolved_node_id = GraphNodeId(node_id)
        resolved_outcome = outcome if isinstance(outcome, TerminalOutcome) else str(outcome)
        for edge in self.edge_contract_set:
            edge_outcome = edge.outcome if isinstance(edge.outcome, TerminalOutcome) else str(edge.outcome)
            if edge.from_node_id == resolved_node_id and edge_outcome == resolved_outcome:
                return edge.to_node_id
        return None


DEFAULT_NODE_CONTRACTS: tuple[GraphNodeContract, ...] = (
    GraphNodeContract(
        GraphNodeId.PACKET_INTAKE,
        GraphPhase.PACKET_INTAKE,
        required_state_field_set=("active_work_packet_ref", "accepted_boundary_pack_ref_set"),
        required_ref_field_set=("accepted_boundary_pack_ref_set",),
    ),
    GraphNodeContract(
        GraphNodeId.READINESS_GUARD,
        GraphPhase.READINESS_GUARD,
        required_state_field_set=("active_work_packet_ref",),
    ),
    GraphNodeContract(
        GraphNodeId.COORDINATION_GUARD,
        GraphPhase.COORDINATION_GUARD,
    ),
    GraphNodeContract(
        GraphNodeId.OPERATOR_CONTRACT_SELECT,
        GraphPhase.OPERATOR_CONTRACT_SELECT,
    ),
    GraphNodeContract(
        GraphNodeId.OPERATOR_INVOCATION,
        GraphPhase.OPERATOR_INVOCATION,
    ),
    GraphNodeContract(
        GraphNodeId.TRACE_RECORDING,
        GraphPhase.TRACE_RECORDING,
        required_for_success_field_set=("operator_trace_ref_set",),
    ),
    GraphNodeContract(
        GraphNodeId.COMPLETION_GATE,
        GraphPhase.COMPLETION_GATE,
        required_for_success_field_set=("completion_review_ref", "no_hidden_write_proof_ref"),
    ),
    GraphNodeContract(
        GraphNodeId.SOP_FIRST_INTERRUPT,
        GraphPhase.SOP_FIRST_INTERRUPT,
        required_state_field_set=("pending_interrupt_ref",),
    ),
    GraphNodeContract(
        GraphNodeId.TERMINAL_OUTCOME,
        GraphPhase.TERMINAL_OUTCOME,
        terminal_on_issue=False,
    ),
)


DEFAULT_EDGE_CONTRACTS: tuple[GraphEdgeContract, ...] = (
    GraphEdgeContract(GraphNodeId.PACKET_INTAKE, TerminalOutcome.SUCCESS, GraphNodeId.READINESS_GUARD),
    GraphEdgeContract(GraphNodeId.PACKET_INTAKE, TerminalOutcome.BLOCKED, GraphNodeId.TERMINAL_OUTCOME),
    GraphEdgeContract(GraphNodeId.PACKET_INTAKE, TerminalOutcome.STALE, GraphNodeId.TERMINAL_OUTCOME),
    GraphEdgeContract(GraphNodeId.PACKET_INTAKE, TerminalOutcome.FAULT, GraphNodeId.TERMINAL_OUTCOME),
    GraphEdgeContract(GraphNodeId.PACKET_INTAKE, TerminalOutcome.INTERRUPT, GraphNodeId.TERMINAL_OUTCOME),
    GraphEdgeContract(GraphNodeId.READINESS_GUARD, TerminalOutcome.SUCCESS, GraphNodeId.COORDINATION_GUARD),
    GraphEdgeContract(GraphNodeId.READINESS_GUARD, TerminalOutcome.BLOCKED, GraphNodeId.TERMINAL_OUTCOME),
    GraphEdgeContract(GraphNodeId.READINESS_GUARD, TerminalOutcome.STALE, GraphNodeId.TERMINAL_OUTCOME),
    GraphEdgeContract(GraphNodeId.READINESS_GUARD, TerminalOutcome.FAULT, GraphNodeId.TERMINAL_OUTCOME),
    GraphEdgeContract(GraphNodeId.READINESS_GUARD, TerminalOutcome.INTERRUPT, GraphNodeId.TERMINAL_OUTCOME),
    GraphEdgeContract(GraphNodeId.COORDINATION_GUARD, TerminalOutcome.SUCCESS, GraphNodeId.OPERATOR_CONTRACT_SELECT),
    GraphEdgeContract(GraphNodeId.COORDINATION_GUARD, TerminalOutcome.BLOCKED, GraphNodeId.TERMINAL_OUTCOME),
    GraphEdgeContract(GraphNodeId.COORDINATION_GUARD, TerminalOutcome.STALE, GraphNodeId.TERMINAL_OUTCOME),
    GraphEdgeContract(GraphNodeId.COORDINATION_GUARD, TerminalOutcome.FAULT, GraphNodeId.TERMINAL_OUTCOME),
    GraphEdgeContract(GraphNodeId.COORDINATION_GUARD, TerminalOutcome.INTERRUPT, GraphNodeId.TERMINAL_OUTCOME),
    GraphEdgeContract(GraphNodeId.OPERATOR_CONTRACT_SELECT, TerminalOutcome.SUCCESS, GraphNodeId.OPERATOR_INVOCATION),
    GraphEdgeContract(GraphNodeId.OPERATOR_CONTRACT_SELECT, TerminalOutcome.BLOCKED, GraphNodeId.TERMINAL_OUTCOME),
    GraphEdgeContract(GraphNodeId.OPERATOR_CONTRACT_SELECT, TerminalOutcome.STALE, GraphNodeId.TERMINAL_OUTCOME),
    GraphEdgeContract(GraphNodeId.OPERATOR_CONTRACT_SELECT, TerminalOutcome.FAULT, GraphNodeId.TERMINAL_OUTCOME),
    GraphEdgeContract(GraphNodeId.OPERATOR_CONTRACT_SELECT, TerminalOutcome.INTERRUPT, GraphNodeId.TERMINAL_OUTCOME),
    GraphEdgeContract(GraphNodeId.OPERATOR_INVOCATION, TerminalOutcome.SUCCESS, GraphNodeId.TRACE_RECORDING),
    GraphEdgeContract(GraphNodeId.OPERATOR_INVOCATION, TerminalOutcome.BLOCKED, GraphNodeId.TRACE_RECORDING),
    GraphEdgeContract(GraphNodeId.OPERATOR_INVOCATION, TerminalOutcome.FAULT, GraphNodeId.TRACE_RECORDING),
    GraphEdgeContract(GraphNodeId.OPERATOR_INVOCATION, TerminalOutcome.INTERRUPT, GraphNodeId.TRACE_RECORDING),
    GraphEdgeContract(GraphNodeId.TRACE_RECORDING, TerminalOutcome.SUCCESS, GraphNodeId.COMPLETION_GATE),
    GraphEdgeContract(GraphNodeId.TRACE_RECORDING, TerminalOutcome.BLOCKED, GraphNodeId.TERMINAL_OUTCOME),
    GraphEdgeContract(GraphNodeId.TRACE_RECORDING, TerminalOutcome.STALE, GraphNodeId.TERMINAL_OUTCOME),
    GraphEdgeContract(GraphNodeId.TRACE_RECORDING, TerminalOutcome.FAULT, GraphNodeId.TERMINAL_OUTCOME),
    GraphEdgeContract(GraphNodeId.TRACE_RECORDING, TerminalOutcome.INTERRUPT, GraphNodeId.TERMINAL_OUTCOME),
    GraphEdgeContract(GraphNodeId.COMPLETION_GATE, "open_next_slice", GraphNodeId.TERMINAL_OUTCOME),
    GraphEdgeContract(GraphNodeId.COMPLETION_GATE, TerminalOutcome.BLOCKED, GraphNodeId.TERMINAL_OUTCOME),
    GraphEdgeContract(GraphNodeId.COMPLETION_GATE, TerminalOutcome.STALE, GraphNodeId.TERMINAL_OUTCOME),
    GraphEdgeContract(GraphNodeId.COMPLETION_GATE, TerminalOutcome.FAULT, GraphNodeId.TERMINAL_OUTCOME),
    GraphEdgeContract(GraphNodeId.COMPLETION_GATE, TerminalOutcome.INTERRUPT, GraphNodeId.TERMINAL_OUTCOME),
)


DEFAULT_WHOLE_FIELD_PLANNER_GRAPH_CONTRACT = WholeFieldPlannerGraphContract(
    node_contract_set=DEFAULT_NODE_CONTRACTS,
    edge_contract_set=DEFAULT_EDGE_CONTRACTS,
)


def validate_graph_state(state: GraphState) -> GraphValidationResult:
    """Validate graph state shape and authority/projection boundaries."""

    issues: list[GraphIssue] = []
    if not state.active_work_packet_ref:
        issues.append(
            GraphIssue(
                GraphIssueKind.MISSING_FIELD,
                GraphIssueSeverity.FAULT,
                "active_work_packet_ref is required",
                "active_work_packet_ref",
            )
        )

    if not state.accepted_boundary_pack_ref_set:
        issues.append(
            GraphIssue(
                GraphIssueKind.MISSING_AUTHORITY,
                GraphIssueSeverity.FAULT,
                "accepted boundary pack refs are required",
                "accepted_boundary_pack_ref_set",
            )
        )

    if state.authority_limit != "execution_state_only":
        issues.append(
            GraphIssue(
                GraphIssueKind.GENERATED_AUTHORITY,
                GraphIssueSeverity.FAULT,
                "graph state may not claim authority beyond execution_state_only",
                "authority_limit",
            )
        )

    if state.stale_projection_ref_set:
        issues.append(
            GraphIssue(
                GraphIssueKind.STALE_PROJECTION,
                GraphIssueSeverity.STALE,
                "stale projection refs are present",
                "stale_projection_ref_set",
            )
        )

    if state.fault_record_ref_set:
        issues.append(
            GraphIssue(
                GraphIssueKind.HIDDEN_WRITE_ATTEMPT,
                GraphIssueSeverity.FAULT,
                "fault records are present in graph state",
                "fault_record_ref_set",
            )
        )

    return GraphValidationResult(not issues, tuple(issues))


def validate_node_preconditions(
    state: GraphState,
    contract: GraphNodeContract,
) -> GraphValidationResult:
    """Validate node-specific state preconditions without running the node."""

    issues: list[GraphIssue] = []
    if state.current_node_id != contract.node_id:
        issues.append(
            GraphIssue(
                GraphIssueKind.INVALID_TRANSITION,
                GraphIssueSeverity.FAULT,
                "state current node does not match node contract",
                "current_node_id",
            )
        )

    if state.graph_phase != contract.graph_phase:
        issues.append(
            GraphIssue(
                GraphIssueKind.INVALID_TRANSITION,
                GraphIssueSeverity.FAULT,
                "state graph phase does not match node contract",
                "graph_phase",
            )
        )

    for field_name in contract.required_state_field_set:
        if not _field_has_value(state, field_name):
            issues.append(
                GraphIssue(
                    GraphIssueKind.MISSING_FIELD,
                    GraphIssueSeverity.FAULT,
                    f"{field_name} is required for {contract.node_id.value}",
                    field_name,
                )
            )

    for field_name in contract.required_ref_field_set:
        if not _field_has_value(state, field_name):
            issues.append(
                GraphIssue(
                    GraphIssueKind.MISSING_AUTHORITY,
                    GraphIssueSeverity.FAULT,
                    f"{field_name} is required authority input for {contract.node_id.value}",
                    field_name,
                )
            )

    return GraphValidationResult(not issues, tuple(issues))


def validate_success_postconditions(
    state: GraphState,
    contract: GraphNodeContract,
) -> GraphValidationResult:
    """Validate fields required before a node may claim success."""

    issues = tuple(
        GraphIssue(
            GraphIssueKind.MISSING_FIELD,
            GraphIssueSeverity.BLOCKED,
            f"{field_name} is required before {contract.node_id.value} may claim success",
            field_name,
        )
        for field_name in contract.required_for_success_field_set
        if not _field_has_value(state, field_name)
    )
    return GraphValidationResult(not issues, issues)


def classify_terminal_outcome(validation: GraphValidationResult) -> TerminalOutcome:
    """Classify a validation result into the accepted terminal outcome set."""

    return terminal_outcome_for_issues(validation.issues)


def validate_edge_transition(
    contract: WholeFieldPlannerGraphContract,
    from_node_id: GraphNodeId | str,
    outcome: TerminalOutcome | str,
    to_node_id: GraphNodeId | str,
) -> GraphValidationResult:
    """Validate a requested transition against the accepted edge map."""

    resolved_from = GraphNodeId(from_node_id)
    resolved_to = GraphNodeId(to_node_id)
    accepted_to = contract.next_node_for(resolved_from, outcome)
    if accepted_to == resolved_to:
        return GraphValidationResult(True)
    return GraphValidationResult(
        False,
        (
            GraphIssue(
                GraphIssueKind.INVALID_TRANSITION,
                GraphIssueSeverity.FAULT,
                "edge transition is not accepted by the graph contract",
                "to_node_id",
            ),
        ),
    )


def _field_has_value(state: GraphState, field_name: str) -> bool:
    value = getattr(state, field_name)
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value)
    if isinstance(value, tuple):
        return bool(value)
    return True
