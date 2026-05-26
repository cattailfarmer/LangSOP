"""Pure in-process runner for the bounded IR4 runtime graph proof.

The runner evaluates graph contracts and operator harness results in memory. It
does not persist checkpoints, write generated traces, dispatch jobs, or control
external processes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

from langsop.operators import OperatorContract, OperatorRequest, OperatorRunResult, OutcomeKind, run_contract_operator

from .checkpoints import CheckpointEnvelope, CheckpointValidationResult, validate_checkpoint
from .graph_contracts import (
    DEFAULT_WHOLE_FIELD_PLANNER_GRAPH_CONTRACT,
    WholeFieldPlannerGraphContract,
    classify_terminal_outcome,
    validate_graph_state,
    validate_node_preconditions,
    validate_success_postconditions,
)
from .graph_state import (
    GraphIssue,
    GraphIssueKind,
    GraphIssueSeverity,
    GraphNodeId,
    GraphPhase,
    GraphState,
    GraphValidationResult,
    TerminalOutcome,
    TerminalOutcomeRecord,
    merge_validation_results,
)
from .interrupts import InterruptContextPacket, build_interrupt_context, interrupt_kind_for_issue


OperatorFunction = Callable[[tuple[object, ...]], Mapping[str, object] | object]


@dataclass(frozen=True)
class GraphRunPolicy:
    """Policy inputs that keep the pure runner bounded."""

    accepted_freshness_basis_ref_set: tuple[str, ...] = ()
    accepted_scope: str = "accepted_activation_boundary"
    require_readiness_proof: bool = True
    require_completion_review_for_success: bool = True
    require_no_hidden_write_proof_for_success: bool = True
    run_id: str = "ir4-runtime-graph-run"


@dataclass(frozen=True)
class GraphRunResult:
    """Complete projection-only graph run result."""

    request_ref: str
    accepted: bool
    terminal_outcome: TerminalOutcome
    terminal_record: TerminalOutcomeRecord
    graph_phase_sequence: tuple[GraphPhase, ...]
    node_visit_set: tuple[GraphNodeId, ...]
    validation: GraphValidationResult
    operator_run_result: OperatorRunResult | None = None
    checkpoint_validation_result: CheckpointValidationResult | None = None
    interrupt_context: InterruptContextPacket | None = None


def run_whole_field_planner_graph(
    graph_state: GraphState,
    operator_contract: OperatorContract,
    *,
    operator_request: OperatorRequest | Mapping[str, object] | None = None,
    operator_function: OperatorFunction | None = None,
    input_records: Sequence[object] = (),
    checkpoint: CheckpointEnvelope | None = None,
    policy: GraphRunPolicy | None = None,
    graph_contract: WholeFieldPlannerGraphContract = DEFAULT_WHOLE_FIELD_PLANNER_GRAPH_CONTRACT,
) -> GraphRunResult:
    """Evaluate the accepted graph path without external side effects."""

    resolved_policy = policy or GraphRunPolicy()
    phase_sequence: list[GraphPhase] = []
    node_visits: list[GraphNodeId] = []
    request_ref = _request_ref(operator_request)

    packet_validation = _visit_node(
        graph_state,
        GraphNodeId.PACKET_INTAKE,
        graph_contract,
        phase_sequence,
        node_visits,
    )
    state_validation = validate_graph_state(graph_state)
    validation = merge_validation_results(packet_validation, state_validation)
    if not validation.accepted:
        return _terminal_result(
            request_ref=request_ref,
            state=graph_state,
            validation=validation,
            phase_sequence=phase_sequence,
            node_visits=node_visits,
        )

    if checkpoint is not None:
        checkpoint_validation = validate_checkpoint(
            checkpoint,
            accepted_freshness_basis_ref_set=resolved_policy.accepted_freshness_basis_ref_set,
        )
        if not checkpoint_validation.accepted:
            return _terminal_result(
                request_ref=request_ref,
                state=graph_state,
                validation=checkpoint_validation.validation,
                phase_sequence=phase_sequence,
                node_visits=node_visits,
                checkpoint_validation_result=checkpoint_validation,
            )

    readiness_validation = _visit_node(
        graph_state,
        GraphNodeId.READINESS_GUARD,
        graph_contract,
        phase_sequence,
        node_visits,
        override_phase=GraphPhase.READINESS_GUARD,
    )
    if resolved_policy.require_readiness_proof and not graph_state.proof_result_ref_set:
        readiness_validation = merge_validation_results(
            readiness_validation,
            GraphValidationResult(
                False,
                (
                    GraphIssue(
                        GraphIssueKind.MISSING_AUTHORITY,
                        GraphIssueSeverity.BLOCKED,
                        "readiness proof refs are required before operator invocation",
                        "proof_result_ref_set",
                    ),
                ),
            ),
        )
    if not readiness_validation.accepted:
        return _terminal_result(
            request_ref=request_ref,
            state=graph_state,
            validation=readiness_validation,
            phase_sequence=phase_sequence,
            node_visits=node_visits,
        )

    coordination_validation = _visit_node(
        graph_state,
        GraphNodeId.COORDINATION_GUARD,
        graph_contract,
        phase_sequence,
        node_visits,
        override_phase=GraphPhase.COORDINATION_GUARD,
    )
    contested_claims = tuple(ref for ref in graph_state.coordination_claim_ref_set if "contested" in ref.lower())
    if contested_claims:
        coordination_validation = merge_validation_results(
            coordination_validation,
            GraphValidationResult(
                False,
                (
                    GraphIssue(
                        GraphIssueKind.CONTESTED_COORDINATION,
                        GraphIssueSeverity.INTERRUPT,
                        "contested coordination claims must be resolved outside the runner",
                        "coordination_claim_ref_set",
                    ),
                ),
            ),
        )
    if not coordination_validation.accepted:
        return _terminal_result(
            request_ref=request_ref,
            state=graph_state,
            validation=coordination_validation,
            phase_sequence=phase_sequence,
            node_visits=node_visits,
        )

    select_validation = _visit_node(
        graph_state,
        GraphNodeId.OPERATOR_CONTRACT_SELECT,
        graph_contract,
        phase_sequence,
        node_visits,
        override_phase=GraphPhase.OPERATOR_CONTRACT_SELECT,
    )
    if operator_request is None:
        select_validation = merge_validation_results(
            select_validation,
            GraphValidationResult(
                False,
                (
                    GraphIssue(
                        GraphIssueKind.MISSING_AUTHORITY,
                        GraphIssueSeverity.BLOCKED,
                        "operator_request is required before operator invocation",
                        "operator_request",
                    ),
                ),
            ),
        )
    if not select_validation.accepted:
        return _terminal_result(
            request_ref=request_ref,
            state=graph_state,
            validation=select_validation,
            phase_sequence=phase_sequence,
            node_visits=node_visits,
        )

    _append_visit(phase_sequence, node_visits, GraphPhase.OPERATOR_INVOCATION, GraphNodeId.OPERATOR_INVOCATION)
    operator_run = run_contract_operator(
        operator_request,
        operator_contract,
        operator_function=operator_function,
        input_records=input_records,
        run_id=resolved_policy.run_id,
        event_id="ir4-runtime-operator-event",
        accepted_scope=resolved_policy.accepted_scope,
    )

    _append_visit(phase_sequence, node_visits, GraphPhase.TRACE_RECORDING, GraphNodeId.TRACE_RECORDING)
    trace_validation = _trace_validation(operator_run)
    if not trace_validation.accepted:
        return _terminal_result(
            request_ref=request_ref,
            state=graph_state,
            validation=trace_validation,
            phase_sequence=phase_sequence,
            node_visits=node_visits,
            operator_run_result=operator_run,
        )

    if operator_run.outcome_kind != OutcomeKind.SUCCESS:
        validation = _operator_terminal_validation(operator_run)
        return _terminal_result(
            request_ref=request_ref,
            state=graph_state,
            validation=validation,
            phase_sequence=phase_sequence,
            node_visits=node_visits,
            operator_run_result=operator_run,
        )

    _append_visit(phase_sequence, node_visits, GraphPhase.COMPLETION_GATE, GraphNodeId.COMPLETION_GATE)
    completion_contract = graph_contract.node_contract(GraphNodeId.COMPLETION_GATE)
    completion_validation = (
        validate_success_postconditions(graph_state, completion_contract)
        if completion_contract is not None
        else GraphValidationResult(True)
    )
    completion_validation = _apply_completion_policy(graph_state, completion_validation, resolved_policy)
    if not completion_validation.accepted:
        return _terminal_result(
            request_ref=request_ref,
            state=graph_state,
            validation=completion_validation,
            phase_sequence=phase_sequence,
            node_visits=node_visits,
            operator_run_result=operator_run,
        )

    return _terminal_result(
        request_ref=request_ref,
        state=graph_state,
        validation=GraphValidationResult(True),
        phase_sequence=phase_sequence,
        node_visits=node_visits,
        operator_run_result=operator_run,
    )


def _visit_node(
    state: GraphState,
    node_id: GraphNodeId,
    graph_contract: WholeFieldPlannerGraphContract,
    phase_sequence: list[GraphPhase],
    node_visits: list[GraphNodeId],
    *,
    override_phase: GraphPhase | None = None,
) -> GraphValidationResult:
    phase = override_phase or state.graph_phase
    _append_visit(phase_sequence, node_visits, phase, node_id)
    node_contract = graph_contract.node_contract(node_id)
    if node_contract is None:
        return GraphValidationResult(
            False,
            (
                GraphIssue(
                    GraphIssueKind.INVALID_TRANSITION,
                    GraphIssueSeverity.FAULT,
                    "node is not present in graph contract",
                    "current_node_id",
                ),
            ),
        )
    if node_id == state.current_node_id:
        return validate_node_preconditions(state, node_contract)
    return GraphValidationResult(True)


def _append_visit(
    phase_sequence: list[GraphPhase],
    node_visits: list[GraphNodeId],
    phase: GraphPhase,
    node_id: GraphNodeId,
) -> None:
    phase_sequence.append(phase)
    node_visits.append(node_id)


def _trace_validation(operator_run: OperatorRunResult) -> GraphValidationResult:
    if operator_run.operator_trace.trace_id:
        return GraphValidationResult(True)
    return GraphValidationResult(
        False,
        (
            GraphIssue(
                GraphIssueKind.MISSING_TRACE,
                GraphIssueSeverity.FAULT,
                "operator trace is required before terminal success",
                "operator_trace",
            ),
        ),
    )


def _operator_terminal_validation(operator_run: OperatorRunResult) -> GraphValidationResult:
    if operator_run.outcome_kind == OutcomeKind.BLOCKED_OUTPUT:
        severity = GraphIssueSeverity.BLOCKED
        issue_kind = GraphIssueKind.MISSING_AUTHORITY
    elif operator_run.outcome_kind == OutcomeKind.SOP_FIRST_INTERRUPT:
        severity = GraphIssueSeverity.INTERRUPT
        issue_kind = GraphIssueKind.AMBIGUOUS_IDENTITY
    else:
        severity = GraphIssueSeverity.FAULT
        issue_kind = GraphIssueKind.HIDDEN_WRITE_ATTEMPT
    return GraphValidationResult(
        False,
        (
            GraphIssue(
                issue_kind,
                severity,
                f"operator runner returned {operator_run.outcome_kind.value}",
                "operator_run_result",
            ),
        ),
    )


def _apply_completion_policy(
    state: GraphState,
    validation: GraphValidationResult,
    policy: GraphRunPolicy,
) -> GraphValidationResult:
    issues = list(validation.issues)
    if policy.require_completion_review_for_success and not state.completion_review_ref:
        issues.append(
            GraphIssue(
                GraphIssueKind.MISSING_COMPLETION_REVIEW,
                GraphIssueSeverity.BLOCKED,
                "accepted completion review is required before terminal success",
                "completion_review_ref",
            )
        )
    if policy.require_no_hidden_write_proof_for_success and not state.no_hidden_write_proof_ref:
        issues.append(
            GraphIssue(
                GraphIssueKind.HIDDEN_WRITE_ATTEMPT,
                GraphIssueSeverity.BLOCKED,
                "no-hidden-write proof is required before terminal success",
                "no_hidden_write_proof_ref",
            )
        )
    return GraphValidationResult(not issues, tuple(issues))


def _terminal_result(
    *,
    request_ref: str,
    state: GraphState,
    validation: GraphValidationResult,
    phase_sequence: list[GraphPhase],
    node_visits: list[GraphNodeId],
    operator_run_result: OperatorRunResult | None = None,
    checkpoint_validation_result: CheckpointValidationResult | None = None,
) -> GraphRunResult:
    if not phase_sequence or phase_sequence[-1] != GraphPhase.TERMINAL_OUTCOME:
        _append_visit(phase_sequence, node_visits, GraphPhase.TERMINAL_OUTCOME, GraphNodeId.TERMINAL_OUTCOME)
    terminal_outcome = classify_terminal_outcome(validation)
    primary_issue = validation.issues[0] if validation.issues else None
    interrupt_context = _interrupt_context_for_issue(state, primary_issue) if terminal_outcome == TerminalOutcome.INTERRUPT else None
    terminal_record = TerminalOutcomeRecord(
        terminal_outcome=terminal_outcome,
        reason=primary_issue.reason if primary_issue else "graph path completed",
        node_id=GraphNodeId.TERMINAL_OUTCOME,
        graph_phase_sequence=tuple(phase_sequence),
        operator_trace_ref_set=_operator_trace_ref_set(operator_run_result),
        output_record_ref_set=state.output_record_ref_set,
        fault_record_ref_set=state.fault_record_ref_set,
        stale_projection_ref_set=state.stale_projection_ref_set,
        pending_interrupt_ref=interrupt_context.interrupt_id if interrupt_context else state.pending_interrupt_ref,
        no_hidden_write_proof_ref=state.no_hidden_write_proof_ref,
    )
    return GraphRunResult(
        request_ref=request_ref,
        accepted=terminal_outcome == TerminalOutcome.SUCCESS,
        terminal_outcome=terminal_outcome,
        terminal_record=terminal_record,
        graph_phase_sequence=tuple(phase_sequence),
        node_visit_set=tuple(node_visits),
        validation=validation,
        operator_run_result=operator_run_result,
        checkpoint_validation_result=checkpoint_validation_result,
        interrupt_context=interrupt_context,
    )


def _interrupt_context_for_issue(state: GraphState, issue: GraphIssue | None) -> InterruptContextPacket | None:
    if issue is None:
        return None
    interrupt_kind = interrupt_kind_for_issue(issue)
    return build_interrupt_context(
        interrupt_kind=interrupt_kind,
        graph_state=state,
        required_judgment=issue.reason,
        allowed_resume_route_set=("accepted_SOP_decision_or_review_artifact",),
        evidence_ref_set=tuple(ref for ref in (issue.field_name, issue.reason) if ref),
    )


def _operator_trace_ref_set(operator_run_result: OperatorRunResult | None) -> tuple[str, ...]:
    if operator_run_result is None:
        return ()
    return (operator_run_result.operator_trace.trace_id,)


def _request_ref(operator_request: OperatorRequest | Mapping[str, object] | None) -> str:
    if operator_request is None:
        return "missing_operator_request"
    if isinstance(operator_request, OperatorRequest):
        return operator_request.request_id
    return str(operator_request.get("request_id", "operator_request"))
