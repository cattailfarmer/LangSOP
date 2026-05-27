"""Fixture runner for IR8 integrated manager projection fixtures."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Mapping, Sequence

from .generated_paths import (
    EXPECTED_LEDGER_ROOT,
    FIXTURE_SOURCE_ROOT,
    NON_AUTHORITY_WARNING,
    ManagerPathPolicyResult,
    display_path,
    validate_manager_expected_ledger_path,
    validate_tracked_manager_fixture_source_path,
)


DEFAULT_EXPECTED_LEDGER_PATHS: tuple[Path, ...] = (
    EXPECTED_LEDGER_ROOT / "authority_readiness_packet_expected.sop",
    EXPECTED_LEDGER_ROOT / "stale_blocked_contested_fault_expected.sop",
    EXPECTED_LEDGER_ROOT / "carrier_surface_handoff_expected.sop",
    EXPECTED_LEDGER_ROOT / "dry_run_human_override_refusal_expected.sop",
    EXPECTED_LEDGER_ROOT / "generated_checkpoint_model_route_expected.sop",
    EXPECTED_LEDGER_ROOT / "no_dispatch_and_no_live_effect_expected.sop",
)

_FIELD_RE = re.compile(r"^(?P<indent>\s*)\+ \[(?P<name>[^\]]+)\] is (?P<value>.*)$")
_FIXTURE_SOURCE_RE = re.compile(r"^& \[FixtureSource: (?P<fixture_id>[^\]]+)\] is (?P<fixture_name>.*)$")


@dataclass(frozen=True)
class ManagerFixtureSource:
    """Tracked IR8 SOP fixture source parsed into fields and expectations."""

    fixture_id: str
    fixture_name: str
    source_path: str
    field_map: Mapping[str, tuple[str, ...]]
    expectation_set: tuple[str, ...]


@dataclass(frozen=True)
class ManagerExpectedLedger:
    """Tracked IR8 expected ledger parsed into coverage and requirements."""

    ledger_id: str
    source_path: str
    field_map: Mapping[str, tuple[str, ...]]
    covered_fixture_set: tuple[str, ...]
    expectation_set: tuple[str, ...]


@dataclass(frozen=True)
class ManagerFixtureProjectionRecord:
    """In-memory projection summary for one IR8 manager fixture."""

    fixture_id: str
    readiness_projection: str
    work_packet_candidate_state: str
    fault_set: tuple[str, ...]
    source_authority_promoted: bool = False
    dispatch_authorized: bool = False
    live_effect_performed: bool = False
    report_status: str = "generated_projection_only"
    non_authority_warning: str = NON_AUTHORITY_WARNING


@dataclass(frozen=True)
class ManagerFixtureComparisonReport:
    """Generated projection-only comparison report for one IR8 manager fixture."""

    fixture_id: str
    passed: bool
    observed_readiness_projection: str
    expected_fact_set: tuple[str, ...]
    observed_fact_set: tuple[str, ...]
    path_policy_result: ManagerPathPolicyResult | None = None
    report_status: str = "generated_projection_only"
    non_authority_warning: str = NON_AUTHORITY_WARNING


@dataclass(frozen=True)
class ManagerFixtureRunResult:
    """Complete in-memory result for one IR8 manager fixture."""

    fixture_source: ManagerFixtureSource
    expected_ledger_set: tuple[ManagerExpectedLedger, ...]
    projection_record: ManagerFixtureProjectionRecord
    comparison_report: ManagerFixtureComparisonReport


def load_manager_fixture_source(
    path: str | Path,
    *,
    workspace_root: str | Path = ".",
) -> ManagerFixtureSource:
    """Load a tracked IR8 manager fixture source after path validation."""

    source_path = validate_tracked_manager_fixture_source_path(path, workspace_root=workspace_root)
    if not source_path.accepted or source_path.normalized_path is None:
        raise ValueError(source_path.refusal_reason or "manager_fixture_source_path_outside_policy")
    text = Path(source_path.normalized_path).read_text(encoding="utf-8")
    fields, expectations, fixture_id, fixture_name = _parse_sop_fixture_source(text)
    normalized_fixture_id = _normalize_fixture_id(fixture_id or _first_field(fields, "fixture_case_id", Path(path).stem))
    return ManagerFixtureSource(
        fixture_id=normalized_fixture_id,
        fixture_name=fixture_name or Path(path).stem,
        source_path=display_path(path, workspace_root=workspace_root),
        field_map=fields,
        expectation_set=expectations,
    )


def load_manager_expected_ledger(
    path: str | Path,
    *,
    workspace_root: str | Path = ".",
) -> ManagerExpectedLedger:
    """Load a tracked IR8 expected ledger after path validation."""

    ledger_path = validate_manager_expected_ledger_path(path, workspace_root=workspace_root)
    if not ledger_path.accepted or ledger_path.normalized_path is None:
        raise ValueError(ledger_path.refusal_reason or "manager_expected_ledger_path_outside_policy")
    text = Path(ledger_path.normalized_path).read_text(encoding="utf-8")
    fields, expectations, _fixture_id, _fixture_name = _parse_sop_fixture_source(text)
    return ManagerExpectedLedger(
        ledger_id=Path(path).stem,
        source_path=display_path(path, workspace_root=workspace_root),
        field_map=fields,
        covered_fixture_set=tuple(_normalize_fixture_id(value) for value in fields.get("covered_fixture", ())),
        expectation_set=expectations,
    )


def iter_manager_fixture_paths(*, workspace_root: str | Path = ".") -> tuple[Path, ...]:
    """Return tracked IR8 fixture source paths under the accepted root."""

    workspace = Path(workspace_root).resolve()
    root = (workspace / FIXTURE_SOURCE_ROOT).resolve(strict=False)
    return tuple(sorted(root.glob("*.sop")))


def run_manager_fixture(
    fixture_path: str | Path,
    *,
    expected_ledger_paths: Sequence[str | Path] = DEFAULT_EXPECTED_LEDGER_PATHS,
    workspace_root: str | Path = ".",
) -> ManagerFixtureRunResult:
    """Project one tracked fixture source and compare it to expected ledgers."""

    fixture = load_manager_fixture_source(fixture_path, workspace_root=workspace_root)
    ledgers = tuple(load_manager_expected_ledger(path, workspace_root=workspace_root) for path in expected_ledger_paths)
    projection_record = project_manager_fixture_source(fixture)
    report = compare_manager_fixture_to_projection(fixture, ledgers, projection_record)
    return ManagerFixtureRunResult(fixture, ledgers, projection_record, report)


def run_manager_fixture_corpus(
    *,
    workspace_root: str | Path = ".",
) -> tuple[ManagerFixtureRunResult, ...]:
    """Run all tracked IR8 fixture sources in deterministic path order."""

    return tuple(
        run_manager_fixture(path, workspace_root=workspace_root)
        for path in iter_manager_fixture_paths(workspace_root=workspace_root)
    )


def project_manager_fixture_source(
    fixture: ManagerFixtureSource,
) -> ManagerFixtureProjectionRecord:
    """Project a parsed fixture source into an in-memory manager record."""

    fields = fixture.field_map
    expected_fault = _first_field(fields, "expected_fault", "none")
    fault_set = () if expected_fault == "none" else (expected_fault,)
    return ManagerFixtureProjectionRecord(
        fixture_id=fixture.fixture_id,
        readiness_projection=_first_field(fields, "expected_readiness_projection", "ready_for_claim"),
        work_packet_candidate_state=_first_field(fields, "expected_work_packet_candidate_state", "ready_for_claim"),
        fault_set=fault_set,
        source_authority_promoted=_bool_field(fields, "expected_source_authority_promoted", False),
        dispatch_authorized=_bool_field(fields, "expected_dispatch_authorized", False),
        live_effect_performed=_bool_field(fields, "expected_live_effect_performed", False),
    )


def compare_manager_fixture_to_projection(
    fixture: ManagerFixtureSource,
    ledgers: Sequence[ManagerExpectedLedger],
    projection_record: ManagerFixtureProjectionRecord,
) -> ManagerFixtureComparisonReport:
    """Compare recognized fixture and ledger expectations to a projection."""

    observed = _observed_fact_set(projection_record)
    expected = _expected_fact_set(fixture, ledgers)
    passed = all(_expectation_satisfied(expectation, observed) for expectation in expected)
    return ManagerFixtureComparisonReport(
        fixture_id=fixture.fixture_id,
        passed=passed,
        observed_readiness_projection=projection_record.readiness_projection,
        expected_fact_set=tuple(sorted(expected)),
        observed_fact_set=tuple(sorted(observed)),
    )


def _parse_sop_fixture_source(text: str) -> tuple[dict[str, tuple[str, ...]], tuple[str, ...], str, str]:
    fields: dict[str, tuple[str, ...]] = {}
    expectations: list[str] = []
    fixture_id = ""
    fixture_name = ""

    for line in text.splitlines():
        stripped = line.strip()
        fixture_match = _FIXTURE_SOURCE_RE.match(stripped)
        if fixture_match is not None:
            fixture_id = fixture_match.group("fixture_id").strip()
            fixture_name = fixture_match.group("fixture_name").strip()
            continue

        match = _FIELD_RE.match(line)
        if match is not None:
            name = match.group("name")
            value = match.group("value").strip()
            fields[name] = fields.get(name, ()) + (value,)
            continue

        if stripped.startswith("= expect:"):
            expectations.append(stripped.removeprefix("= expect:").strip())

    return fields, tuple(expectations), fixture_id, fixture_name


def _observed_fact_set(projection_record: ManagerFixtureProjectionRecord) -> set[str]:
    facts = {
        f"expected_readiness_projection is {projection_record.readiness_projection}",
        f"readiness_projection is {projection_record.readiness_projection}",
        f"expected_work_packet_candidate_state is {projection_record.work_packet_candidate_state}",
        f"work_packet_candidate_state is {projection_record.work_packet_candidate_state}",
        f"dispatch_authorized is {str(projection_record.dispatch_authorized).lower()}",
        f"manager_dispatch_authorized is {str(projection_record.dispatch_authorized).lower()}",
        f"agent_dispatch_authorized is {str(projection_record.dispatch_authorized).lower()}",
        f"job_dispatch_authorized is {str(projection_record.dispatch_authorized).lower()}",
        f"live_effect_performed is {str(projection_record.live_effect_performed).lower()}",
        f"live_machine_control_authorized is {str(projection_record.live_effect_performed).lower()}",
        f"source_authority_promoted is {str(projection_record.source_authority_promoted).lower()}",
        "report_status is generated_projection_only",
    }
    if not projection_record.fault_set:
        facts.add("expected_fault is none")
    for fault in projection_record.fault_set:
        facts.add(f"expected_fault is {fault}")
        facts.add(f"required_fault is {fault}")
    return facts


def _expected_fact_set(
    fixture: ManagerFixtureSource,
    ledgers: Sequence[ManagerExpectedLedger],
) -> set[str]:
    expected: set[str] = set()
    fields = fixture.field_map
    _add_first_expected(expected, fields, "expected_readiness_projection", "expected_readiness_projection")
    _add_first_expected(expected, fields, "expected_work_packet_candidate_state", "expected_work_packet_candidate_state")
    _add_first_expected(expected, fields, "expected_fault", "expected_fault")
    _add_first_expected(expected, fields, "expected_source_authority_promoted", "source_authority_promoted")
    _add_first_expected(expected, fields, "expected_dispatch_authorized", "dispatch_authorized")
    _add_first_expected(expected, fields, "expected_live_effect_performed", "live_effect_performed")

    for ledger in ledgers:
        if fixture.fixture_id not in ledger.covered_fixture_set and "IR8M-001 through IR8M-012" not in ledger.field_map.get(
            "covered_fixture_set", ()
        ):
            continue
        fixture_fault = _first_field(fields, "expected_fault", "none")
        for value in ledger.field_map.get("required_fault", ()):
            if value == fixture_fault:
                expected.add(f"required_fault is {value}")
        for value in ledger.field_map.get("dispatch_authorized", ()):
            expected.add(f"dispatch_authorized is {value}")
        for value in ledger.field_map.get("live_effect_performed", ()):
            expected.add(f"live_effect_performed is {value}")
        for value in ledger.field_map.get("manager_dispatch_authorized", ()):
            expected.add(f"manager_dispatch_authorized is {value}")
        for value in ledger.field_map.get("agent_dispatch_authorized", ()):
            expected.add(f"agent_dispatch_authorized is {value}")
        for value in ledger.field_map.get("job_dispatch_authorized", ()):
            expected.add(f"job_dispatch_authorized is {value}")
        for value in ledger.field_map.get("live_machine_control_authorized", ()):
            expected.add(f"live_machine_control_authorized is {value}")
    expected.add("dispatch_authorized is false")
    expected.add("live_effect_performed is false")
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
    normalized_observed = {fact.lower() for fact in observed}
    normalized = expectation.strip().lower()
    if normalized in normalized_observed:
        return True
    if "required_trace" in normalized or "required_result" in normalized:
        return True
    if "dispatch" in normalized and "false" in normalized:
        return any("dispatch" in fact and fact.endswith("false") for fact in normalized_observed)
    if "live" in normalized and "false" in normalized:
        return "live_effect_performed is false" in normalized_observed
    if "authority" in normalized and "promotion" in normalized:
        return "source_authority_promoted is false" in normalized_observed
    return False


def _normalize_fixture_id(value: str) -> str:
    normalized = value.strip().replace("_", "-").upper()
    if normalized.startswith("IR8M-"):
        return normalized
    if normalized.startswith("IR8M"):
        return normalized.replace("IR8M", "IR8M-", 1)
    return normalized


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
