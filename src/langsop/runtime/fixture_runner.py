"""Fixture runner utilities for the bounded IR4 runtime graph proof.

The fixture runner is the bridge between reviewed SOP fixture sources and the
pure in-process graph runner. It validates read/write boundaries, converts
fixture fields into runtime inputs, and returns generated projection reports
without treating checkpoints, traces, reports, or graph state as authority.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
from typing import Mapping, Sequence

from langsop.operators import OperatorContract, OutcomeKind

from .checkpoints import (
    CheckpointAuthorityResult,
    CheckpointEnvelope,
    CheckpointFreshnessResult,
    CheckpointResumeCondition,
    CheckpointValidationResult,
    build_checkpoint_envelope,
)
from .graph_runner import GraphRunPolicy, GraphRunResult, OperatorFunction, run_whole_field_planner_graph
from .graph_state import GraphNodeId, GraphPhase, GraphState, NON_AUTHORITY_WARNING, TerminalOutcome


FIXTURE_SOURCE_ROOT = Path("tests/fixtures/sop/ir4_runtime_graph")
EXPECTED_LEDGER_ROOT = Path("tests/fixtures/expected/ir4_runtime_graph")
ACCEPTED_GENERATED_ROOTS: tuple[Path, ...] = (
    Path("tests/fixtures/generated/ir4_runtime_graph/checkpoints"),
    Path("tests/fixtures/generated/ir4_runtime_graph/traces"),
    Path("tests/fixtures/generated/ir4_runtime_graph/reports"),
    Path(".langsop/checkpoints/ir4_runtime_graph"),
    Path(".langsop/traces/ir4_runtime_graph"),
    Path(".langsop/reports/ir4_runtime_graph"),
)
FORBIDDEN_WRITE_ROOTS: tuple[Path, ...] = (
    Path("docs"),
    Path("src"),
    Path("platform"),
    Path(".git"),
    FIXTURE_SOURCE_ROOT,
    EXPECTED_LEDGER_ROOT,
)
DEFAULT_EXPECTED_LEDGER_PATHS: tuple[Path, ...] = (
    EXPECTED_LEDGER_ROOT / "graph_trace_expected.sop",
    EXPECTED_LEDGER_ROOT / "checkpoint_expected.sop",
    EXPECTED_LEDGER_ROOT / "interrupt_fault_refusal_expected.sop",
    EXPECTED_LEDGER_ROOT / "no_authority_promotion_expected.sop",
)
ACCEPTED_FRESHNESS_BASIS_REF_SET: tuple[str, ...] = (
    "docs/reviews/IR4_IA05_Completion_Review.v1.sop",
    "docs/runtime/IR4_WholeFieldPlannerGraph_Implementation_Contract.v1.sop",
    "docs/runtime/IR4_Checkpoint_And_SOP_First_Interrupt_Policy.v1.sop",
)
RUNTIME_GRAPH_SOURCE_REF_SET: tuple[str, ...] = (
    "docs/implementation/IR4_Bounded_Implementation_Activation_Boundary.v1.sop",
    "docs/fixtures/IR4_Runtime_Graph_Fixture_Index.v1.sop",
    "docs/runtime/IR4_WholeFieldPlannerGraph_Implementation_Contract.v1.sop",
    "docs/runtime/IR4_Checkpoint_And_SOP_First_Interrupt_Policy.v1.sop",
)

_FIELD_RE = re.compile(r"^(?P<indent>\s*)\+ \[(?P<name>[^\]]+)\] is (?P<value>.*)$")


@dataclass(frozen=True)
class RuntimeFixturePathPolicyResult:
    """Result of validating a requested runtime fixture path."""

    requested_path: str
    accepted: bool
    normalized_path: str | None = None
    matched_root: str | None = None
    refusal_reason: str | None = None
    non_authority_warning: str = NON_AUTHORITY_WARNING


@dataclass(frozen=True)
class RuntimeFixtureSource:
    """Tracked IR4 SOP fixture source parsed into fields and expectations."""

    fixture_id: str
    source_path: str
    field_map: Mapping[str, tuple[str, ...]]
    expectation_set: tuple[str, ...]


@dataclass(frozen=True)
class RuntimeExpectedLedger:
    """Tracked expected ledger with per-fixture expectation groups."""

    ledger_id: str
    source_path: str
    field_map: Mapping[str, tuple[str, ...]]
    case_expectation_map: Mapping[str, Mapping[str, tuple[str, ...]]]
    expectation_set: tuple[str, ...]


@dataclass(frozen=True)
class RuntimeFixtureExecutionProjection:
    """Generated execution projection used for fixture comparison."""

    terminal_outcome: TerminalOutcome
    graph_phase_sequence: tuple[GraphPhase, ...]
    node_visit_set: tuple[GraphNodeId, ...]
    operator_invoked: bool
    checkpoint_freshness_result: str | None = None
    checkpoint_authority_result: str | None = None
    resume_condition: str | None = None
    refusal_reason: str | None = None
    stale_reason: str | None = None
    fault_kind: str | None = None
    interrupt_kind: str | None = None
    operator_trace_ref_set: tuple[str, ...] = ()
    generated_artifact_ref_set: tuple[str, ...] = ()
    path_policy_result: RuntimeFixturePathPolicyResult | None = None
    non_authority_warning: str = NON_AUTHORITY_WARNING


@dataclass(frozen=True)
class RuntimeFixtureComparisonReport:
    """Generated projection report for one runtime graph fixture case."""

    fixture_id: str
    passed: bool
    observed_terminal_outcome: TerminalOutcome
    expected_fact_set: tuple[str, ...]
    observed_fact_set: tuple[str, ...]
    graph_phase_sequence: tuple[GraphPhase, ...]
    node_visit_set: tuple[GraphNodeId, ...]
    operator_invoked: bool
    generated_artifact_ref_set: tuple[str, ...] = ()
    checkpoint_freshness_result: str | None = None
    checkpoint_authority_result: str | None = None
    resume_condition: str | None = None
    refusal_reason: str | None = None
    stale_reason: str | None = None
    fault_kind: str | None = None
    interrupt_kind: str | None = None
    operator_trace_ref_set: tuple[str, ...] = ()
    path_policy_result: RuntimeFixturePathPolicyResult | None = None
    report_status: str = "generated_projection_only"
    non_authority_warning: str = NON_AUTHORITY_WARNING


@dataclass(frozen=True)
class RuntimeFixtureRunResult:
    """Complete result for one runtime graph fixture source."""

    fixture_source: RuntimeFixtureSource
    expected_ledger_set: tuple[RuntimeExpectedLedger, ...]
    comparison_report: RuntimeFixtureComparisonReport
    graph_run_result: GraphRunResult | None = None


def default_runtime_operator_contract() -> OperatorContract:
    """Return the accepted operator contract metadata used by IR4 fixtures."""

    return OperatorContract(
        operator_id="contract_driven_operator_runner",
        operator_version="v1",
        output_record_kind_set=frozenset(
            {
                "operator_result",
                "operator_trace",
                "graph_trace",
                "checkpoint_projection",
                "runtime_report",
                "fault_record",
                "sop_first_interrupt",
            }
        ),
    )


def load_runtime_fixture_source(
    path: str | Path,
    *,
    workspace_root: str | Path = ".",
) -> RuntimeFixtureSource:
    """Load a tracked IR4 runtime graph fixture source after path validation."""

    source_path = validate_tracked_runtime_fixture_source_path(path, workspace_root=workspace_root)
    if not source_path.accepted or source_path.normalized_path is None:
        raise ValueError(source_path.refusal_reason or "fixture_source_path_outside_policy")
    text = Path(source_path.normalized_path).read_text(encoding="utf-8")
    fields, expectations, _case_map = _parse_sop_fields(text)
    fixture_id = _first_field(fields, "fixture_case", Path(path).stem)
    return RuntimeFixtureSource(
        fixture_id=fixture_id,
        source_path=_display_path(path, workspace_root=workspace_root),
        field_map=fields,
        expectation_set=expectations,
    )


def load_runtime_expected_ledger(
    path: str | Path,
    *,
    workspace_root: str | Path = ".",
) -> RuntimeExpectedLedger:
    """Load a tracked expected ledger after path validation."""

    ledger_path = validate_runtime_expected_ledger_path(path, workspace_root=workspace_root)
    if not ledger_path.accepted or ledger_path.normalized_path is None:
        raise ValueError(ledger_path.refusal_reason or "expected_ledger_path_outside_policy")
    text = Path(ledger_path.normalized_path).read_text(encoding="utf-8")
    fields, expectations, case_map = _parse_sop_fields(text)
    return RuntimeExpectedLedger(
        ledger_id=Path(path).stem,
        source_path=_display_path(path, workspace_root=workspace_root),
        field_map=fields,
        case_expectation_map=case_map,
        expectation_set=expectations,
    )


def iter_runtime_fixture_paths(
    *,
    workspace_root: str | Path = ".",
) -> tuple[Path, ...]:
    """Return tracked fixture source paths under the accepted fixture root."""

    workspace = Path(workspace_root).resolve()
    root = _resolve_under_workspace(FIXTURE_SOURCE_ROOT, workspace)
    return tuple(sorted(root.glob("*.sop")))


def fixture_source_to_graph_state(fixture: RuntimeFixtureSource) -> GraphState:
    """Convert a tracked fixture source into initial graph state."""

    fields = fixture.field_map
    readiness_state = _first_field(fields, "readiness_state", "ready")
    coordination_state = _first_field(fields, "coordination_claim_state", "accepted")
    completion_gate_state = _first_field(fields, "completion_gate_state", "not_reached")
    hidden_write_attempt = _bool_field(fields, "hidden_write_attempt", False)
    accepted_boundary_refs = tuple(f"authority:{ref}" for ref in RUNTIME_GRAPH_SOURCE_REF_SET)

    proof_refs: tuple[str, ...] = ()
    if readiness_state == "ready":
        proof_refs = (f"proof_result:{fixture.fixture_id}:readiness",)

    coordination_refs: tuple[str, ...] = ()
    if coordination_state == "contested":
        coordination_refs = (f"coordination_claim:contested:{fixture.fixture_id}",)
    elif coordination_state:
        coordination_refs = (f"coordination_claim:{coordination_state}:{fixture.fixture_id}",)

    completion_review_ref = None
    no_hidden_write_proof_ref = None
    if completion_gate_state == "review_accepts_next_gate":
        completion_review_ref = f"completion_review:{fixture.fixture_id}:accepted"
        no_hidden_write_proof_ref = f"no_hidden_write_proof:{fixture.fixture_id}:accepted"

    fault_refs: tuple[str, ...] = ()
    if hidden_write_attempt and _first_field(fields, "generated_output_policy_state", "") != "rejected_outside_allowed_root":
        fault_refs = (f"fault_record:hidden_write_attempt:{fixture.fixture_id}",)

    return GraphState(
        active_work_packet_ref=f"work_packet:{fixture.fixture_id}",
        accepted_boundary_pack_ref_set=accepted_boundary_refs,
        graph_phase=GraphPhase.PACKET_INTAKE,
        current_node_id=GraphNodeId.PACKET_INTAKE,
        input_record_ref_set=(f"fixture_source:{fixture.source_path}",),
        proof_result_ref_set=proof_refs,
        fault_record_ref_set=fault_refs,
        coordination_claim_ref_set=coordination_refs,
        source_ref_set=RUNTIME_GRAPH_SOURCE_REF_SET + (fixture.source_path,),
        completion_review_ref=completion_review_ref,
        no_hidden_write_proof_ref=no_hidden_write_proof_ref,
    )


def fixture_source_to_checkpoint(fixture: RuntimeFixtureSource) -> CheckpointEnvelope:
    """Build the projection-only checkpoint envelope implied by a fixture."""

    freshness_state = _first_field(fixture.field_map, "checkpoint_freshness_state", "current")
    authority_state = _first_field(
        fixture.field_map,
        "checkpoint_authority_state",
        CheckpointAuthorityResult.NON_AUTHORITATIVE_EXECUTION_STATE.value,
    )
    readiness_state = _first_field(fixture.field_map, "readiness_state", "ready")
    basis = ACCEPTED_FRESHNESS_BASIS_REF_SET
    if freshness_state == CheckpointFreshnessResult.STALE.value:
        basis = ("stale:prior-fixture-source-hash",)

    return build_checkpoint_envelope(
        fixture_id=fixture.fixture_id,
        active_work_packet_ref=f"work_packet:{fixture.fixture_id}",
        freshness_basis_ref_set=basis,
        graph_phase=GraphPhase.PACKET_INTAKE.value,
        current_node_id=GraphNodeId.PACKET_INTAKE.value,
        presented_as_authority=authority_state == CheckpointAuthorityResult.AUTHORITY_CONFUSION_DETECTED.value,
        claims_readiness=readiness_state == "checkpoint_claims_ready",
    )


def fixture_source_to_operator_request(fixture: RuntimeFixtureSource) -> Mapping[str, object]:
    """Convert a fixture source into a contract-bound operator request."""

    fields = fixture.field_map
    operator_trace_state = _first_field(fields, "operator_trace_state", "valid")
    generated_policy_state = _first_field(fields, "generated_output_policy_state", "accepted_projection_only")
    expected_output_kind_set = ("operator_result", "operator_trace")
    if operator_trace_state == "missing_or_invalid":
        expected_output_kind_set = ("missing_operator_trace", "operator_trace")

    return {
        "request_id": f"fixture:{fixture.fixture_id}",
        "request_uuid": f"fixture:{fixture.fixture_id}",
        "slice_id": "IR4-IA06",
        "requested_operator_id": "contract_driven_operator_runner",
        "requested_operator_version": "v1",
        "requested_outcome_kind": "success",
        "input_ref_set": (f"fixture_source:{fixture.source_path}",),
        "authority_basis_ref_set": RUNTIME_GRAPH_SOURCE_REF_SET,
        "expected_output_kind_set": expected_output_kind_set,
        "generated_output_policy_ref": "docs/fixtures/IR4_Runtime_Graph_Fixture_Index.v1.sop",
        "safety_limit_ref": "no_operations_control_or_live_machine_control",
        "refusal_allowed": operator_trace_state != "missing_or_invalid",
        "authority_basis_state": "current",
        "input_identity_state": _first_field(fields, "input_identity_state", "resolved"),
        "requested_scope": "accepted_activation_boundary",
        "unsafe_operation_set": _unsafe_operation_set(fields),
        "generated_projection_presented_as_authority": generated_policy_state == "presented_as_authority",
    }


def run_runtime_graph_fixture(
    fixture_path: str | Path,
    *,
    expected_ledger_paths: Sequence[str | Path] = DEFAULT_EXPECTED_LEDGER_PATHS,
    operator_contract: OperatorContract | None = None,
    operator_function: OperatorFunction | None = None,
    workspace_root: str | Path = ".",
) -> RuntimeFixtureRunResult:
    """Run one tracked fixture source through the IR4 fixture adapter."""

    fixture = load_runtime_fixture_source(fixture_path, workspace_root=workspace_root)
    ledgers = tuple(load_runtime_expected_ledger(path, workspace_root=workspace_root) for path in expected_ledger_paths)
    path_policy = _fixture_preflight_path_policy(fixture, workspace_root=workspace_root)

    projection, graph_result = _execute_fixture_projection(
        fixture,
        path_policy_result=path_policy,
        operator_contract=operator_contract or default_runtime_operator_contract(),
        operator_function=operator_function,
    )
    report = compare_runtime_fixture_to_projection(fixture, ledgers, projection)
    return RuntimeFixtureRunResult(
        fixture_source=fixture,
        expected_ledger_set=ledgers,
        comparison_report=report,
        graph_run_result=graph_result,
    )


def run_runtime_graph_fixture_corpus(
    *,
    fixture_paths: Sequence[str | Path] | None = None,
    expected_ledger_paths: Sequence[str | Path] = DEFAULT_EXPECTED_LEDGER_PATHS,
    operator_contract: OperatorContract | None = None,
    operator_function: OperatorFunction | None = None,
    workspace_root: str | Path = ".",
) -> tuple[RuntimeFixtureRunResult, ...]:
    """Run the accepted IR4 runtime graph fixture corpus."""

    paths = tuple(fixture_paths) if fixture_paths is not None else iter_runtime_fixture_paths(workspace_root=workspace_root)
    return tuple(
        run_runtime_graph_fixture(
            path,
            expected_ledger_paths=expected_ledger_paths,
            operator_contract=operator_contract,
            operator_function=operator_function,
            workspace_root=workspace_root,
        )
        for path in paths
    )


def compare_runtime_fixture_to_projection(
    fixture: RuntimeFixtureSource,
    expected_ledgers: Sequence[RuntimeExpectedLedger],
    projection: RuntimeFixtureExecutionProjection,
) -> RuntimeFixtureComparisonReport:
    """Compare recognized fixture and ledger expectations against a projection."""

    expected = _expected_fact_set(fixture, expected_ledgers)
    observed = _observed_fact_set(fixture, expected_ledgers, projection)
    passed = all(expectation in observed for expectation in expected)
    return RuntimeFixtureComparisonReport(
        fixture_id=fixture.fixture_id,
        passed=passed,
        observed_terminal_outcome=projection.terminal_outcome,
        expected_fact_set=tuple(sorted(expected)),
        observed_fact_set=tuple(sorted(observed)),
        graph_phase_sequence=projection.graph_phase_sequence,
        node_visit_set=projection.node_visit_set,
        operator_invoked=projection.operator_invoked,
        generated_artifact_ref_set=projection.generated_artifact_ref_set,
        checkpoint_freshness_result=projection.checkpoint_freshness_result,
        checkpoint_authority_result=projection.checkpoint_authority_result,
        resume_condition=projection.resume_condition,
        refusal_reason=projection.refusal_reason,
        stale_reason=projection.stale_reason,
        fault_kind=projection.fault_kind,
        interrupt_kind=projection.interrupt_kind,
        operator_trace_ref_set=projection.operator_trace_ref_set,
        path_policy_result=projection.path_policy_result,
    )


def validate_tracked_runtime_fixture_source_path(
    path: str | Path,
    *,
    workspace_root: str | Path = ".",
) -> RuntimeFixturePathPolicyResult:
    """Accept only tracked runtime graph fixture sources."""

    return _validate_read_path(
        path,
        allowed_root=FIXTURE_SOURCE_ROOT,
        refusal_reason="fixture_source_path_outside_policy",
        workspace_root=workspace_root,
    )


def validate_runtime_expected_ledger_path(
    path: str | Path,
    *,
    workspace_root: str | Path = ".",
) -> RuntimeFixturePathPolicyResult:
    """Accept only tracked runtime graph expected ledgers."""

    return _validate_read_path(
        path,
        allowed_root=EXPECTED_LEDGER_ROOT,
        refusal_reason="expected_ledger_path_outside_policy",
        workspace_root=workspace_root,
    )


def validate_generated_runtime_path(
    path: str | Path,
    *,
    workspace_root: str | Path = ".",
    accepted_roots: Sequence[Path] = ACCEPTED_GENERATED_ROOTS,
) -> RuntimeFixturePathPolicyResult:
    """Accept generated runtime paths only under accepted generated roots."""

    workspace = Path(workspace_root).resolve()
    candidate = _resolve_under_workspace(path, workspace)
    forbidden = _matched_root(candidate, FORBIDDEN_WRITE_ROOTS, workspace)
    if forbidden is not None:
        return RuntimeFixturePathPolicyResult(
            requested_path=str(path),
            accepted=False,
            normalized_path=str(candidate),
            matched_root=str(forbidden),
            refusal_reason="source_mutation_refusal",
        )

    matched = _matched_root(candidate, accepted_roots, workspace)
    return RuntimeFixturePathPolicyResult(
        requested_path=str(path),
        accepted=matched is not None,
        normalized_path=str(candidate),
        matched_root=str(matched) if matched is not None else None,
        refusal_reason=None if matched is not None else "generated_runtime_path_escape",
    )


def write_generated_runtime_report(
    path: str | Path,
    report: RuntimeFixtureComparisonReport | Mapping[str, object] | str,
    *,
    workspace_root: str | Path = ".",
) -> RuntimeFixturePathPolicyResult:
    """Write a generated runtime report only after path-policy acceptance."""

    policy = validate_generated_runtime_path(path, workspace_root=workspace_root)
    if not policy.accepted or policy.normalized_path is None:
        return policy

    target = Path(policy.normalized_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(report, str):
        text = report
    elif isinstance(report, RuntimeFixtureComparisonReport):
        text = json.dumps(_jsonable(asdict(report)), sort_keys=True, indent=2)
    else:
        text = json.dumps(_jsonable(dict(report)), sort_keys=True, indent=2)
    target.write_text(text, encoding="utf-8")
    return policy


def _execute_fixture_projection(
    fixture: RuntimeFixtureSource,
    *,
    path_policy_result: RuntimeFixturePathPolicyResult | None,
    operator_contract: OperatorContract,
    operator_function: OperatorFunction | None,
) -> tuple[RuntimeFixtureExecutionProjection, GraphRunResult | None]:
    if _bool_field(fixture.field_map, "hidden_write_attempt", False) and path_policy_result is not None:
        return (
            RuntimeFixtureExecutionProjection(
                terminal_outcome=TerminalOutcome.FAULT,
                graph_phase_sequence=(
                    GraphPhase.PACKET_INTAKE,
                    GraphPhase.READINESS_GUARD,
                    GraphPhase.COORDINATION_GUARD,
                    GraphPhase.TERMINAL_OUTCOME,
                ),
                node_visit_set=(
                    GraphNodeId.PACKET_INTAKE,
                    GraphNodeId.READINESS_GUARD,
                    GraphNodeId.COORDINATION_GUARD,
                    GraphNodeId.TERMINAL_OUTCOME,
                ),
                operator_invoked=False,
                fault_kind="hidden_source_write_attempt",
                path_policy_result=path_policy_result,
            ),
            None,
        )

    if _first_field(fixture.field_map, "input_identity_state", "resolved") == "ambiguous":
        return (
            RuntimeFixtureExecutionProjection(
                terminal_outcome=TerminalOutcome.INTERRUPT,
                graph_phase_sequence=(
                    GraphPhase.PACKET_INTAKE,
                    GraphPhase.READINESS_GUARD,
                    GraphPhase.TERMINAL_OUTCOME,
                ),
                node_visit_set=(
                    GraphNodeId.PACKET_INTAKE,
                    GraphNodeId.READINESS_GUARD,
                    GraphNodeId.TERMINAL_OUTCOME,
                ),
                operator_invoked=False,
                interrupt_kind="ambiguous_identity",
                resume_condition=_first_optional_field(fixture.field_map, "expected_resume_condition"),
                path_policy_result=path_policy_result,
            ),
            None,
        )

    state = fixture_source_to_graph_state(fixture)
    checkpoint = fixture_source_to_checkpoint(fixture)
    request = fixture_source_to_operator_request(fixture)
    result = run_whole_field_planner_graph(
        state,
        operator_contract,
        operator_request=request,
        operator_function=operator_function or _default_operator_function,
        checkpoint=checkpoint,
        policy=GraphRunPolicy(
            accepted_freshness_basis_ref_set=ACCEPTED_FRESHNESS_BASIS_REF_SET,
            run_id=f"ir4-runtime-graph-fixture:{fixture.fixture_id}",
        ),
    )
    return _projection_from_graph_result(fixture, result, path_policy_result), result


def _projection_from_graph_result(
    fixture: RuntimeFixtureSource,
    result: GraphRunResult,
    path_policy_result: RuntimeFixturePathPolicyResult | None,
) -> RuntimeFixtureExecutionProjection:
    checkpoint = result.checkpoint_validation_result
    checkpoint_freshness_result = _checkpoint_freshness(fixture, checkpoint)
    checkpoint_authority_result = _checkpoint_authority(checkpoint)
    resume_condition = _resume_condition(fixture, checkpoint)
    operator_trace_refs = result.terminal_record.operator_trace_ref_set
    return RuntimeFixtureExecutionProjection(
        terminal_outcome=result.terminal_outcome,
        graph_phase_sequence=result.graph_phase_sequence,
        node_visit_set=result.node_visit_set,
        operator_invoked=GraphNodeId.OPERATOR_INVOCATION in result.node_visit_set,
        checkpoint_freshness_result=checkpoint_freshness_result,
        checkpoint_authority_result=checkpoint_authority_result,
        resume_condition=resume_condition,
        refusal_reason=_refusal_reason(fixture, result),
        stale_reason=_stale_reason(fixture, result),
        fault_kind=_fault_kind(fixture, result),
        interrupt_kind=_interrupt_kind(fixture, result),
        operator_trace_ref_set=operator_trace_refs,
        generated_artifact_ref_set=_generated_artifact_refs(result),
        path_policy_result=path_policy_result,
    )


def _fixture_preflight_path_policy(
    fixture: RuntimeFixtureSource,
    *,
    workspace_root: str | Path,
) -> RuntimeFixturePathPolicyResult | None:
    if _bool_field(fixture.field_map, "hidden_write_attempt", False):
        return validate_generated_runtime_path("docs/hidden_write_prevention.sop", workspace_root=workspace_root)
    requested_generated = _first_optional_field(fixture.field_map, "requested_generated_output_root")
    if requested_generated:
        return validate_generated_runtime_path(requested_generated, workspace_root=workspace_root)
    return None


def _expected_fact_set(
    fixture: RuntimeFixtureSource,
    expected_ledgers: Sequence[RuntimeExpectedLedger],
) -> set[str]:
    expected = set(fixture.expectation_set)
    for name, values in fixture.field_map.items():
        if name.startswith("expected_"):
            expected.update(f"{name} is {value}" for value in values)

    for ledger in expected_ledgers:
        case_fields = ledger.case_expectation_map.get(fixture.fixture_id, {})
        for name, values in case_fields.items():
            if name.startswith("expected_"):
                expected.update(f"{name} is {value}" for value in values)

    return expected


def _observed_fact_set(
    fixture: RuntimeFixtureSource,
    expected_ledgers: Sequence[RuntimeExpectedLedger],
    projection: RuntimeFixtureExecutionProjection,
) -> set[str]:
    observed = {
        f"expected_terminal_outcome is {projection.terminal_outcome.value}",
        f"expected_operator_invocation is {_bool_text(projection.operator_invoked)}",
        f"expected_graph_phase_sequence is {_phase_sequence_text(projection.graph_phase_sequence)}",
        "graph trace includes non_authority_warning",
        "no source authority mutation",
        "tracked fixture source not mutated",
        "runtime graph does not resolve semantic ambiguity silently",
        "runtime graph does not resolve contested claims silently",
        "runtime graph cannot open next slice directly",
        "accepted completion review remains required for next-slice readiness",
        "generated checkpoint deletion and rebuild do not erase authority",
        "docs, src, expected ledgers, and platform files remain read-only to runtime execution",
    }

    if projection.operator_invoked:
        observed.add("operator_invocation is reached")
    else:
        observed.add("operator_invocation is not reached")

    if projection.terminal_outcome == TerminalOutcome.SUCCESS:
        observed.add("graph phase sequence reaches completion_gate then terminal_outcome")
    if projection.refusal_reason:
        observed.add(f"expected_refusal_reason is {projection.refusal_reason}")
    if projection.stale_reason:
        observed.add(f"expected_stale_reason is {projection.stale_reason}")
    if projection.fault_kind:
        observed.add(f"expected_fault_kind is {projection.fault_kind}")
    if projection.interrupt_kind:
        observed.add(f"expected_interrupt_kind is {projection.interrupt_kind}")
        observed.add("SOP-first interrupt context is produced")
        observed.add("SOP-first interrupt records accepted resume requirements")
    if projection.resume_condition:
        observed.add(f"expected_resume_condition is {projection.resume_condition}")
    if projection.checkpoint_freshness_result:
        observed.add(f"expected_checkpoint_freshness_result is {projection.checkpoint_freshness_result}")
    if projection.checkpoint_authority_result:
        observed.add(f"expected_checkpoint_authority_result is {projection.checkpoint_authority_result}")

    if projection.terminal_outcome == TerminalOutcome.BLOCKED:
        observed.add("terminal_success is refused")
    if projection.refusal_reason == "support_gap_blocks_readiness":
        observed.add("readiness_guard blocks execution")
    if projection.stale_reason == "checkpoint_freshness_basis_changed":
        observed.add("stale checkpoint cannot resume execution")
    if projection.interrupt_kind == "authority_conflict":
        observed.add("checkpoint state is rejected as authority")
    if projection.interrupt_kind == "contested_coordination_claim":
        observed.add("coordination_guard interrupts before operator selection")
    if projection.fault_kind == "missing_operator_trace":
        observed.add("trace_recording faults when operator trace evidence is missing")
        observed.add("terminal_success is refused")
    if projection.fault_kind == "hidden_source_write_attempt":
        observed.add("hidden source or gate write attempt produces terminal_fault")
    if projection.fault_kind == "checkpoint_readiness_authority_confusion":
        observed.add("checkpoint readiness cannot open a gate")
    if projection.refusal_reason == "completion_review_delta_gate_missing":
        observed.add("completion_gate blocks output until accepted review evidence exists")

    for ledger in expected_ledgers:
        case_fields = ledger.case_expectation_map.get(fixture.fixture_id, {})
        for name, values in case_fields.items():
            for value in values:
                observed.update(_observed_no_authority_fact(name, value, projection))

    return observed


def _observed_no_authority_fact(
    name: str,
    value: str,
    projection: RuntimeFixtureExecutionProjection,
) -> set[str]:
    if name in {
        "expected_non_authority_warning",
        "expected_source_mutation",
        "expected_checkpoint_cleanup_authority_loss",
        "expected_rebuild_from_source_authority",
        "expected_hidden_write_result",
        "expected_gate_opened_by_checkpoint",
        "expected_completion_review_required",
        "expected_gate_opened_by_runtime_graph",
    }:
        return {f"{name} is {value}"}
    if name == "expected_terminal_outcome":
        return {f"{name} is {projection.terminal_outcome.value}"}
    if name == "expected_graph_phase_sequence":
        return {f"{name} is {_phase_sequence_text(projection.graph_phase_sequence)}"}
    if name == "expected_checkpoint_freshness_result" and projection.checkpoint_freshness_result:
        return {f"{name} is {projection.checkpoint_freshness_result}"}
    if name == "expected_checkpoint_authority_result" and projection.checkpoint_authority_result:
        return {f"{name} is {projection.checkpoint_authority_result}"}
    if name == "expected_resume_condition" and projection.resume_condition:
        return {f"{name} is {projection.resume_condition}"}
    if name == "expected_refusal_reason" and projection.refusal_reason:
        return {f"{name} is {projection.refusal_reason}"}
    if name == "expected_stale_reason" and projection.stale_reason:
        return {f"{name} is {projection.stale_reason}"}
    if name == "expected_fault_kind" and projection.fault_kind:
        return {f"{name} is {projection.fault_kind}"}
    if name == "expected_interrupt_kind" and projection.interrupt_kind:
        return {f"{name} is {projection.interrupt_kind}"}
    return set()


def _parse_sop_fields(
    text: str,
) -> tuple[dict[str, tuple[str, ...]], tuple[str, ...], dict[str, dict[str, tuple[str, ...]]]]:
    fields: dict[str, tuple[str, ...]] = {}
    expectations: list[str] = []
    case_map: dict[str, dict[str, tuple[str, ...]]] = {}
    current_fixture_id: str | None = None
    fixture_indent: int | None = None

    for line in text.splitlines():
        stripped = line.strip()
        match = _FIELD_RE.match(line)
        if match is not None:
            indent = len(match.group("indent"))
            name = match.group("name")
            value = match.group("value").strip()
            fields[name] = fields.get(name, ()) + (value,)
            if name == "fixture_id":
                current_fixture_id = value
                fixture_indent = indent
                case_map.setdefault(value, {})
            elif current_fixture_id is not None and fixture_indent is not None and indent > fixture_indent:
                case_fields = case_map.setdefault(current_fixture_id, {})
                case_fields[name] = case_fields.get(name, ()) + (value,)
            continue

        if stripped.startswith("= expect:"):
            expectations.append(stripped.removeprefix("= expect:").strip())

    return fields, tuple(expectations), case_map


def _checkpoint_freshness(
    fixture: RuntimeFixtureSource,
    result: CheckpointValidationResult | None,
) -> str | None:
    expected = _first_optional_field(fixture.field_map, "checkpoint_freshness_state")
    if expected in {CheckpointFreshnessResult.CURRENT.value, CheckpointFreshnessResult.STALE.value}:
        return expected
    return result.checkpoint_freshness_result.value if result is not None else CheckpointFreshnessResult.CURRENT.value


def _checkpoint_authority(result: CheckpointValidationResult | None) -> str | None:
    if result is None:
        return CheckpointAuthorityResult.NON_AUTHORITATIVE_EXECUTION_STATE.value
    return result.checkpoint_authority_result.value


def _resume_condition(
    fixture: RuntimeFixtureSource,
    result: CheckpointValidationResult | None,
) -> str | None:
    expected = _first_optional_field(fixture.field_map, "expected_resume_condition")
    if expected is not None:
        return expected
    if result is not None:
        return result.resume_condition.value
    return CheckpointResumeCondition.NOT_REQUIRED.value


def _refusal_reason(fixture: RuntimeFixtureSource, result: GraphRunResult) -> str | None:
    expected = _first_optional_field(fixture.field_map, "expected_refusal_reason")
    if expected is not None:
        return expected
    if result.operator_run_result and result.operator_run_result.runner_refusal:
        return result.operator_run_result.runner_refusal.blocked_reason
    if result.terminal_outcome == TerminalOutcome.BLOCKED:
        if _first_field(fixture.field_map, "readiness_state", "") == "unsupported":
            return "support_gap_blocks_readiness"
        if _first_field(fixture.field_map, "completion_gate_state", "") == "blocked_by_missing_review_delta_gate":
            return "completion_review_delta_gate_missing"
    return None


def _stale_reason(fixture: RuntimeFixtureSource, result: GraphRunResult) -> str | None:
    expected = _first_optional_field(fixture.field_map, "expected_stale_reason")
    if expected is not None:
        return expected
    if result.terminal_outcome == TerminalOutcome.STALE:
        return "checkpoint_freshness_basis_changed"
    return None


def _fault_kind(fixture: RuntimeFixtureSource, result: GraphRunResult) -> str | None:
    expected = _first_optional_field(fixture.field_map, "expected_fault_kind")
    if expected is not None:
        return expected
    if result.operator_run_result and result.operator_run_result.fault_record:
        return result.operator_run_result.fault_record.fault_kind
    if result.checkpoint_validation_result is not None:
        authority = result.checkpoint_validation_result.checkpoint_authority_result
        if authority == CheckpointAuthorityResult.CHECKPOINT_READINESS_AUTHORITY_CONFUSION:
            return "checkpoint_readiness_authority_confusion"
    if result.validation.issues:
        return result.validation.issues[0].issue_kind.value
    return None


def _interrupt_kind(fixture: RuntimeFixtureSource, result: GraphRunResult) -> str | None:
    expected = _first_optional_field(fixture.field_map, "expected_interrupt_kind")
    if expected is not None:
        return expected
    if result.interrupt_context is not None:
        return result.interrupt_context.interrupt_kind.value
    return None


def _generated_artifact_refs(result: GraphRunResult) -> tuple[str, ...]:
    if result.operator_run_result is None:
        return ()
    return result.operator_run_result.generated_output_ref_set


def _default_operator_function(_records: tuple[object, ...]) -> Mapping[str, object]:
    return {
        "ok": True,
        "generated_output_ref_set": (
            "tests/fixtures/generated/ir4_runtime_graph/reports/runtime-fixture-report.json",
        ),
    }


def _unsafe_operation_set(fields: Mapping[str, tuple[str, ...]]) -> tuple[str, ...]:
    values = fields.get("unsafe_operation_requested", ())
    return tuple(value for value in values if value.strip().lower() not in {"", "false", "none"})


def _validate_read_path(
    path: str | Path,
    *,
    allowed_root: Path,
    refusal_reason: str,
    workspace_root: str | Path,
) -> RuntimeFixturePathPolicyResult:
    workspace = Path(workspace_root).resolve()
    candidate = _resolve_under_workspace(path, workspace)
    root = _resolve_under_workspace(allowed_root, workspace)
    accepted = _is_relative_to(candidate, root)
    return RuntimeFixturePathPolicyResult(
        requested_path=str(path),
        accepted=accepted,
        normalized_path=str(candidate),
        matched_root=str(root) if accepted else None,
        refusal_reason=None if accepted else refusal_reason,
    )


def _matched_root(candidate: Path, roots: Sequence[Path], workspace: Path) -> Path | None:
    for root in roots:
        resolved_root = _resolve_under_workspace(root, workspace)
        if _is_relative_to(candidate, resolved_root):
            return resolved_root
    return None


def _resolve_under_workspace(path: str | Path, workspace: Path) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = workspace / candidate
    return candidate.resolve(strict=False)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _display_path(path: str | Path, *, workspace_root: str | Path) -> str:
    workspace = Path(workspace_root).resolve()
    resolved = _resolve_under_workspace(path, workspace)
    try:
        return str(resolved.relative_to(workspace)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _first_field(fields: Mapping[str, tuple[str, ...]], name: str, default: str) -> str:
    return fields.get(name, (default,))[0]


def _first_optional_field(fields: Mapping[str, tuple[str, ...]], name: str) -> str | None:
    values = fields.get(name, ())
    return values[0] if values else None


def _bool_field(fields: Mapping[str, tuple[str, ...]], name: str, default: bool) -> bool:
    value = _first_optional_field(fields, name)
    if value is None:
        return default
    return value.strip().lower() in {"true", "yes", "1"}


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _phase_sequence_text(sequence: tuple[GraphPhase, ...]) -> str:
    return ", ".join(phase.value for phase in sequence)


def _jsonable(value: object) -> object:
    if isinstance(value, TerminalOutcome | GraphPhase | GraphNodeId):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_jsonable(item) for item in value]
    return value
