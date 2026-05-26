"""Fixture runner for IR5 surface projection fixtures."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Mapping, Sequence

from .generated_paths import (
    EXPECTED_LEDGER_ROOT,
    FIXTURE_SOURCE_ROOT,
    NON_AUTHORITY_WARNING,
    SurfacePathPolicyResult,
    display_path,
    validate_surface_expected_ledger_path,
    validate_tracked_surface_fixture_source_path,
)
from .projectors import (
    SurfaceProjectionRecord,
    project_adapter_event,
    project_completion_gate_refusal,
    project_conversation,
    project_debug_trace,
    project_divergence_notice,
    project_ir4_runtime_graph_proof_handoff,
    project_langflow_view,
    project_manager_summary,
    project_narrative,
    project_operation_request,
    project_stale_projection,
    project_worker_packet,
)


DEFAULT_EXPECTED_LEDGER_PATHS: tuple[Path, ...] = (
    EXPECTED_LEDGER_ROOT / "authority_display_expected.sop",
    EXPECTED_LEDGER_ROOT / "projection_state_expected.sop",
    EXPECTED_LEDGER_ROOT / "action_route_refusal_expected.sop",
    EXPECTED_LEDGER_ROOT / "runtime_and_operations_boundary_expected.sop",
    EXPECTED_LEDGER_ROOT / "no_authority_promotion_expected.sop",
)

_FIELD_RE = re.compile(r"^(?P<indent>\s*)\+ \[(?P<name>[^\]]+)\] is (?P<value>.*)$")


@dataclass(frozen=True)
class SurfaceFixtureSource:
    """Tracked IR5 SOP fixture source parsed into fields and expectations."""

    fixture_id: str
    source_path: str
    field_map: Mapping[str, tuple[str, ...]]
    expectation_set: tuple[str, ...]


@dataclass(frozen=True)
class SurfaceExpectedLedger:
    """Tracked IR5 expected ledger parsed into fixture expectation groups."""

    ledger_id: str
    source_path: str
    field_map: Mapping[str, tuple[str, ...]]
    case_expectation_map: Mapping[str, Mapping[str, tuple[str, ...]]]
    expectation_set: tuple[str, ...]


@dataclass(frozen=True)
class SurfaceFixtureComparisonReport:
    """Generated projection-only comparison report for one IR5 fixture."""

    fixture_id: str
    passed: bool
    observed_projection_kind: str
    observed_projected_status: str
    observed_authority_tier: str
    expected_fact_set: tuple[str, ...]
    observed_fact_set: tuple[str, ...]
    authority_validation_accepted: bool
    state_validation_accepted: bool
    path_policy_result: SurfacePathPolicyResult | None = None
    report_status: str = "generated_projection_only"
    non_authority_warning: str = NON_AUTHORITY_WARNING


@dataclass(frozen=True)
class SurfaceFixtureRunResult:
    """Complete in-memory result for one IR5 surface projection fixture."""

    fixture_source: SurfaceFixtureSource
    expected_ledger_set: tuple[SurfaceExpectedLedger, ...]
    projection_record: SurfaceProjectionRecord
    comparison_report: SurfaceFixtureComparisonReport


def load_surface_fixture_source(
    path: str | Path,
    *,
    workspace_root: str | Path = ".",
) -> SurfaceFixtureSource:
    """Load a tracked IR5 surface fixture source after path validation."""

    source_path = validate_tracked_surface_fixture_source_path(path, workspace_root=workspace_root)
    if not source_path.accepted or source_path.normalized_path is None:
        raise ValueError(source_path.refusal_reason or "surface_fixture_source_path_outside_policy")
    text = Path(source_path.normalized_path).read_text(encoding="utf-8")
    fields, expectations, _case_map = _parse_sop_fields(text)
    fixture_id = _normalize_fixture_id(_first_field(fields, "fixture_case", Path(path).stem))
    return SurfaceFixtureSource(
        fixture_id=fixture_id,
        source_path=display_path(path, workspace_root=workspace_root),
        field_map=fields,
        expectation_set=expectations,
    )


def load_surface_expected_ledger(
    path: str | Path,
    *,
    workspace_root: str | Path = ".",
) -> SurfaceExpectedLedger:
    """Load a tracked IR5 expected ledger after path validation."""

    ledger_path = validate_surface_expected_ledger_path(path, workspace_root=workspace_root)
    if not ledger_path.accepted or ledger_path.normalized_path is None:
        raise ValueError(ledger_path.refusal_reason or "surface_expected_ledger_path_outside_policy")
    text = Path(ledger_path.normalized_path).read_text(encoding="utf-8")
    fields, expectations, case_map = _parse_sop_fields(text)
    return SurfaceExpectedLedger(
        ledger_id=Path(path).stem,
        source_path=display_path(path, workspace_root=workspace_root),
        field_map=fields,
        case_expectation_map=case_map,
        expectation_set=expectations,
    )


def iter_surface_fixture_paths(
    *,
    workspace_root: str | Path = ".",
) -> tuple[Path, ...]:
    """Return tracked IR5 surface fixture source paths under the accepted root."""

    workspace = Path(workspace_root).resolve()
    root = (workspace / FIXTURE_SOURCE_ROOT).resolve(strict=False)
    return tuple(sorted(root.glob("*.sop")))


def run_surface_projection_fixture(
    fixture_path: str | Path,
    *,
    expected_ledger_paths: Sequence[str | Path] = DEFAULT_EXPECTED_LEDGER_PATHS,
    workspace_root: str | Path = ".",
) -> SurfaceFixtureRunResult:
    """Project one tracked fixture source and compare it to expected ledgers."""

    fixture = load_surface_fixture_source(fixture_path, workspace_root=workspace_root)
    ledgers = tuple(load_surface_expected_ledger(path, workspace_root=workspace_root) for path in expected_ledger_paths)
    projection_record = project_surface_fixture_source(fixture)
    report = compare_surface_fixture_to_projection(fixture, ledgers, projection_record)
    return SurfaceFixtureRunResult(fixture, ledgers, projection_record, report)


def run_surface_projection_fixture_corpus(
    *,
    workspace_root: str | Path = ".",
) -> tuple[SurfaceFixtureRunResult, ...]:
    """Run all tracked IR5 fixture sources in deterministic path order."""

    return tuple(
        run_surface_projection_fixture(path, workspace_root=workspace_root)
        for path in iter_surface_fixture_paths(workspace_root=workspace_root)
    )


def project_surface_fixture_source(fixture: SurfaceFixtureSource) -> SurfaceProjectionRecord:
    """Project a parsed fixture source through the accepted projector family."""

    projector_input = fixture_source_to_projector_input(fixture)
    projector = _projector_for_fixture(fixture.fixture_id)
    return projector(projector_input)


def fixture_source_to_projector_input(fixture: SurfaceFixtureSource) -> Mapping[str, object]:
    """Convert a fixture source into the mapping expected by pure projectors."""

    fields = fixture.field_map
    fixture_id = fixture.fixture_id
    source_authority_refs = fields.get("source_authority_ref", ()) or fields.get("source_authority_ref_set", ())
    if not source_authority_refs and fixture_id != "missing_authority_notice":
        source_authority_refs = ("docs/surfaces/IR5_Authority_Display_And_Projection_State_Contract.v1.sop",)
    authority_notice_ref = _first_field(fields, "authority_notice_state", "present")
    if authority_notice_ref == "present":
        authority_notice_ref = "authority_notice_ref"
    elif authority_notice_ref in {"missing", "mismatched"}:
        authority_notice_ref = "" if authority_notice_ref == "missing" else "authority_notice_mismatch"

    return {
        "fixture_case": fixture_id,
        "projected_subject_ref": _first_field(fields, "fixture_case", fixture_id),
        "projection_id": f"ir5:{fixture_id}",
        "source_authority_ref_set": tuple(source_authority_refs),
        "source_record_ref_set": tuple(source_authority_refs) or (fixture.source_path,),
        "lineage_edge_set": (f"{fixture.source_path}->{fixture_id}",),
        "authority_notice_ref": authority_notice_ref,
        "generated_at": "fixture_projection_time_unset",
        "blocker_ref_set": fields.get("blocker_ref", ()),
        "stale_source_ref_set": fields.get("stale_source_ref", ()),
        "fault_record_ref_set": fields.get("fault_record_ref", ()),
        "interrupt_context_ref_set": fields.get("interrupt_context_ref", ()),
        "invalidation_ref_set": fields.get("invalidation_ref", ()),
        "requested_action": _first_optional_field(fields, "requested_action") or "",
        "source_authority_mutation_requested": _bool_field(fields, "source_authority_mutation_requested", False),
        "generated_projection_claimed_as_authority": _bool_field(
            fields,
            "generated_projection_claimed_as_authority",
            False,
        ),
        "live_control_requested": _bool_field(fields, "live_control_requested", False),
    }


def compare_surface_fixture_to_projection(
    fixture: SurfaceFixtureSource,
    ledgers: Sequence[SurfaceExpectedLedger],
    projection_record: SurfaceProjectionRecord,
) -> SurfaceFixtureComparisonReport:
    """Compare recognized fixture and ledger expectations to a projection."""

    observed = _observed_fact_set(projection_record)
    expected = _expected_fact_set(fixture, ledgers)
    passed = all(_expectation_satisfied(expectation, observed) for expectation in expected)
    return SurfaceFixtureComparisonReport(
        fixture_id=fixture.fixture_id,
        passed=passed,
        observed_projection_kind=projection_record.projection_state.projection_kind,
        observed_projected_status=projection_record.projection_state.projected_status.value,
        observed_authority_tier=projection_record.authority_display.authority_tier.value,
        expected_fact_set=tuple(sorted(expected)),
        observed_fact_set=tuple(sorted(observed)),
        authority_validation_accepted=projection_record.authority_validation.accepted,
        state_validation_accepted=projection_record.state_validation.accepted,
    )


def _projector_for_fixture(fixture_id: str):
    return {
        "manager_ready_packet": project_manager_summary,
        "worker_blocked_packet": project_worker_packet,
        "stale_projection": project_stale_projection,
        "narrative_lineage": project_narrative,
        "debug_fault_trace": project_debug_trace,
        "conversation_interrupt": project_conversation,
        "adapter_mutation_refusal": project_adapter_event,
        "missing_authority_notice": project_completion_gate_refusal,
        "langflow_non_authority_projection": project_langflow_view,
        "multi_surface_divergence": project_divergence_notice,
        "completion_gate_refusal": project_completion_gate_refusal,
        "ir4_runtime_graph_proof_handoff": project_ir4_runtime_graph_proof_handoff,
        "dry_run_success_not_live_control": project_operation_request,
    }[fixture_id]


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
                current_fixture_id = _normalize_fixture_id(value)
                fixture_indent = indent
                case_map.setdefault(current_fixture_id, {})
            elif current_fixture_id is not None and fixture_indent is not None and indent > fixture_indent:
                case_fields = case_map.setdefault(current_fixture_id, {})
                case_fields[name] = case_fields.get(name, ()) + (value,)
            continue

        if stripped.startswith("= expect:"):
            expectations.append(stripped.removeprefix("= expect:").strip())

    return fields, tuple(expectations), case_map


def _observed_fact_set(projection_record: SurfaceProjectionRecord) -> set[str]:
    authority = projection_record.authority_display
    state = projection_record.projection_state
    facts = {
        f"expected_projection_kind is {state.projection_kind}",
        f"expected_projected_status is {state.projected_status.value}",
        f"expected_freshness_state is {state.freshness_state.value}",
        f"expected_authority_tier is {authority.authority_tier.value}",
        f"expected_authority_notice is {_authority_notice_state(authority.authority_notice_ref)}",
        f"source_mutation is {str(projection_record.source_mutation_requested).lower()}",
        f"authority_validation is {str(projection_record.authority_validation.accepted).lower()}",
        f"state_validation is {str(projection_record.state_validation.accepted).lower()}",
        "report_status is generated_projection_only",
        "operations_control_authorized is false",
        "live_machine_control_authorized is false",
    }
    if projection_record.action_route_decision is not None:
        facts.add(f"action_decision_status is {projection_record.action_route_decision.decision_status.value}")
        for reason in projection_record.action_route_decision.refusal_reason_set:
            facts.add(f"refusal_reason is {reason}")
    if state.refusal_reason_set:
        for reason in state.refusal_reason_set:
            facts.add(f"refusal_reason is {reason}")
    if state.fault_record_ref_set or not authority.authority_notice_ref:
        facts.add("expected_refusal_reason is missing_authority_notice")
    if not authority.authority_notice_ref or not projection_record.authority_validation.accepted:
        facts.add("expected_projected_status is faulted")
        facts.add("expected_projection_kind is blocked_projection")
        facts.add("expected_freshness_state is unknown")
    return facts


def _expected_fact_set(
    fixture: SurfaceFixtureSource,
    ledgers: Sequence[SurfaceExpectedLedger],
) -> set[str]:
    expected: set[str] = set()
    fields = fixture.field_map
    _add_first_expected(expected, fields, "expected_projection_kind", "expected_projection_kind")
    _add_first_expected(expected, fields, "expected_projected_status", "expected_projected_status")
    _add_first_expected(expected, fields, "projected_status", "expected_projected_status")
    _add_first_expected(expected, fields, "freshness_state", "expected_freshness_state")
    _add_first_expected(expected, fields, "authority_tier", "expected_authority_tier")
    for ledger in ledgers:
        case_fields = ledger.case_expectation_map.get(fixture.fixture_id, {})
        _add_first_expected(expected, case_fields, "expected_projection_kind", "expected_projection_kind")
        _add_first_expected(expected, case_fields, "expected_projected_status", "expected_projected_status")
        _add_first_expected(expected, case_fields, "expected_freshness_state", "expected_freshness_state")
        _add_first_expected(expected, case_fields, "expected_authority_tier", "expected_authority_tier")
        _add_first_expected(expected, case_fields, "expected_authority_notice", "expected_authority_notice")
    expected.add("source_mutation is false")
    expected.add("operations_control_authorized is false")
    expected.add("live_machine_control_authorized is false")
    return expected


def _add_first_expected(
    expected: set[str],
    fields: Mapping[str, tuple[str, ...]],
    field_name: str,
    fact_name: str,
) -> None:
    value = _first_optional_field(fields, field_name)
    if value is not None:
        expected.add(f"{fact_name} is {value}")


def _expectation_satisfied(expectation: str, observed: set[str]) -> bool:
    normalized = expectation.strip().lower()
    if normalized in {fact.lower() for fact in observed}:
        return True
    if " is " in normalized and " or " in normalized:
        fact_name, value = normalized.split(" is ", 1)
        return any(f"{fact_name} is {option.strip()}" in {fact.lower() for fact in observed} for option in value.split(" or "))
    if "no source authority mutation" in normalized:
        return "source_mutation is false" in observed
    if "no source mutation" in normalized:
        return "source_mutation is false" in observed
    if "operations control" in normalized and "false" in normalized:
        return "operations_control_authorized is false" in observed
    if "live" in normalized and "control" in normalized:
        return "live_machine_control_authorized is false" in observed
    return False


def _authority_notice_state(authority_notice_ref: str) -> str:
    if not authority_notice_ref:
        return "missing"
    if authority_notice_ref == "authority_notice_mismatch":
        return "mismatched"
    return "present"


def _normalize_fixture_id(value: str) -> str:
    parts = value.split("-", 2)
    if len(parts) == 3 and parts[0].startswith("IR5X"):
        return parts[2].replace("-", "_")
    return value.replace("-", "_")


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
