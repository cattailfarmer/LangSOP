"""Fixture runner utilities for the bounded IR3 operator harness.

This module keeps tracked fixture sources and generated outputs separated. It
loads reviewed fixture material, validates generated paths, runs in-process
operator fixtures through the pure runner, and returns comparison reports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Mapping, Sequence

from .contracts import OperatorContract, OutcomeKind
from .runner import OperatorFunction, OperatorRunResult, run_contract_operator
from .traces import NON_AUTHORITY_WARNING, build_generated_output_manifest


FIXTURE_SOURCE_ROOT = Path("tests/fixtures/sop/ir3_operator_harness")
EXPECTED_LEDGER_ROOT = Path("tests/fixtures/expected/ir3_operator_harness")
ACCEPTED_GENERATED_ROOTS: tuple[Path, ...] = (
    Path("tests/fixtures/generated/ir3_operator_harness"),
    Path(".langsop/traces/ir3_operator_harness"),
    Path(".langsop/reports/ir3_operator_harness"),
    Path(".langsop/fixtures/ir3_operator_harness"),
)
FORBIDDEN_WRITE_ROOTS: tuple[Path, ...] = (
    Path("docs"),
    Path("src"),
    Path("platform"),
    Path(".git"),
    FIXTURE_SOURCE_ROOT,
    EXPECTED_LEDGER_ROOT,
)


@dataclass(frozen=True)
class FixturePathPolicyResult:
    """Result of validating a requested generated-output path."""

    requested_path: str
    accepted: bool
    normalized_path: str | None = None
    matched_root: str | None = None
    refusal_reason: str | None = None
    non_authority_warning: str = NON_AUTHORITY_WARNING


@dataclass(frozen=True)
class FixtureSource:
    """Tracked SOP fixture source parsed into fields and expectations."""

    fixture_id: str
    source_path: str
    field_map: Mapping[str, tuple[str, ...]]
    expectation_set: tuple[str, ...]


@dataclass(frozen=True)
class ExpectedLedger:
    """Tracked expected ledger parsed into reviewable fields."""

    ledger_id: str
    source_path: str
    field_map: Mapping[str, tuple[str, ...]]


@dataclass(frozen=True)
class FixtureComparisonReport:
    """Generated projection report for a fixture run or path refusal."""

    fixture_id: str
    passed: bool
    observed_outcome_kind: OutcomeKind
    expected_fact_set: tuple[str, ...]
    observed_fact_set: tuple[str, ...]
    generated_artifact_ref_set: tuple[str, ...] = ()
    path_policy_result: FixturePathPolicyResult | None = None
    operator_trace_ref: str | None = None
    runner_refusal_reason: str | None = None
    fault_kind: str | None = None
    interrupt_kind: str | None = None
    report_status: str = "generated_projection_only"
    non_authority_warning: str = NON_AUTHORITY_WARNING


@dataclass(frozen=True)
class FixtureRunResult:
    """Complete result for one fixture source."""

    fixture_source: FixtureSource
    expected_ledger_set: tuple[ExpectedLedger, ...]
    comparison_report: FixtureComparisonReport
    operator_run_result: OperatorRunResult | None = None


def default_operator_contract() -> OperatorContract:
    """Return the accepted IR3 contract metadata used by fixture conversion."""

    return OperatorContract(
        operator_id="contract_driven_operator_runner",
        operator_version="v1",
        output_record_kind_set=frozenset(
            {
                "operator_result",
                "operator_trace",
                "readiness_projection",
                "work_packet",
                "support_gap",
                "stale_projection",
                "proof_result",
                "fault_record",
                "sop_first_interrupt",
                "generated_output_manifest",
            }
        ),
    )


def load_fixture_source(
    path: str | Path,
    *,
    workspace_root: str | Path = ".",
) -> FixtureSource:
    """Load a tracked fixture source after validating its read boundary."""

    source_path = validate_tracked_fixture_source_path(path, workspace_root=workspace_root)
    text = Path(source_path.normalized_path or path).read_text(encoding="utf-8")
    fields, expectations = _parse_sop_fields(text)
    fixture_id = _first_field(fields, "fixture_case", Path(path).stem)
    return FixtureSource(
        fixture_id=fixture_id,
        source_path=str(path),
        field_map=fields,
        expectation_set=expectations,
    )


def load_expected_ledger(
    path: str | Path,
    *,
    workspace_root: str | Path = ".",
) -> ExpectedLedger:
    """Load a tracked expected ledger after validating its read boundary."""

    ledger_path = validate_expected_ledger_path(path, workspace_root=workspace_root)
    text = Path(ledger_path.normalized_path or path).read_text(encoding="utf-8")
    fields, _expectations = _parse_sop_fields(text)
    return ExpectedLedger(
        ledger_id=Path(path).stem,
        source_path=str(path),
        field_map=fields,
    )


def fixture_source_to_request(fixture: FixtureSource) -> Mapping[str, object]:
    """Convert a tracked fixture source into an operator runner request."""

    fields = fixture.field_map
    output_kind = _first_field(fields, "requested_output_kind", "operator_result")
    unsafe = tuple(
        value
        for value in fields.get("unsafe_operation_requested", ())
        if value.strip().lower() not in {"", "false", "none"}
    )
    return {
        "request_id": f"fixture:{fixture.fixture_id}",
        "request_uuid": f"fixture:{fixture.fixture_id}",
        "slice_id": "IR3-IA05",
        "requested_operator_id": _first_field(fields, "requested_operator_id", "contract_driven_operator_runner"),
        "requested_operator_version": _first_field(fields, "requested_operator_version", "v1"),
        "requested_outcome_kind": _first_field(fields, "requested_outcome_kind", "success"),
        "input_ref_set": (f"fixture_source:{fixture.source_path}",),
        "authority_basis_ref_set": (
            "docs/operators/IR3_Contract_Driven_Operator_Runner_And_Trace_Contract.v1.sop",
        ),
        "expected_output_kind_set": (output_kind, "operator_trace"),
        "generated_output_policy_ref": "docs/fixtures/IR3_Fixture_Runner_IO_And_Generated_Trace_Policy.v1.sop",
        "safety_limit_ref": "no_live_operations_control",
        "refusal_allowed": _bool_field(fields, "refusal_allowed", True),
        "authority_basis_state": _first_field(fields, "authority_basis_state", "current"),
        "input_identity_state": _first_field(fields, "input_identity_state", "resolved"),
        "requested_scope": _first_field(fields, "requested_scope", "accepted_activation_boundary"),
        "unsafe_operation_set": unsafe,
        "generated_projection_presented_as_authority": _bool_field(
            fields,
            "generated_projection_presented_as_authority",
            False,
        ),
    }


def run_operator_fixture(
    fixture_path: str | Path,
    *,
    expected_ledger_paths: Sequence[str | Path] = (),
    contract: OperatorContract | None = None,
    operator_function: OperatorFunction | None = None,
    workspace_root: str | Path = ".",
) -> FixtureRunResult:
    """Run one fixture source through path policy checks and the pure runner."""

    fixture = load_fixture_source(fixture_path, workspace_root=workspace_root)
    ledgers = tuple(load_expected_ledger(path, workspace_root=workspace_root) for path in expected_ledger_paths)

    path_policy = _fixture_preflight_path_policy(fixture, workspace_root=workspace_root)
    if path_policy is not None and not path_policy.accepted:
        return _preflight_refusal_result(fixture, ledgers, path_policy)

    mismatch = _deterministic_replay_mismatch(fixture)
    if mismatch is not None:
        return _preflight_fault_result(fixture, ledgers, "deterministic_replay_mismatch", mismatch)

    request = fixture_source_to_request(fixture)
    run_result = run_contract_operator(
        request,
        contract or default_operator_contract(),
        operator_function=operator_function,
        source_ref_set=(f"fixture_source:{fixture.source_path}",),
    )
    report = compare_fixture_to_result(fixture, run_result, path_policy_result=path_policy)
    return FixtureRunResult(
        fixture_source=fixture,
        expected_ledger_set=ledgers,
        comparison_report=report,
        operator_run_result=run_result,
    )


def compare_fixture_to_result(
    fixture: FixtureSource,
    run_result: OperatorRunResult,
    *,
    path_policy_result: FixturePathPolicyResult | None = None,
) -> FixtureComparisonReport:
    """Compare recognized fixture expectations against a runner result."""

    observed = _observed_fact_set(run_result, path_policy_result)
    expected = fixture.expectation_set
    passed = all(_expectation_satisfied(expectation, observed) for expectation in expected)
    return FixtureComparisonReport(
        fixture_id=fixture.fixture_id,
        passed=passed,
        observed_outcome_kind=run_result.outcome_kind,
        expected_fact_set=expected,
        observed_fact_set=tuple(sorted(observed)),
        generated_artifact_ref_set=run_result.generated_output_ref_set,
        path_policy_result=path_policy_result,
        operator_trace_ref=run_result.operator_trace.trace_id,
        runner_refusal_reason=run_result.runner_refusal.blocked_reason if run_result.runner_refusal else None,
        fault_kind=run_result.fault_record.fault_kind if run_result.fault_record else None,
        interrupt_kind=run_result.sop_first_interrupt.interrupt_kind if run_result.sop_first_interrupt else None,
    )


def validate_tracked_fixture_source_path(
    path: str | Path,
    *,
    workspace_root: str | Path = ".",
) -> FixturePathPolicyResult:
    """Accept only tracked fixture source files under the fixture source root."""

    return _validate_read_path(
        path,
        allowed_root=FIXTURE_SOURCE_ROOT,
        refusal_reason="fixture_source_path_outside_policy",
        workspace_root=workspace_root,
    )


def validate_expected_ledger_path(
    path: str | Path,
    *,
    workspace_root: str | Path = ".",
) -> FixturePathPolicyResult:
    """Accept only tracked expected ledgers under the expected ledger root."""

    return _validate_read_path(
        path,
        allowed_root=EXPECTED_LEDGER_ROOT,
        refusal_reason="expected_ledger_path_outside_policy",
        workspace_root=workspace_root,
    )


def validate_generated_output_path(
    path: str | Path,
    *,
    workspace_root: str | Path = ".",
    accepted_roots: Sequence[Path] = ACCEPTED_GENERATED_ROOTS,
) -> FixturePathPolicyResult:
    """Accept generated output paths only under accepted generated roots."""

    workspace = Path(workspace_root).resolve()
    candidate = _resolve_under_workspace(path, workspace)
    forbidden = _matched_root(candidate, FORBIDDEN_WRITE_ROOTS, workspace)
    if forbidden is not None:
        return FixturePathPolicyResult(
            requested_path=str(path),
            accepted=False,
            normalized_path=str(candidate),
            matched_root=str(forbidden),
            refusal_reason="source_mutation_refusal",
        )

    matched = _matched_root(candidate, accepted_roots, workspace)
    return FixturePathPolicyResult(
        requested_path=str(path),
        accepted=matched is not None,
        normalized_path=str(candidate),
        matched_root=str(matched) if matched is not None else None,
        refusal_reason=None if matched is not None else "generated_output_path_escape",
    )


def write_generated_output(
    path: str | Path,
    content: Mapping[str, object] | str,
    *,
    workspace_root: str | Path = ".",
) -> FixturePathPolicyResult:
    """Write a generated projection only after path-policy acceptance."""

    policy = validate_generated_output_path(path, workspace_root=workspace_root)
    if not policy.accepted or policy.normalized_path is None:
        return policy

    target = Path(policy.normalized_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, str):
        text = content
    else:
        text = json.dumps(content, sort_keys=True, indent=2)
    target.write_text(text, encoding="utf-8")
    return policy


def build_fixture_manifest(
    *,
    manifest_id: str,
    generated_output_root: str,
    generated_output_ref_set: Sequence[str],
) -> object:
    """Build a non-authoritative generated-output manifest for fixtures."""

    return build_generated_output_manifest(
        manifest_id=manifest_id,
        generated_output_root=generated_output_root,
        generated_output_ref_set=tuple(generated_output_ref_set),
    )


def _parse_sop_fields(text: str) -> tuple[dict[str, tuple[str, ...]], tuple[str, ...]]:
    fields: dict[str, tuple[str, ...]] = {}
    expectations: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("+ [") and "] is " in stripped:
            name, value = stripped[3:].split("] is ", 1)
            fields[name] = fields.get(name, ()) + (value.strip(),)
        elif stripped.startswith("= expect:"):
            expectations.append(stripped.removeprefix("= expect:").strip())
    return fields, tuple(expectations)


def _fixture_preflight_path_policy(
    fixture: FixtureSource,
    *,
    workspace_root: str | Path,
) -> FixturePathPolicyResult | None:
    fields = fixture.field_map
    requested_generated = _first_optional_field(fields, "requested_generated_output_root")
    if requested_generated:
        return validate_generated_output_path(requested_generated, workspace_root=workspace_root)
    requested_write = _first_optional_field(fields, "requested_write_root")
    if requested_write:
        return validate_generated_output_path(requested_write, workspace_root=workspace_root)
    return None


def _preflight_refusal_result(
    fixture: FixtureSource,
    ledgers: tuple[ExpectedLedger, ...],
    path_policy: FixturePathPolicyResult,
) -> FixtureRunResult:
    observed = {
        "blocked_refusal",
        path_policy.refusal_reason or "path_policy_refusal",
        "no generated trace written",
        "no operator_result produced",
    }
    report = FixtureComparisonReport(
        fixture_id=fixture.fixture_id,
        passed=all(_expectation_satisfied(expectation, observed) for expectation in fixture.expectation_set),
        observed_outcome_kind=OutcomeKind.BLOCKED_OUTPUT,
        expected_fact_set=fixture.expectation_set,
        observed_fact_set=tuple(sorted(observed)),
        path_policy_result=path_policy,
        runner_refusal_reason=path_policy.refusal_reason,
    )
    return FixtureRunResult(fixture, ledgers, report)


def _preflight_fault_result(
    fixture: FixtureSource,
    ledgers: tuple[ExpectedLedger, ...],
    fault_kind: str,
    reason: str,
) -> FixtureRunResult:
    observed = {"fault_output", f"fault_code is {fault_kind}", reason}
    report = FixtureComparisonReport(
        fixture_id=fixture.fixture_id,
        passed=all(_expectation_satisfied(expectation, observed) for expectation in fixture.expectation_set),
        observed_outcome_kind=OutcomeKind.FAULT_OUTPUT,
        expected_fact_set=fixture.expectation_set,
        observed_fact_set=tuple(sorted(observed)),
        fault_kind=fault_kind,
    )
    return FixtureRunResult(fixture, ledgers, report)


def _observed_fact_set(
    run_result: OperatorRunResult,
    path_policy_result: FixturePathPolicyResult | None,
) -> set[str]:
    observed = {run_result.outcome_kind.value}
    if run_result.operator_result is not None:
        observed.add("operator_result produced")
    else:
        observed.add("no operator_result produced")
    if run_result.operator_trace is not None:
        observed.add("operator_trace produced with non_authority_warning")
    if run_result.runner_refusal is not None:
        observed.add("blocked_refusal")
        observed.add(run_result.runner_refusal.blocked_reason)
        observed.add(f"refusal_reason is {run_result.runner_refusal.blocked_reason}")
        observed.add(f"required_resolution is {run_result.runner_refusal.required_resolution}")
    if run_result.fault_record is not None:
        observed.add("fault_output")
        observed.add(run_result.fault_record.fault_kind)
        observed.add(f"fault_code is {run_result.fault_record.fault_kind}")
    if run_result.sop_first_interrupt is not None:
        observed.add("sop_first_interrupt")
        observed.add(run_result.sop_first_interrupt.interrupt_kind)
        observed.add(f"interrupt_kind is {run_result.sop_first_interrupt.interrupt_kind}")
    if path_policy_result is not None and not path_policy_result.accepted:
        observed.add(path_policy_result.refusal_reason or "path_policy_refusal")
    return observed


def _expectation_satisfied(expectation: str, observed: set[str]) -> bool:
    if expectation in observed:
        return True
    if expectation == "operator_trace produced with non_authority_warning":
        return expectation in observed
    if expectation == "tracked fixture source not mutated":
        return "source_mutation_refusal" in observed
    if expectation == "required_resolution is supply accepted operator contract version":
        return "missing_contract_version" in observed
    if expectation == "no dispatch output":
        return "unsupported_operations_control" in observed
    if expectation == "no generated trace written":
        return "generated_output_path_escape" in observed or "source_mutation_refusal" in observed
    return False


def _deterministic_replay_mismatch(fixture: FixtureSource) -> str | None:
    replay_identity = _first_optional_field(fixture.field_map, "replay_identity_state")
    replay_outcome = _first_optional_field(fixture.field_map, "observed_replay_outcome")
    if replay_identity == "unchanged" and replay_outcome == "changed":
        return "unchanged replay identity produced changed outcome"
    return None


def _validate_read_path(
    path: str | Path,
    *,
    allowed_root: Path,
    refusal_reason: str,
    workspace_root: str | Path,
) -> FixturePathPolicyResult:
    workspace = Path(workspace_root).resolve()
    candidate = _resolve_under_workspace(path, workspace)
    root = _resolve_under_workspace(allowed_root, workspace)
    accepted = _is_relative_to(candidate, root)
    return FixturePathPolicyResult(
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
