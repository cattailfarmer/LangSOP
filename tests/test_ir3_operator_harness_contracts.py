"""IR3 operator harness contract and fixture tests."""

from __future__ import annotations

import json
import pathlib
import shutil
import sys
import unittest


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from langsop.authority.discovery import discover_sop_artifacts  # noqa: E402
from langsop.operators import OperatorContract, OutcomeKind, run_contract_operator  # noqa: E402
from langsop.operators.fixture_runner import (  # noqa: E402
    NON_AUTHORITY_WARNING,
    run_operator_fixture,
    validate_generated_output_path,
    write_generated_output,
)


FIXTURE_ROOT = PROJECT_ROOT / "tests" / "fixtures" / "sop" / "ir3_operator_harness"
GENERATED_ROOT = PROJECT_ROOT / "tests" / "fixtures" / "generated" / "ir3_operator_harness"


class IR3OperatorHarnessContractTests(unittest.TestCase):
    def tearDown(self) -> None:
        if GENERATED_ROOT.exists():
            shutil.rmtree(GENERATED_ROOT)

    def test_runner_returns_success_and_stable_trace_identity(self) -> None:
        request = _base_request()
        first = run_contract_operator(request, _contract(), operator_function=lambda records: {"ok": True})
        second = run_contract_operator(request, _contract(), operator_function=lambda records: {"ok": True})

        self.assertTrue(first.accepted)
        self.assertEqual(OutcomeKind.SUCCESS, first.outcome_kind)
        self.assertIsNotNone(first.operator_result)
        self.assertEqual(first.operator_trace.trace_id, second.operator_trace.trace_id)
        self.assertEqual(NON_AUTHORITY_WARNING, first.operator_trace.non_authority_warning)

    def test_runner_classifies_refusal_fault_and_interrupt(self) -> None:
        stale = run_contract_operator({**_base_request(), "authority_basis_state": "stale"}, _contract())
        generated_authority = run_contract_operator(
            {
                **_base_request(),
                "authority_basis_state": "generated_projection_only",
                "generated_projection_presented_as_authority": True,
            },
            _contract(),
        )
        ambiguous = run_contract_operator({**_base_request(), "input_identity_state": "ambiguous"}, _contract())

        self.assertEqual("stale_refusal", stale.runner_refusal.blocked_reason)
        self.assertEqual("generated_trace_authority_confusion", generated_authority.fault_record.fault_kind)
        self.assertEqual("ambiguous_identity", ambiguous.sop_first_interrupt.interrupt_kind)

    def test_fixture_runner_corpus_matches_expectations(self) -> None:
        failed: list[str] = []
        for fixture_path in sorted(FIXTURE_ROOT.glob("*.sop")):
            result = run_operator_fixture(
                fixture_path,
                operator_function=lambda records: {"ok": True},
                workspace_root=PROJECT_ROOT,
            )
            if not result.comparison_report.passed:
                failed.append(fixture_path.name)

        self.assertEqual([], failed)

    def test_generated_path_policy_refuses_escape_and_source_mutation(self) -> None:
        escape = validate_generated_output_path("outside/generated.sop", workspace_root=PROJECT_ROOT)
        source_mutation = validate_generated_output_path(
            "tests/fixtures/sop/ir3_operator_harness/source_mutation_refusal.sop",
            workspace_root=PROJECT_ROOT,
        )
        accepted = validate_generated_output_path(
            "tests/fixtures/generated/ir3_operator_harness/reports/report.json",
            workspace_root=PROJECT_ROOT,
        )

        self.assertFalse(escape.accepted)
        self.assertEqual("generated_output_path_escape", escape.refusal_reason)
        self.assertFalse(source_mutation.accepted)
        self.assertEqual("source_mutation_refusal", source_mutation.refusal_reason)
        self.assertTrue(accepted.accepted)

    def test_generated_output_write_is_ignored_and_not_discovered_as_authority(self) -> None:
        generated_path = "tests/fixtures/generated/ir3_operator_harness/reports/proof_report.json"
        policy = write_generated_output(
            generated_path,
            {
                "report_status": "generated_projection_only",
                "non_authority_warning": NON_AUTHORITY_WARNING,
            },
            workspace_root=PROJECT_ROOT,
        )

        self.assertTrue(policy.accepted)
        output_file = PROJECT_ROOT / generated_path
        self.assertTrue(output_file.exists())
        payload = json.loads(output_file.read_text(encoding="utf-8"))
        self.assertEqual(NON_AUTHORITY_WARNING, payload["non_authority_warning"])

        discovered_paths = {artifact.source_path for artifact in discover_sop_artifacts(PROJECT_ROOT).artifacts}
        self.assertFalse(any(path.startswith("tests/fixtures/generated/ir3_operator_harness/") for path in discovered_paths))


def _contract() -> OperatorContract:
    return OperatorContract(
        operator_id="contract_driven_operator_runner",
        operator_version="v1",
        output_record_kind_set=frozenset(
            {
                "operator_result",
                "operator_trace",
                "fault_record",
                "sop_first_interrupt",
                "stale_projection",
                "generated_output_manifest",
            }
        ),
    )


def _base_request() -> dict[str, object]:
    return {
        "request_id": "test-request",
        "request_uuid": "test-request-uuid",
        "slice_id": "IR3-IA06",
        "requested_operator_id": "contract_driven_operator_runner",
        "requested_operator_version": "v1",
        "requested_outcome_kind": "success",
        "input_ref_set": ("input:a",),
        "authority_basis_ref_set": ("authority:b",),
        "expected_output_kind_set": ("operator_result", "operator_trace"),
        "generated_output_policy_ref": "docs/fixtures/IR3_Fixture_Runner_IO_And_Generated_Trace_Policy.v1.sop",
        "safety_limit_ref": "no_live_operations_control",
        "refusal_allowed": True,
    }


if __name__ == "__main__":
    unittest.main()
