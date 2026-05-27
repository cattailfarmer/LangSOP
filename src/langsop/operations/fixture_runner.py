"""Fixture runner for IR7 operations dry-run projection fixtures."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Mapping, Sequence

from .generated_paths import (
    EXPECTED_LEDGER_ROOT,
    FIXTURE_SOURCE_ROOT,
    NON_AUTHORITY_WARNING,
    OperationsPathPolicyResult,
    display_path,
    validate_operations_expected_ledger_path,
    validate_tracked_operations_fixture_source_path,
)


DEFAULT_EXPECTED_LEDGER_PATHS: tuple[Path, ...] = (
    EXPECTED_LEDGER_ROOT / "operation_request_identity_and_safety_expected.sop",
    EXPECTED_LEDGER_ROOT / "dry_run_result_non_authority_expected.sop",
    EXPECTED_LEDGER_ROOT / "refusal_and_interrupt_expected.sop",
    EXPECTED_LEDGER_ROOT / "resource_safety_and_human_approval_expected.sop",
    EXPECTED_LEDGER_ROOT / "no_live_effect_and_authority_nonpromotion_expected.sop",
)

_FIELD_RE = re.compile(r"^(?P<indent>\s*)\+ \[(?P<name>[^\]]+)\] is (?P<value>.*)$")
_FIXTURE_SOURCE_RE = re.compile(r"^& \[FixtureSource: (?P<fixture_id>[^\]]+)\] is (?P<fixture_name>.*)$")


@dataclass(frozen=True)
class OperationsFixtureSource:
    """Tracked IR7 SOP fixture source parsed into fields and expectations."""

    fixture_id: str
    fixture_name: str
    source_path: str
    field_map: Mapping[str, tuple[str, ...]]
    expectation_set: tuple[str, ...]


@dataclass(frozen=True)
class OperationsExpectedLedger:
    """Tracked IR7 expected ledger parsed into coverage and requirements."""

    ledger_id: str
    source_path: str
    field_map: Mapping[str, tuple[str, ...]]
    covered_fixture_set: tuple[str, ...]
    expectation_set: tuple[str, ...]


@dataclass(frozen=True)
class OperationsFixtureProjectionRecord:
    """In-memory projection summary for one IR7 operations fixture."""

    fixture_id: str
    operation_request_id: str
    projected_status: str
    intended_effect: str
    resource_target: str
    authority_notice_state: str
    expected_refusal: str
    expected_refusal_reason: str
    authority_status: str
    required_human_approval: bool
    live_effect_performed: bool = False
    completion_review_required: bool = True
    non_authority_notice_present: bool = True
    live_approval_granted: bool = False
    dispatch_permission_granted: bool = False
    source_authority_promoted: bool = False
    operations_control_authorized: bool = False
    live_machine_control_authorized: bool = False


@dataclass(frozen=True)
class OperationsFixtureComparisonReport:
    """Generated projection-only comparison report for one IR7 fixture."""

    fixture_id: str
    passed: bool
    observed_projected_status: str
    expected_fact_set: tuple[str, ...]
    observed_fact_set: tuple[str, ...]
    path_policy_result: OperationsPathPolicyResult | None = None
    report_status: str = "generated_projection_only"
    non_authority_warning: str = NON_AUTHORITY_WARNING


@dataclass(frozen=True)
class OperationsFixtureRunResult:
    """Complete in-memory result for one IR7 operations fixture."""

    fixture_source: OperationsFixtureSource
    expected_ledger_set: tuple[OperationsExpectedLedger, ...]
    projection_record: OperationsFixtureProjectionRecord
    comparison_report: OperationsFixtureComparisonReport


def load_operations_fixture_source(
    path: str | Path,
    *,
    workspace_root: str | Path = ".",
) -> OperationsFixtureSource:
    """Load a tracked IR7 operations fixture source after path validation."""

    source_path = validate_tracked_operations_fixture_source_path(path, workspace_root=workspace_root)
    if not source_path.accepted or source_path.normalized_path is None:
        raise ValueError(source_path.refusal_reason or "operations_fixture_source_path_outside_policy")
    text = Path(source_path.normalized_path).read_text(encoding="utf-8")
    fields, expectations, fixture_id, fixture_name = _parse_sop_fixture_source(text)
    normalized_fixture_id = _normalize_fixture_id(
        fixture_id or _first_field(fields, "operation_request_id", Path(path).stem)
    )
    return OperationsFixtureSource(
        fixture_id=normalized_fixture_id,
        fixture_name=fixture_name or Path(path).stem,
        source_path=display_path(path, workspace_root=workspace_root),
        field_map=fields,
        expectation_set=expectations,
    )


def load_operations_expected_ledger(
    path: str | Path,
    *,
    workspace_root: str | Path = ".",
) -> OperationsExpectedLedger:
    """Load a tracked IR7 expected ledger after path validation."""

    ledger_path = validate_operations_expected_ledger_path(path, workspace_root=workspace_root)
    if not ledger_path.accepted or ledger_path.normalized_path is None:
        raise ValueError(ledger_path.refusal_reason or "operations_expected_ledger_path_outside_policy")
    text = Path(ledger_path.normalized_path).read_text(encoding="utf-8")
    fields, expectations, _fixture_id, _fixture_name = _parse_sop_fixture_source(text)
    return OperationsExpectedLedger(
        ledger_id=Path(path).stem,
        source_path=display_path(path, workspace_root=workspace_root),
        field_map=fields,
        covered_fixture_set=tuple(_normalize_fixture_id(value) for value in fields.get("covered_fixture", ())),
        expectation_set=expectations,
    )


def iter_operations_fixture_paths(*, workspace_root: str | Path = ".") -> tuple[Path, ...]:
    """Return tracked IR7 fixture source paths under the accepted root."""

    workspace = Path(workspace_root).resolve()
    root = (workspace / FIXTURE_SOURCE_ROOT).resolve(strict=False)
    return tuple(sorted(root.glob("*.sop")))


def run_operations_dry_run_fixture(
    fixture_path: str | Path,
    *,
    expected_ledger_paths: Sequence[str | Path] = DEFAULT_EXPECTED_LEDGER_PATHS,
    workspace_root: str | Path = ".",
) -> OperationsFixtureRunResult:
    """Project one tracked fixture source and compare it to expected ledgers."""

    fixture = load_operations_fixture_source(fixture_path, workspace_root=workspace_root)
    ledgers = tuple(load_operations_expected_ledger(path, workspace_root=workspace_root) for path in expected_ledger_paths)
    projection_record = project_operations_fixture_source(fixture)
    report = compare_operations_fixture_to_projection(fixture, ledgers, projection_record)
    return OperationsFixtureRunResult(fixture, ledgers, projection_record, report)


def run_operations_dry_run_fixture_corpus(
    *,
    workspace_root: str | Path = ".",
) -> tuple[OperationsFixtureRunResult, ...]:
    """Run all tracked IR7 fixture sources in deterministic path order."""

    return tuple(
        run_operations_dry_run_fixture(path, workspace_root=workspace_root)
        for path in iter_operations_fixture_paths(workspace_root=workspace_root)
    )


def project_operations_fixture_source(
    fixture: OperationsFixtureSource,
) -> OperationsFixtureProjectionRecord:
    """Project a parsed fixture source into an in-memory operations record."""

    fields = fixture.field_map
    refusal = _first_field(fields, "expected_refusal", "")
    return OperationsFixtureProjectionRecord(
        fixture_id=fixture.fixture_id,
        operation_request_id=_first_field(fields, "operation_request_id", fixture.fixture_id.lower()),
        projected_status=_first_field(fields, "expected_status", "accepted"),
        intended_effect=_first_field(fields, "intended_effect", _first_field(fields, "follow_on_intended_effect", "")),
        resource_target=_first_field(fields, "resource_target", _target_from_refusal(refusal)),
        authority_notice_state=_first_field(fields, "authority_notice_state", "present_and_fresh"),
        expected_refusal=refusal,
        expected_refusal_reason=_first_field(fields, "expected_refusal_reason", ""),
        authority_status=_first_field(fields, "expected_authority_status", "operations_projection_only"),
        required_human_approval=_bool_field(fields, "expected_required_human_approval", False),
        live_effect_performed=_bool_field(fields, "expected_live_effect_performed", False),
    )


def compare_operations_fixture_to_projection(
    fixture: OperationsFixtureSource,
    ledgers: Sequence[OperationsExpectedLedger],
    projection_record: OperationsFixtureProjectionRecord,
) -> OperationsFixtureComparisonReport:
    """Compare recognized fixture and ledger expectations to a projection."""

    observed = _observed_fact_set(projection_record)
    expected = _expected_fact_set(fixture, ledgers)
    passed = all(_expectation_satisfied(expectation, observed) for expectation in expected)
    return OperationsFixtureComparisonReport(
        fixture_id=fixture.fixture_id,
        passed=passed,
        observed_projected_status=projection_record.projected_status,
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


def _observed_fact_set(projection_record: OperationsFixtureProjectionRecord) -> set[str]:
    facts = {
        f"expected_status is {projection_record.projected_status}",
        f"expected_projected_status is {projection_record.projected_status}",
        f"expected_authority_notice is {projection_record.authority_notice_state}",
        f"expected_authority_status is {projection_record.authority_status}",
        f"expected_live_effect_performed is {str(projection_record.live_effect_performed).lower()}",
        f"live_effect_performed is {str(projection_record.live_effect_performed).lower()}",
        f"required_human_approval is {str(projection_record.required_human_approval).lower()}",
        f"expected_required_human_approval is {str(projection_record.required_human_approval).lower()}",
        f"completion_review_required is {str(projection_record.completion_review_required).lower()}",
        f"non_authority_notice is {'present' if projection_record.non_authority_notice_present else 'missing'}",
        f"live_approval is {str(projection_record.live_approval_granted).lower()}",
        f"dry_run_success_to_dispatch_permission is {str(projection_record.dispatch_permission_granted).lower()}",
        f"coordination_claim_to_dispatch_authority is {str(projection_record.dispatch_permission_granted).lower()}",
        f"mailbox_carrier_context_to_authority is {str(projection_record.dispatch_permission_granted).lower()}",
        f"generated_projection_to_source_authority is {str(projection_record.source_authority_promoted).lower()}",
        f"operations_control_authorized is {str(projection_record.operations_control_authorized).lower()}",
        f"live_machine_control_authorized is {str(projection_record.live_machine_control_authorized).lower()}",
        "report_status is generated_projection_only",
    }
    if projection_record.expected_refusal:
        facts.add(f"expected_refusal is {projection_record.expected_refusal}")
        facts.add(f"required_refusal_output is {projection_record.expected_refusal}")
    if projection_record.expected_refusal_reason:
        facts.add(f"expected_refusal_reason is {projection_record.expected_refusal_reason}")
    if projection_record.authority_status == "secret_reference_not_secret_access":
        facts.add("opaque_secret_ref_only is true")
    if projection_record.projected_status in {"blocked", "blocked_for_live_effect", "faulted", "review_required"}:
        facts.add("refusal_as_record_not_command is true")
    return facts


def _expected_fact_set(
    fixture: OperationsFixtureSource,
    ledgers: Sequence[OperationsExpectedLedger],
) -> set[str]:
    expected: set[str] = set()
    fields = fixture.field_map
    _add_first_expected(expected, fields, "expected_status", "expected_status")
    _add_first_expected(expected, fields, "expected_refusal", "expected_refusal")
    _add_first_expected(expected, fields, "expected_refusal_reason", "expected_refusal_reason")
    _add_first_expected(expected, fields, "expected_authority_status", "expected_authority_status")
    _add_first_expected(expected, fields, "expected_live_effect_performed", "expected_live_effect_performed")
    _add_first_expected(expected, fields, "expected_required_human_approval", "expected_required_human_approval")

    for ledger in ledgers:
        if fixture.fixture_id not in ledger.covered_fixture_set:
            continue
        expected.add(f"covered_by_expected_ledger is {ledger.ledger_id}")
        for value in ledger.field_map.get("required_result_field", ()):
            if value == "live_effect_performed false":
                expected.add("live_effect_performed is false")
            elif value == "completion_review_required true":
                expected.add("completion_review_required is true")
            elif value == "non_authority_notice present":
                expected.add("non_authority_notice is present")
        for value in ledger.field_map.get("forbidden_result", ()):
            expected.add(f"{value} is false")
        for value in ledger.field_map.get("forbidden_promotion", ()):
            expected.add(f"{value} is false")
        for value in ledger.field_map.get("required_record_status", ()):
            expected.add(f"{value} is true")
        if _first_field(fields, "resource_target", "") == "credential_or_secret" or "credential_reference_shape" in fields:
            for value in ledger.field_map.get("required_secret_result", ()):
                expected.add(f"{value} is true")
        for value in ledger.field_map.get("live_effect_performed", ()):
            expected.add(f"live_effect_performed is {value}")
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
    normalized_observed = {fact.lower() for fact in observed}
    normalized = expectation.strip().lower()
    if normalized in normalized_observed:
        return True
    if normalized.startswith("covered_by_expected_ledger"):
        return True
    if "live_effect_performed" in normalized and "false" in normalized:
        return "live_effect_performed is false" in normalized_observed
    if "non_authority_notice" in normalized and "present" in normalized:
        return "non_authority_notice is present" in normalized_observed
    if "completion_review_required" in normalized and "true" in normalized:
        return "completion_review_required is true" in normalized_observed
    if "forbidden" in normalized or "promotion" in normalized or "authority" in normalized:
        return _authority_or_promotion_expectation_satisfied(normalized, normalized_observed)
    if "refusal_as_record_not_command" in normalized:
        return "refusal_as_record_not_command is true" in normalized_observed
    if "opaque_secret_ref_only" in normalized:
        return "opaque_secret_ref_only is true" in normalized_observed
    return False


def _authority_or_promotion_expectation_satisfied(normalized: str, observed: set[str]) -> bool:
    if "live_approval" in normalized:
        return "live_approval is false" in observed
    if "dry_run_success_to_dispatch_permission" in normalized:
        return "dry_run_success_to_dispatch_permission is false" in observed
    if "coordination_claim_to_dispatch_authority" in normalized:
        return "coordination_claim_to_dispatch_authority is false" in observed
    if "mailbox_carrier_context_to_authority" in normalized:
        return "mailbox_carrier_context_to_authority is false" in observed
    if "generated_projection_to_source_authority" in normalized:
        return "generated_projection_to_source_authority is false" in observed
    if "expected_authority_status" in normalized:
        return normalized in observed
    return False


def _normalize_fixture_id(value: str) -> str:
    normalized = value.strip().replace("_", "-").upper()
    if normalized.startswith("IR7X-"):
        return normalized
    if normalized.startswith("IR7X"):
        return normalized.replace("IR7X", "IR7X-", 1)
    return normalized


def _target_from_refusal(refusal: str) -> str:
    if "gpu" in refusal:
        return "gpu"
    if "model_runtime" in refusal:
        return "model_runtime"
    if "job" in refusal:
        return "job_queue"
    if "credential" in refusal:
        return "credential_or_secret"
    if "network" in refusal:
        return "network_service"
    if "destructive" in refusal or "filesystem" in refusal:
        return "filesystem_destructive_target"
    return "unknown_or_ambiguous"


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
