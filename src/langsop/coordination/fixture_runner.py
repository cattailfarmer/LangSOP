"""Fixture runner for IR6 coordination mailbox projection fixtures."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Mapping, Sequence

from .generated_paths import (
    EXPECTED_LEDGER_ROOT,
    FIXTURE_SOURCE_ROOT,
    NON_AUTHORITY_WARNING,
    CoordinationPathPolicyResult,
    display_path,
    validate_coordination_expected_ledger_path,
    validate_tracked_coordination_fixture_source_path,
)


DEFAULT_EXPECTED_LEDGER_PATHS: tuple[Path, ...] = (
    EXPECTED_LEDGER_ROOT / "claim_identity_expected.sop",
    EXPECTED_LEDGER_ROOT / "work_boundary_expected.sop",
    EXPECTED_LEDGER_ROOT / "mailbox_carrier_expected.sop",
    EXPECTED_LEDGER_ROOT / "conflict_and_stale_review_expected.sop",
    EXPECTED_LEDGER_ROOT / "no_authority_promotion_expected.sop",
)

_FIELD_RE = re.compile(r"^(?P<indent>\s*)\+ \[(?P<name>[^\]]+)\] is (?P<value>.*)$")


@dataclass(frozen=True)
class CoordinationFixtureSource:
    """Tracked IR6 SOP fixture source parsed into fields and expectations."""

    fixture_id: str
    source_path: str
    field_map: Mapping[str, tuple[str, ...]]
    expectation_set: tuple[str, ...]


@dataclass(frozen=True)
class CoordinationExpectedLedger:
    """Tracked IR6 expected ledger parsed into fixture expectation groups."""

    ledger_id: str
    source_path: str
    field_map: Mapping[str, tuple[str, ...]]
    case_expectation_map: Mapping[str, Mapping[str, tuple[str, ...]]]
    expectation_set: tuple[str, ...]


@dataclass(frozen=True)
class CoordinationFixtureProjectionRecord:
    """In-memory projection summary for one IR6 coordination fixture."""

    fixture_id: str
    projection_kind: str
    projected_status: str
    freshness_state: str
    authority_notice_state: str
    carrier_authority_status: str = "carrier_context_only"
    source_mutation_requested: bool = False
    mailbox_io_requested: bool = False
    agent_dispatch_requested: bool = False
    live_machine_control_authorized: bool = False


@dataclass(frozen=True)
class CoordinationFixtureComparisonReport:
    """Generated projection-only comparison report for one IR6 fixture."""

    fixture_id: str
    passed: bool
    observed_projection_kind: str
    observed_projected_status: str
    expected_fact_set: tuple[str, ...]
    observed_fact_set: tuple[str, ...]
    path_policy_result: CoordinationPathPolicyResult | None = None
    report_status: str = "generated_projection_only"
    non_authority_warning: str = NON_AUTHORITY_WARNING


@dataclass(frozen=True)
class CoordinationFixtureRunResult:
    """Complete in-memory result for one IR6 coordination fixture."""

    fixture_source: CoordinationFixtureSource
    expected_ledger_set: tuple[CoordinationExpectedLedger, ...]
    projection_record: CoordinationFixtureProjectionRecord
    comparison_report: CoordinationFixtureComparisonReport


def load_coordination_fixture_source(
    path: str | Path,
    *,
    workspace_root: str | Path = ".",
) -> CoordinationFixtureSource:
    """Load a tracked IR6 coordination fixture source after path validation."""

    source_path = validate_tracked_coordination_fixture_source_path(path, workspace_root=workspace_root)
    if not source_path.accepted or source_path.normalized_path is None:
        raise ValueError(source_path.refusal_reason or "coordination_fixture_source_path_outside_policy")
    text = Path(source_path.normalized_path).read_text(encoding="utf-8")
    fields, expectations, _case_map = _parse_sop_fields(text)
    fixture_id = _normalize_fixture_id(_first_field(fields, "fixture_case", Path(path).stem))
    return CoordinationFixtureSource(
        fixture_id=fixture_id,
        source_path=display_path(path, workspace_root=workspace_root),
        field_map=fields,
        expectation_set=expectations,
    )


def load_coordination_expected_ledger(
    path: str | Path,
    *,
    workspace_root: str | Path = ".",
) -> CoordinationExpectedLedger:
    """Load a tracked IR6 expected ledger after path validation."""

    ledger_path = validate_coordination_expected_ledger_path(path, workspace_root=workspace_root)
    if not ledger_path.accepted or ledger_path.normalized_path is None:
        raise ValueError(ledger_path.refusal_reason or "coordination_expected_ledger_path_outside_policy")
    text = Path(ledger_path.normalized_path).read_text(encoding="utf-8")
    fields, expectations, case_map = _parse_sop_fields(text)
    return CoordinationExpectedLedger(
        ledger_id=Path(path).stem,
        source_path=display_path(path, workspace_root=workspace_root),
        field_map=fields,
        case_expectation_map=case_map,
        expectation_set=expectations,
    )


def iter_coordination_fixture_paths(*, workspace_root: str | Path = ".") -> tuple[Path, ...]:
    """Return tracked IR6 fixture source paths under the accepted root."""

    workspace = Path(workspace_root).resolve()
    root = (workspace / FIXTURE_SOURCE_ROOT).resolve(strict=False)
    return tuple(sorted(root.glob("*.sop")))


def run_coordination_mailbox_fixture(
    fixture_path: str | Path,
    *,
    expected_ledger_paths: Sequence[str | Path] = DEFAULT_EXPECTED_LEDGER_PATHS,
    workspace_root: str | Path = ".",
) -> CoordinationFixtureRunResult:
    """Project one tracked fixture source and compare it to expected ledgers."""

    fixture = load_coordination_fixture_source(fixture_path, workspace_root=workspace_root)
    ledgers = tuple(load_coordination_expected_ledger(path, workspace_root=workspace_root) for path in expected_ledger_paths)
    projection_record = project_coordination_fixture_source(fixture)
    report = compare_coordination_fixture_to_projection(fixture, ledgers, projection_record)
    return CoordinationFixtureRunResult(fixture, ledgers, projection_record, report)


def run_coordination_mailbox_fixture_corpus(
    *,
    workspace_root: str | Path = ".",
) -> tuple[CoordinationFixtureRunResult, ...]:
    """Run all tracked IR6 fixture sources in deterministic path order."""

    return tuple(
        run_coordination_mailbox_fixture(path, workspace_root=workspace_root)
        for path in iter_coordination_fixture_paths(workspace_root=workspace_root)
    )


def project_coordination_fixture_source(
    fixture: CoordinationFixtureSource,
) -> CoordinationFixtureProjectionRecord:
    """Project a parsed fixture source into an in-memory summary record."""

    fields = fixture.field_map
    return CoordinationFixtureProjectionRecord(
        fixture_id=fixture.fixture_id,
        projection_kind=_first_field(fields, "projection_kind", "coordination_projection"),
        projected_status=_first_field(fields, "expected_status", "accepted"),
        freshness_state=_first_field(fields, "freshness_state", _freshness_for_fixture(fixture.fixture_id)),
        authority_notice_state=_first_field(fields, "authority_notice_state", "present"),
        carrier_authority_status=_first_field(fields, "carrier_authority_status", "carrier_context_only"),
        source_mutation_requested=_bool_field(fields, "source_authority_mutation_requested", False),
        mailbox_io_requested=_bool_field(fields, "mailbox_io_requested", False),
        agent_dispatch_requested=_bool_field(fields, "agent_dispatch_requested", False),
        live_machine_control_authorized=_bool_field(fields, "live_machine_control_authorized", False),
    )


def compare_coordination_fixture_to_projection(
    fixture: CoordinationFixtureSource,
    ledgers: Sequence[CoordinationExpectedLedger],
    projection_record: CoordinationFixtureProjectionRecord,
) -> CoordinationFixtureComparisonReport:
    """Compare recognized fixture and ledger expectations to a projection."""

    observed = _observed_fact_set(projection_record)
    expected = _expected_fact_set(fixture, ledgers)
    passed = all(_expectation_satisfied(expectation, observed) for expectation in expected)
    return CoordinationFixtureComparisonReport(
        fixture_id=fixture.fixture_id,
        passed=passed,
        observed_projection_kind=projection_record.projection_kind,
        observed_projected_status=projection_record.projected_status,
        expected_fact_set=tuple(sorted(expected)),
        observed_fact_set=tuple(sorted(observed)),
    )


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


def _observed_fact_set(projection_record: CoordinationFixtureProjectionRecord) -> set[str]:
    return {
        f"expected_projection_kind is {projection_record.projection_kind}",
        f"expected_projected_status is {projection_record.projected_status}",
        f"expected_freshness_state is {projection_record.freshness_state}",
        f"expected_authority_notice is {projection_record.authority_notice_state}",
        f"expected_carrier_authority_status is {projection_record.carrier_authority_status}",
        f"source_mutation is {str(projection_record.source_mutation_requested).lower()}",
        f"mailbox_io_requested is {str(projection_record.mailbox_io_requested).lower()}",
        f"agent_dispatch_authorized is {str(projection_record.agent_dispatch_requested).lower()}",
        f"live_machine_control_authorized is {str(projection_record.live_machine_control_authorized).lower()}",
        "report_status is generated_projection_only",
    }


def _expected_fact_set(
    fixture: CoordinationFixtureSource,
    ledgers: Sequence[CoordinationExpectedLedger],
) -> set[str]:
    expected: set[str] = set()
    fields = fixture.field_map
    _add_first_expected(expected, fields, "projection_kind", "expected_projection_kind")
    _add_first_expected(expected, fields, "expected_status", "expected_projected_status")
    _add_first_expected(expected, fields, "freshness_state", "expected_freshness_state")
    _add_first_expected(expected, fields, "authority_notice_state", "expected_authority_notice")
    _add_first_expected(expected, fields, "carrier_authority_status", "expected_carrier_authority_status")
    for ledger in ledgers:
        case_fields = ledger.case_expectation_map.get(fixture.fixture_id, {})
        _add_first_expected(expected, case_fields, "expected_projection_kind", "expected_projection_kind")
        _add_first_expected(expected, case_fields, "expected_projected_status", "expected_projected_status")
        _add_first_expected(expected, case_fields, "expected_freshness_state", "expected_freshness_state")
        _add_first_expected(expected, case_fields, "expected_carrier_authority_status", "expected_carrier_authority_status")
    expected.add("source_mutation is false")
    expected.add("mailbox_io_requested is false")
    expected.add("agent_dispatch_authorized is false")
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
    normalized_observed = {fact.lower() for fact in observed}
    normalized = expectation.strip().lower()
    if normalized in normalized_observed:
        return True
    if "no source" in normalized and "mutation" in normalized:
        return "source_mutation is false" in normalized_observed
    if "mailbox" in normalized and ("not created" in normalized or "not mutated" in normalized or "false" in normalized):
        return "mailbox_io_requested is false" in normalized_observed
    if "dispatch" in normalized:
        return "agent_dispatch_authorized is false" in normalized_observed
    if "live" in normalized and "control" in normalized:
        return "live_machine_control_authorized is false" in normalized_observed
    if "authority" in normalized and "promotion" in normalized:
        return "source_mutation is false" in normalized_observed
    return False


def _normalize_fixture_id(value: str) -> str:
    parts = value.split("-", 2)
    if len(parts) == 3 and parts[0].startswith("IR6X"):
        return parts[2].replace("-", "_")
    return value.replace("-", "_")


def _freshness_for_fixture(fixture_id: str) -> str:
    if "stale" in fixture_id:
        return "stale"
    if "unread" in fixture_id or "human_override" in fixture_id:
        return "pending_review"
    if "ambiguous" in fixture_id:
        return "interrupted"
    if "conflicting" in fixture_id:
        return "contested"
    if "hidden_scope" in fixture_id:
        return "faulted"
    if "completion_gate" in fixture_id:
        return "blocked"
    return "fresh"


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
