"""IR5 surface projection contract and generated-output policy tests."""

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
from langsop.surfaces import (  # noqa: E402
    AuthorityTier,
    ProjectionStateIssueKind,
    ProjectionStatus,
    authority_display_envelope_from_parts,
    classify_surface_action,
    projection_state_envelope_from_parts,
    run_surface_projection_fixture_corpus,
    validate_authority_display_envelope,
    validate_generated_surface_output_path,
    validate_projection_state_envelope,
    write_generated_surface_output,
)


GENERATED_ROOT = PROJECT_ROOT / "tests" / "fixtures" / "generated" / "ir5_surface_projection"


class IR5SurfaceProjectionContractTests(unittest.TestCase):
    def tearDown(self) -> None:
        if GENERATED_ROOT.exists():
            shutil.rmtree(GENERATED_ROOT)

    def test_surface_fixture_corpus_matches_expected_ledgers(self) -> None:
        results = run_surface_projection_fixture_corpus(workspace_root=PROJECT_ROOT)
        failed = [result.fixture_source.fixture_id for result in results if not result.comparison_report.passed]

        self.assertEqual([], failed)
        self.assertEqual(13, len(results))

    def test_authority_display_refuses_missing_notice_and_source_refs(self) -> None:
        envelope = authority_display_envelope_from_parts(
            display_projection_id="missing-authority",
            projected_subject_ref="fixture:missing_authority_notice",
            carrier_surface="incomplete_projection_surface",
            authority_tier=AuthorityTier.GENERATED_PROJECTION_EVIDENCE,
            trust_limit="invalid until repaired",
            source_authority_ref_set=(),
            derived_from_ref_set=(),
            authority_notice_ref="",
            freshness_state="unknown",
            risk_reason="missing_authority_notice",
            permitted_action_set=("request_review",),
            forbidden_action_set=("decision_making_projection_use",),
            required_route_set=("repair_projection_contract_output_before_use",),
            mutation_boundary_ref="projection_only_no_source_mutation",
        )

        result = validate_authority_display_envelope(envelope)

        self.assertFalse(result.accepted)
        self.assertTrue(any(issue.issue_kind.value == "missing_authority_notice" for issue in result.issues))
        self.assertTrue(any(issue.issue_kind.value == "missing_source_ref_set" for issue in result.issues))

    def test_projection_state_rejects_ready_with_stop_state(self) -> None:
        envelope = projection_state_envelope_from_parts(
            projection_id="ready-with-blocker",
            projection_kind="manager_summary_projection",
            projected_subject_ref="fixture:blocked",
            source_record_ref_set=("docs/state/IR5_Work_State.v1.sop",),
            lineage_edge_set=("fixture:blocked->manager_summary_projection",),
            generated_at="test",
            projected_status=ProjectionStatus.READY,
            freshness_state="fresh",
            blocker_ref_set=("unresolved_support_gap",),
            supported_action_route_set=("request_review",),
            authority_notice_ref="authority_notice_ref",
        )

        result = validate_projection_state_envelope(envelope)

        self.assertFalse(result.accepted)
        self.assertTrue(any(issue.issue_kind == ProjectionStateIssueKind.READY_WITH_STOP_STATE for issue in result.issues))

    def test_action_route_refuses_direct_mutation_and_live_control(self) -> None:
        direct = classify_surface_action(
            {
                "action_id": "direct",
                "action_kind": "direct_source_authority_write",
                "projected_subject_ref": "fixture:adapter_mutation_refusal",
                "authority_notice_ref": "authority_notice_ref",
                "freshness_state": "fresh",
            }
        )
        live = classify_surface_action(
            {
                "action_id": "live",
                "action_kind": "gpu_control",
                "projected_subject_ref": "fixture:dry_run_success_not_live_control",
                "authority_notice_ref": "authority_notice_ref",
                "freshness_state": "fresh",
            }
        )

        self.assertEqual("refused", direct.decision_status.value)
        self.assertIn("direct_mutation_requested", direct.refusal_reason_set)
        self.assertEqual("refused", live.decision_status.value)
        self.assertIn("live_control_requested", live.refusal_reason_set)

    def test_generated_path_policy_refuses_escape_and_source_mutation(self) -> None:
        accepted = validate_generated_surface_output_path(
            "tests/fixtures/generated/ir5_surface_projection/reports/report.json",
            workspace_root=PROJECT_ROOT,
        )
        escape = validate_generated_surface_output_path("outside/report.json", workspace_root=PROJECT_ROOT)
        source_mutation = validate_generated_surface_output_path(
            "docs/reviews/not_allowed.json",
            workspace_root=PROJECT_ROOT,
        )
        expected_ledger_mutation = validate_generated_surface_output_path(
            "tests/fixtures/expected/ir5_surface_projection/authority_display_expected.sop",
            workspace_root=PROJECT_ROOT,
        )

        self.assertTrue(accepted.accepted)
        self.assertFalse(escape.accepted)
        self.assertEqual("generated_surface_path_escape", escape.refusal_reason)
        self.assertFalse(source_mutation.accepted)
        self.assertEqual("source_mutation_refusal", source_mutation.refusal_reason)
        self.assertFalse(expected_ledger_mutation.accepted)
        self.assertEqual("source_mutation_refusal", expected_ledger_mutation.refusal_reason)

    def test_generated_report_is_disposable_and_not_authority(self) -> None:
        result = run_surface_projection_fixture_corpus(workspace_root=PROJECT_ROOT)[0]
        generated_path = "tests/fixtures/generated/ir5_surface_projection/reports/proof_report.json"
        policy = write_generated_surface_output(
            generated_path,
            result.comparison_report,
            workspace_root=PROJECT_ROOT,
        )

        self.assertTrue(policy.accepted)
        output_file = PROJECT_ROOT / generated_path
        self.assertTrue(output_file.exists())
        payload = json.loads(output_file.read_text(encoding="utf-8"))
        self.assertEqual("generated_projection_only", payload["report_status"])
        self.assertIn("generated-projection-only", payload["non_authority_warning"])

        discovered_paths = {artifact.source_path for artifact in discover_sop_artifacts(PROJECT_ROOT).artifacts}
        self.assertFalse(any(path.startswith("tests/fixtures/generated/ir5_surface_projection/") for path in discovered_paths))

        shutil.rmtree(GENERATED_ROOT)
        rebuilt = run_surface_projection_fixture_corpus(workspace_root=PROJECT_ROOT)
        self.assertEqual(13, len(rebuilt))
        self.assertTrue(all(item.comparison_report.passed for item in rebuilt))


if __name__ == "__main__":
    unittest.main()
