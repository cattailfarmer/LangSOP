"""IR4 runtime graph contract and fixture runner tests."""

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
from langsop.runtime.fixture_runner import (  # noqa: E402
    NON_AUTHORITY_WARNING,
    run_runtime_graph_fixture,
    run_runtime_graph_fixture_corpus,
    validate_generated_runtime_path,
    write_generated_runtime_report,
)
from langsop.runtime.graph_state import GraphNodeId, TerminalOutcome  # noqa: E402


FIXTURE_ROOT = PROJECT_ROOT / "tests" / "fixtures" / "sop" / "ir4_runtime_graph"
GENERATED_ROOT = PROJECT_ROOT / "tests" / "fixtures" / "generated" / "ir4_runtime_graph"


class IR4RuntimeGraphContractTests(unittest.TestCase):
    def tearDown(self) -> None:
        if GENERATED_ROOT.exists():
            shutil.rmtree(GENERATED_ROOT)

    def test_valid_graph_fixture_reaches_success_gate(self) -> None:
        result = run_runtime_graph_fixture(
            FIXTURE_ROOT / "valid_graph_pass.sop",
            workspace_root=PROJECT_ROOT,
        )

        self.assertTrue(result.comparison_report.passed)
        self.assertIsNotNone(result.graph_run_result)
        self.assertEqual(TerminalOutcome.SUCCESS, result.comparison_report.observed_terminal_outcome)
        self.assertTrue(result.graph_run_result.accepted)
        self.assertIn(GraphNodeId.COMPLETION_GATE, result.comparison_report.node_visit_set)
        self.assertEqual(NON_AUTHORITY_WARNING, result.comparison_report.non_authority_warning)

    def test_fixture_runner_classifies_runtime_outcomes(self) -> None:
        expected = {
            "blocked_readiness.sop": (TerminalOutcome.BLOCKED, "support_gap_blocks_readiness"),
            "stale_checkpoint.sop": (TerminalOutcome.STALE, "checkpoint_freshness_basis_changed"),
            "ambiguous_interrupt.sop": (TerminalOutcome.INTERRUPT, "ambiguous_identity"),
            "authority_conflict_interrupt.sop": (TerminalOutcome.INTERRUPT, "authority_conflict"),
            "contested_claim_interrupt.sop": (TerminalOutcome.INTERRUPT, "contested_coordination_claim"),
            "faulted_operator_trace.sop": (TerminalOutcome.FAULT, "missing_operator_trace"),
            "hidden_write_prevention.sop": (TerminalOutcome.FAULT, "hidden_source_write_attempt"),
            "false_ready_checkpoint.sop": (TerminalOutcome.FAULT, "checkpoint_readiness_authority_confusion"),
            "completion_gate_refusal.sop": (TerminalOutcome.BLOCKED, "completion_review_delta_gate_missing"),
        }

        for fixture_name, (outcome, reason) in expected.items():
            with self.subTest(fixture_name=fixture_name):
                result = run_runtime_graph_fixture(FIXTURE_ROOT / fixture_name, workspace_root=PROJECT_ROOT)
                report = result.comparison_report

                self.assertTrue(report.passed)
                self.assertEqual(outcome, report.observed_terminal_outcome)
                self.assertTrue(any(reason in fact for fact in report.observed_fact_set), report.observed_fact_set)

    def test_runtime_fixture_corpus_matches_expected_ledgers(self) -> None:
        results = run_runtime_graph_fixture_corpus(workspace_root=PROJECT_ROOT)
        failed = [result.fixture_source.fixture_id for result in results if not result.comparison_report.passed]

        self.assertEqual([], failed)
        self.assertEqual(10, len(results))

    def test_generated_runtime_path_policy_refuses_escape_and_source_mutation(self) -> None:
        escape = validate_generated_runtime_path("outside/generated.sop", workspace_root=PROJECT_ROOT)
        source_mutation = validate_generated_runtime_path(
            "tests/fixtures/sop/ir4_runtime_graph/valid_graph_pass.sop",
            workspace_root=PROJECT_ROOT,
        )
        expected_ledger_mutation = validate_generated_runtime_path(
            "tests/fixtures/expected/ir4_runtime_graph/graph_trace_expected.sop",
            workspace_root=PROJECT_ROOT,
        )
        accepted = validate_generated_runtime_path(
            "tests/fixtures/generated/ir4_runtime_graph/reports/report.json",
            workspace_root=PROJECT_ROOT,
        )

        self.assertFalse(escape.accepted)
        self.assertEqual("generated_runtime_path_escape", escape.refusal_reason)
        self.assertFalse(source_mutation.accepted)
        self.assertEqual("source_mutation_refusal", source_mutation.refusal_reason)
        self.assertFalse(expected_ledger_mutation.accepted)
        self.assertEqual("source_mutation_refusal", expected_ledger_mutation.refusal_reason)
        self.assertTrue(accepted.accepted)

    def test_generated_runtime_report_is_ignored_and_not_discovered_as_authority(self) -> None:
        result = run_runtime_graph_fixture(
            FIXTURE_ROOT / "valid_graph_pass.sop",
            workspace_root=PROJECT_ROOT,
        )
        generated_path = "tests/fixtures/generated/ir4_runtime_graph/reports/proof_report.json"
        policy = write_generated_runtime_report(generated_path, result.comparison_report, workspace_root=PROJECT_ROOT)

        self.assertTrue(policy.accepted)
        output_file = PROJECT_ROOT / generated_path
        self.assertTrue(output_file.exists())
        payload = json.loads(output_file.read_text(encoding="utf-8"))
        self.assertEqual("generated_projection_only", payload["report_status"])
        self.assertEqual(NON_AUTHORITY_WARNING, payload["non_authority_warning"])

        discovered_paths = {artifact.source_path for artifact in discover_sop_artifacts(PROJECT_ROOT).artifacts}
        self.assertFalse(any(path.startswith("tests/fixtures/generated/ir4_runtime_graph/") for path in discovered_paths))


if __name__ == "__main__":
    unittest.main()
