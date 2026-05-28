"""Fixture runner for P6 surface projection fixtures."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Mapping, Sequence

from .action_classifier import (
    P6InboundActionClassification,
    classify_p6_inbound_action,
    p6_inbound_action_fact_set,
)
from .envelope import (
    NO_ASSIGNMENT_NOTICE,
    NO_DISPATCH_NOTICE,
    NO_LIVE_EFFECT_NOTICE,
    NO_OPERATIONS_CONTROL_NOTICE,
    NON_AUTHORITY_WARNING,
    P6ProjectionStatus,
    p6_projection_fact_set,
)
from .generated_paths import (
    EXPECTED_LEDGER_ROOT,
    FIXTURE_SOURCE_ROOT,
    P6SurfacePathPolicyResult,
    display_path,
    validate_p6_surface_expected_ledger_path,
    validate_tracked_p6_surface_fixture_source_path,
)
from .nonpromotion import evaluate_p6_nonpromotion_fields, p6_nonpromotion_fact_set
from .surface_matrix import project_p6_surface


DEFAULT_EXPECTED_LEDGER_PATHS: tuple[Path, ...] = (
    EXPECTED_LEDGER_ROOT / "authority_projection_expected.sop",
    EXPECTED_LEDGER_ROOT / "nonpromotion_and_action_refusal_expected.sop",
)

_FIELD_RE = re.compile(r"^(?P<indent>\s*)\+ \[(?P<name>[^\]]+)\] is (?P<value>.*)$")
_FIXTURE_ID_RE = re.compile(r"^Fixture ID:\s*(?P<fixture_id>.+)$")
_FIXTURE_CASE_RE = re.compile(r"^& \[FixtureCase: (?P<fixture_case>[^\]]+)\] is (?P<fixture_name>.*)$")
_EXPECTED_LEDGER_RE = re.compile(r"^& \[ExpectedLedger: (?P<ledger_id>[^\]]+)\] is (?P<ledger_name>.*)$")


@dataclass(frozen=True)
class P6SurfaceFixtureSource:
    """Tracked P6 SOP fixture source parsed into fields and expectations."""

    fixture_id: str
    fixture_name: str
    source_path: str
    field_map: Mapping[str, tuple[str, ...]]
    expectation_set: tuple[str, ...]


@dataclass(frozen=True)
class P6SurfaceExpectedLedger:
    """Tracked P6 expected ledger parsed into coverage and requirements."""

    ledger_id: str
    source_path: str
    field_map: Mapping[str, tuple[str, ...]]
    covered_fixture_set: tuple[str, ...]
    expectation_set: tuple[str, ...]


@dataclass(frozen=True)
class P6SurfaceFixtureProjectionRecord:
    """In-memory projection summary for one P6 surface fixture."""

    fixture_id: str
    surface_family: str
    projection_state: str
    projected_status: str
    acceptance_status: str
    action_result: str
    fault_kind_set: tuple[str, ...]
    refusal_kind_set: tuple[str, ...]
    surface_mutation_authority: bool = False
    generated_projection_authority: bool = False
    source_authority_promoted: bool = False
    assignment_authorized: bool = False
    dispatch_authorized: bool = False
    operations_control_authorized: bool = False
    live_control_authorized: bool = False
    report_status: str = "generated_projection_only"
    non_authority_warning: str = NON_AUTHORITY_WARNING
    no_assignment_notice: str = NO_ASSIGNMENT_NOTICE
    no_dispatch_notice: str = NO_DISPATCH_NOTICE
    no_operations_control_notice: str = NO_OPERATIONS_CONTROL_NOTICE
    no_live_effect_notice: str = NO_LIVE_EFFECT_NOTICE


@dataclass(frozen=True)
class P6SurfaceFixtureComparisonReport:
    """Generated projection-only comparison report for one P6 fixture."""

    fixture_id: str
    passed: bool
    observed_projection_state: str
    expected_fact_set: tuple[str, ...]
    observed_fact_set: tuple[str, ...]
    path_policy_result: P6SurfacePathPolicyResult | None = None
    report_status: str = "generated_projection_only"
    non_authority_warning: str = NON_AUTHORITY_WARNING


@dataclass(frozen=True)
class P6SurfaceFixtureRunResult:
    """Complete in-memory result for one P6 surface fixture."""

    fixture_source: P6SurfaceFixtureSource
    expected_ledger_set: tuple[P6SurfaceExpectedLedger, ...]
    projection_record: P6SurfaceFixtureProjectionRecord
    comparison_report: P6SurfaceFixtureComparisonReport


def load_p6_surface_fixture_source(
    path: str | Path,
    *,
    workspace_root: str | Path = ".",
) -> P6SurfaceFixtureSource:
    """Load a tracked P6 fixture source after path validation."""

    source_path = validate_tracked_p6_surface_fixture_source_path(path, workspace_root=workspace_root)
    if not source_path.accepted or source_path.normalized_path is None:
        raise ValueError(source_path.refusal_reason or "p6_surface_fixture_source_path_outside_policy")
    text = Path(source_path.normalized_path).read_text(encoding="utf-8")
    parsed = _parse_sop_surface_text(text)
    fixture_id = _normalize_fixture_id(parsed.fixture_id or Path(path).stem)
    return P6SurfaceFixtureSource(
        fixture_id=fixture_id,
        fixture_name=parsed.record_name or Path(path).stem,
        source_path=display_path(path, workspace_root=workspace_root),
        field_map=parsed.field_map,
        expectation_set=parsed.expectation_set,
    )


def load_p6_surface_expected_ledger(
    path: str | Path,
    *,
    workspace_root: str | Path = ".",
) -> P6SurfaceExpectedLedger:
    """Load a tracked P6 expected ledger after path validation."""

    ledger_path = validate_p6_surface_expected_ledger_path(path, workspace_root=workspace_root)
    if not ledger_path.accepted or ledger_path.normalized_path is None:
        raise ValueError(ledger_path.refusal_reason or "p6_surface_expected_ledger_path_outside_policy")
    text = Path(ledger_path.normalized_path).read_text(encoding="utf-8")
    parsed = _parse_sop_surface_text(text)
    return P6SurfaceExpectedLedger(
        ledger_id=_normalize_fixture_id(parsed.fixture_id or Path(path).stem),
        source_path=display_path(path, workspace_root=workspace_root),
        field_map=parsed.field_map,
        covered_fixture_set=tuple(_normalize_fixture_id(value) for value in parsed.field_map.get("covered_fixture", ())),
        expectation_set=parsed.expectation_set,
    )


def iter_p6_surface_fixture_paths(*, workspace_root: str | Path = ".") -> tuple[Path, ...]:
    """Return tracked P6 fixture source paths under the accepted root."""

    workspace = Path(workspace_root).resolve()
    root = (workspace / FIXTURE_SOURCE_ROOT).resolve(strict=False)
    return tuple(sorted(root.glob("*.sop")))


def run_p6_surface_fixture(
    fixture_path: str | Path,
    *,
    expected_ledger_paths: Sequence[str | Path] = DEFAULT_EXPECTED_LEDGER_PATHS,
    workspace_root: str | Path = ".",
) -> P6SurfaceFixtureRunResult:
    """Project one tracked P6 fixture source and compare expected ledgers."""

    fixture = load_p6_surface_fixture_source(fixture_path, workspace_root=workspace_root)
    ledgers = tuple(load_p6_surface_expected_ledger(path, workspace_root=workspace_root) for path in expected_ledger_paths)
    projection_record = project_p6_surface_fixture_source(fixture)
    report = compare_p6_surface_fixture_to_projection(fixture, ledgers, projection_record)
    return P6SurfaceFixtureRunResult(fixture, ledgers, projection_record, report)


def run_p6_surface_fixture_corpus(
    *,
    workspace_root: str | Path = ".",
) -> tuple[P6SurfaceFixtureRunResult, ...]:
    """Run all tracked P6 surface fixtures in deterministic path order."""

    return tuple(
        run_p6_surface_fixture(path, workspace_root=workspace_root)
        for path in iter_p6_surface_fixture_paths(workspace_root=workspace_root)
    )


def project_p6_surface_fixture_source(
    fixture: P6SurfaceFixtureSource,
) -> P6SurfaceFixtureProjectionRecord:
    """Project a parsed P6 fixture source into an in-memory comparison record."""

    packet = _single_value_packet(fixture)
    projection = project_p6_surface(packet)
    nonpromotion = evaluate_p6_nonpromotion_fields(_nonpromotion_field_map(fixture.field_map))
    action = classify_p6_inbound_action(_action_packet(packet)) if packet.get("inbound_action_kind") else None
    projection_state = _projection_state(projection.envelope.projected_status, projection.envelope.authority_notice_ref)
    fault_kind_set = _fault_kind_set(nonpromotion, projection.validation)
    refusal_kind_set = _refusal_kind_set(action)
    action_result = _action_result(action)
    acceptance_status = _acceptance_status(projection.envelope.projected_status, action_result)
    surface_mutation_authority = False

    return P6SurfaceFixtureProjectionRecord(
        fixture_id=fixture.fixture_id,
        surface_family=projection.envelope.surface_family.value,
        projection_state=projection_state,
        projected_status=projection.envelope.projected_status.value,
        acceptance_status=acceptance_status,
        action_result=action_result,
        fault_kind_set=fault_kind_set,
        refusal_kind_set=refusal_kind_set,
        surface_mutation_authority=surface_mutation_authority,
        generated_projection_authority=False,
        source_authority_promoted=bool(fault_kind_set),
        assignment_authorized=False,
        dispatch_authorized=False,
        operations_control_authorized=False,
        live_control_authorized=False,
    )


def compare_p6_surface_fixture_to_projection(
    fixture: P6SurfaceFixtureSource,
    ledgers: Sequence[P6SurfaceExpectedLedger],
    projection_record: P6SurfaceFixtureProjectionRecord,
) -> P6SurfaceFixtureComparisonReport:
    """Compare fixture and ledger expectations to a P6 projection record."""

    observed = _observed_fact_set(projection_record, fixture)
    expected = _expected_fact_set(fixture, ledgers)
    passed = all(_expectation_satisfied(expectation, observed) for expectation in expected)
    return P6SurfaceFixtureComparisonReport(
        fixture_id=fixture.fixture_id,
        passed=passed,
        observed_projection_state=projection_record.projection_state,
        expected_fact_set=tuple(sorted(expected)),
        observed_fact_set=tuple(sorted(observed)),
    )


@dataclass(frozen=True)
class _ParsedSOPSurfaceText:
    fixture_id: str
    record_name: str
    field_map: dict[str, tuple[str, ...]]
    expectation_set: tuple[str, ...]


def _parse_sop_surface_text(text: str) -> _ParsedSOPSurfaceText:
    fields: dict[str, tuple[str, ...]] = {}
    expectations: list[str] = []
    fixture_id = ""
    record_name = ""

    for line in text.splitlines():
        stripped = line.strip()
        fixture_id_match = _FIXTURE_ID_RE.match(stripped)
        if fixture_id_match is not None:
            fixture_id = fixture_id_match.group("fixture_id").strip()
            continue

        fixture_case_match = _FIXTURE_CASE_RE.match(stripped)
        if fixture_case_match is not None:
            record_name = fixture_case_match.group("fixture_case").strip()
            if not fixture_id:
                fixture_id = record_name
            continue

        ledger_match = _EXPECTED_LEDGER_RE.match(stripped)
        if ledger_match is not None:
            record_name = ledger_match.group("ledger_id").strip()
            if not fixture_id:
                fixture_id = record_name
            continue

        field_match = _FIELD_RE.match(line)
        if field_match is not None:
            name = field_match.group("name")
            value = field_match.group("value").strip()
            fields[name] = fields.get(name, ()) + (value,)
            continue

        if stripped.startswith("= must:"):
            expectations.append(stripped.removeprefix("= must:").strip())
        elif stripped.startswith("= expect:"):
            expectations.append(stripped.removeprefix("= expect:").strip())

    return _ParsedSOPSurfaceText(fixture_id, record_name, fields, tuple(expectations))


def _single_value_packet(fixture: P6SurfaceFixtureSource) -> dict[str, object]:
    packet = {name: values[0] for name, values in fixture.field_map.items() if values}
    packet.setdefault("fixture_case", fixture.fixture_id)
    packet.setdefault("actor_ref", "p6_fixture_runner")
    packet.setdefault("conversation_ref", "p6_surface_fixture_corpus")
    packet.setdefault("source_message_or_event_ref", fixture.source_path)
    packet.setdefault("projection_ref", fixture.source_path)
    packet.setdefault("source_ref", fixture.source_path)
    return packet


def _action_packet(packet: Mapping[str, object]) -> dict[str, object]:
    action_packet = dict(packet)
    action_packet.setdefault("actor_ref", "p6_fixture_runner")
    action_packet.setdefault("conversation_ref", "p6_surface_fixture_corpus")
    action_packet.setdefault("source_message_or_event_ref", action_packet.get("source_ref", "p6_surface_fixture"))
    action_packet.setdefault("projection_ref", action_packet.get("source_ref", "p6_surface_fixture"))
    action_packet.setdefault("authority_notice_seen", bool(action_packet.get("required_notice")))
    action_packet.setdefault("requested_action_kind", action_packet.get("inbound_action_kind", ""))
    return action_packet


def _projection_state(status: P6ProjectionStatus, authority_notice_ref: str) -> str:
    if status == P6ProjectionStatus.READY and authority_notice_ref:
        return "visible_authority_notice"
    if status == P6ProjectionStatus.STALE:
        return "visible_stale_notice"
    return status.value


def _fault_kind_set(nonpromotion: object, validation: object) -> tuple[str, ...]:
    faults: list[str] = []
    issue_kind = getattr(nonpromotion, "issue_kind", None)
    state = getattr(getattr(nonpromotion, "state", None), "value", "")
    if issue_kind is not None and state in {"faulted", "refused"}:
        faults.append(str(issue_kind.value))
    for issue in getattr(validation, "issues", ()):
        severity = getattr(issue, "severity", None)
        if getattr(severity, "value", "") == "fault" and issue.issue_kind.value == "lower_authority_tier_promoted":
            faults.append(str(issue.issue_kind.value))
    return tuple(dict.fromkeys(faults))


def _nonpromotion_field_map(
    fields: Mapping[str, tuple[str, ...]],
) -> dict[str, tuple[str, ...]]:
    nonpromotion_fields = dict(fields)
    nonpromotion_fields.setdefault("projection_record_kind", ("surface_snapshot",))
    nonpromotion_fields.setdefault("required_notice", (NON_AUTHORITY_WARNING,))
    return nonpromotion_fields


def _refusal_kind_set(action: object | None) -> tuple[str, ...]:
    if action is None:
        return ()
    refusals: list[str] = []
    for issue in getattr(action, "issue_set", ()):
        if getattr(issue.severity, "value", "") != "refused":
            continue
        if issue.issue_kind.value == "direct_mutation_requested":
            refusals.append("surface_cannot_mutate_source_authority")
        refusals.append(issue.issue_kind.value)
    return tuple(dict.fromkeys(refusals))


def _action_result(action: object | None) -> str:
    if action is None:
        return "not_applicable"
    if action.classification == P6InboundActionClassification.REFUSED:
        return "refused"
    if getattr(action, "accepted", False):
        return "accepted"
    return "blocked"


def _acceptance_status(status: P6ProjectionStatus, action_result: str) -> str:
    if status == P6ProjectionStatus.FAULTED or action_result == "refused":
        return "refused_or_faulted"
    if status == P6ProjectionStatus.STALE:
        return "stale"
    if status == P6ProjectionStatus.READY:
        return "accepted"
    return status.value


def _observed_fact_set(
    projection_record: P6SurfaceFixtureProjectionRecord,
    fixture: P6SurfaceFixtureSource,
) -> set[str]:
    facts = {
        f"surface_family is {projection_record.surface_family}",
        f"projection_state is {projection_record.projection_state}",
        f"expected_projection_state is {projection_record.projection_state}",
        f"projected_status is {projection_record.projected_status}",
        f"acceptance_status is {projection_record.acceptance_status}",
        f"expected_acceptance_status is {projection_record.acceptance_status}",
        f"action_result is {projection_record.action_result}",
        f"expected_action_result is {projection_record.action_result}",
        f"surface_mutation_authority is {_bool_text(projection_record.surface_mutation_authority)}",
        f"expected_surface_mutation_authority is {_bool_text(projection_record.surface_mutation_authority)}",
        f"generated_projection_authority is {_bool_text(projection_record.generated_projection_authority)}",
        f"source_authority_promoted is {_bool_text(projection_record.source_authority_promoted)}",
        f"assignment_authorized is {_bool_text(projection_record.assignment_authorized)}",
        f"dispatch_authority is {_bool_text(projection_record.dispatch_authorized)}",
        f"dispatch_authorized is {_bool_text(projection_record.dispatch_authorized)}",
        f"operations_control_authorized is {_bool_text(projection_record.operations_control_authorized)}",
        f"live_control_authorized is {_bool_text(projection_record.live_control_authorized)}",
        f"nonpromotion_notice is {projection_record.non_authority_warning}",
        "expected_nonpromotion_notice is rendered_projection_not_source_authority",
        "report_status is generated_projection_only",
    }
    for fault in projection_record.fault_kind_set:
        facts.add(f"fault_kind is {fault}")
        facts.add(f"expected_fault_kind is {fault}")
    for refusal in projection_record.refusal_kind_set:
        facts.add(f"refusal_kind is {refusal}")
        facts.add(f"expected_refusal_kind is {refusal}")

    projection = project_p6_surface(_single_value_packet(fixture))
    facts.update(p6_projection_fact_set(projection.envelope))
    facts.update(p6_nonpromotion_fact_set(evaluate_p6_nonpromotion_fields(_nonpromotion_field_map(fixture.field_map))))
    if "inbound_action_kind" in fixture.field_map:
        facts.update(p6_inbound_action_fact_set(classify_p6_inbound_action(_action_packet(_single_value_packet(fixture)))))
    return facts


def _expected_fact_set(
    fixture: P6SurfaceFixtureSource,
    ledgers: Sequence[P6SurfaceExpectedLedger],
) -> set[str]:
    expected: set[str] = set()
    fields = fixture.field_map
    for field_name in (
        "expected_projection_state",
        "expected_fault_kind",
        "expected_action_result",
        "expected_refusal_kind",
        "expected_acceptance_status",
        "surface_mutation_authority",
        "generated_projection_authority",
        "dispatch_authority",
    ):
        _add_first_expected(expected, fields, field_name, field_name)

    for ledger in ledgers:
        if fixture.fixture_id not in ledger.covered_fixture_set:
            continue
        for value in ledger.field_map.get("expected_projection_state", ()):
            expected.add(f"expected_projection_state is {value}")
        for value in ledger.field_map.get("expected_surface_mutation_authority", ()):
            expected.add(f"expected_surface_mutation_authority is {value}")
        for value in ledger.field_map.get("expected_nonpromotion_notice", ()):
            expected.add(f"expected_nonpromotion_notice is {value}")
        for value in ledger.field_map.get("expected_acceptance_status", ()):
            expected.add(f"expected_acceptance_status is {value}")
        if "inbound_action_kind" in fields:
            for value in ledger.field_map.get("expected_refusal_kind", ()):
                expected.add(f"expected_refusal_kind is {value}")
        if "projection_record_kind" in fields or "claimed_authority_class" in fields:
            for value in ledger.field_map.get("expected_fault_kind", ()):
                expected.add(f"expected_fault_kind is {value}")

    expected.add("surface_mutation_authority is false")
    expected.add("generated_projection_authority is false")
    expected.add("dispatch_authorized is false")
    expected.add("operations_control_authorized is false")
    expected.add("live_control_authorized is false")
    return expected


def _add_first_expected(
    expected: set[str],
    fields: Mapping[str, tuple[str, ...]],
    field_name: str,
    fact_name: str,
) -> None:
    values = fields.get(field_name, ())
    if values:
        expected.add(f"{fact_name} is {values[0]}")


def _expectation_satisfied(expectation: str, observed: set[str]) -> bool:
    normalized_observed = {fact.lower() for fact in observed}
    normalized = expectation.strip().lower()
    if normalized in normalized_observed:
        return True
    if normalized == "expected_projection_state is visible_authority_or_stale_notice":
        return (
            "expected_projection_state is visible_authority_notice" in normalized_observed
            or "expected_projection_state is visible_stale_notice" in normalized_observed
        )
    if normalized == "expected_acceptance_status is refused_or_faulted":
        return (
            "expected_acceptance_status is refused_or_faulted" in normalized_observed
            or "projected_status is faulted" in normalized_observed
            or "expected_action_result is refused" in normalized_observed
        )
    if normalized == "expected_nonpromotion_notice is rendered_projection_not_source_authority":
        return "generated_projection_authority is false" in normalized_observed
    if normalized.endswith(" is false"):
        fact_name = normalized.rsplit(" is ", 1)[0]
        return f"{fact_name} is false" in normalized_observed
    return False


def _normalize_fixture_id(value: str) -> str:
    text = value.strip()
    text = re.sub(r"(?<!^)(?=[A-Z])", "_", text).lower()
    text = text.replace("-", "_").replace(" ", "_")
    text = re.sub(r"[^a-z0-9_]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    if text.startswith("p6_"):
        text = text.removeprefix("p6_")
    return text


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


__all__ = (
    "DEFAULT_EXPECTED_LEDGER_PATHS",
    "P6SurfaceExpectedLedger",
    "P6SurfaceFixtureComparisonReport",
    "P6SurfaceFixtureProjectionRecord",
    "P6SurfaceFixtureRunResult",
    "P6SurfaceFixtureSource",
    "compare_p6_surface_fixture_to_projection",
    "iter_p6_surface_fixture_paths",
    "load_p6_surface_expected_ledger",
    "load_p6_surface_fixture_source",
    "project_p6_surface_fixture_source",
    "run_p6_surface_fixture",
    "run_p6_surface_fixture_corpus",
)
