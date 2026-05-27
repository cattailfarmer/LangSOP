"""IR8 integrated manager contract and no-live-effect tests."""

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
from langsop.manager import (  # noqa: E402
    ManagerIssue,
    ManagerIssueKind,
    ManagerIssueSeverity,
    ManagerModelRoute,
    build_manager_work_packet_candidate,
    human_override_record_from_parts,
    manager_cycle_input_from_parts,
    manager_refusal_record_from_issue,
    recompute_manager_readiness,
    run_manager_fixture_corpus,
    validate_generated_manager_output_path,
    validate_human_override_record,
    validate_manager_handoff_record,
    write_generated_manager_output,
)


GENERATED_ROOT = PROJECT_ROOT / "tests" / "fixtures" / "generated" / "ir8_integrated_manager"
PLATFORM_MAILBOX_ROOT = PROJECT_ROOT / "platform" / "coordination" / "mailboxes"


class IR8IntegratedManagerContractTests(unittest.TestCase):
    def tearDown(self) -> None:
        if GENERATED_ROOT.exists():
            shutil.rmtree(GENERATED_ROOT)

    def test_manager_fixture_corpus_matches_expected_ledgers(self) -> None:
        results = run_manager_fixture_corpus(workspace_root=PROJECT_ROOT)
        failed = [result.fixture_source.fixture_id for result in results if not result.comparison_report.passed]

        self.assertEqual([], failed)
        self.assertEqual(12, len(results))

    def test_ready_packet_requires_source_support_completion_and_model_route(self) -> None:
        cycle = _manager_cycle("IR8M-001")

        readiness = recompute_manager_readiness(cycle)
        packet = build_manager_work_packet_candidate(cycle)

        self.assertTrue(readiness.accepted)
        self.assertEqual("ready_for_claim", readiness.readiness_state.value)
        self.assertTrue(packet.ready_for_claim)
        self.assertFalse(packet.dispatch_authorized)
        self.assertFalse(packet.live_effect_performed)

    def test_stale_contested_and_missing_route_inputs_interrupt_or_block(self) -> None:
        stale = recompute_manager_readiness(_manager_cycle("IR8M-002", source_authority_state="accepted_but_stale"))
        contested = recompute_manager_readiness(_manager_cycle("IR8M-004", coordination_state="contested_by_active_claim"))
        missing_route = recompute_manager_readiness(
            _manager_cycle("IR8M-012", model_route=ManagerModelRoute.MISSING, model_route_state="missing")
        )

        self.assertFalse(stale.accepted)
        self.assertEqual(ManagerIssueKind.STALE_BOUNDARY_INPUT, stale.issues[0].issue_kind)
        self.assertIsNotNone(stale.interrupt_context)
        self.assertFalse(contested.accepted)
        self.assertEqual(ManagerIssueKind.CONTESTED_COORDINATION_CLAIM, contested.issues[0].issue_kind)
        self.assertFalse(missing_route.accepted)
        self.assertEqual(ManagerIssueKind.MODEL_ROUTE_AMBIGUITY, missing_route.issues[0].issue_kind)

    def test_refusal_records_preserve_no_dispatch_and_no_live_effect(self) -> None:
        issue = ManagerIssue(
            ManagerIssueKind.REQUESTED_FORBIDDEN_SCOPE,
            ManagerIssueSeverity.REFUSED,
            "live control requires separate authority",
            "requested_effect_kind",
        )
        refusal = manager_refusal_record_from_issue(
            issue,
            refusal_id="ir8m-011",
            requested_effect="gpu_control",
            source_ref_set=("docs/fixtures/IR8_Integrated_Manager_Fixture_Trace_And_Fault_Plan.v1.sop",),
            evidence_ref_set=("tests/fixtures/sop/ir8_integrated_manager/live_control_request_refused.sop",),
        )

        self.assertEqual(ManagerIssueKind.REQUESTED_FORBIDDEN_SCOPE, refusal.refusal_reason)
        self.assertEqual("refuse_and_require_separate_authority", refusal.safe_next_route)
        self.assertFalse(refusal.dispatch_authorized)
        self.assertFalse(refusal.live_effect_performed)

    def test_human_override_requires_scope_freshness_revocation_and_risk_context(self) -> None:
        valid = human_override_record_from_parts(
            override_id="ir8m-008",
            scope="review_only",
            authority_notice_ref="docs/reviews/IR8_IA04_Completion_Review.v1.sop",
            freshness_state="fresh",
            revocation_route="revoke_before_dispatch",
            risk_context_ref="bounded_review",
            source_ref_set=("tests/fixtures/sop/ir8_integrated_manager/human_override_scoped_revocable.sop",),
        )
        invalid = human_override_record_from_parts(
            override_id="invalid",
            scope="",
            authority_notice_ref="notice",
            freshness_state="stale",
            revocation_route="",
            risk_context_ref="",
            source_ref_set=("source",),
        )

        self.assertEqual((), validate_human_override_record(valid))
        self.assertTrue(validate_human_override_record(invalid))

    def test_handoff_validation_refuses_dispatch_claims(self) -> None:
        cycle = _manager_cycle("IR8M-001")
        readiness = recompute_manager_readiness(cycle)
        handoff = __import__("langsop.manager", fromlist=["handoff_record_from_readiness"]).handoff_record_from_readiness(
            readiness,
            handoff_id="ir8m-001:handoff",
            handoff_kind="manager_to_surface",
            source_ref_set=cycle.source_ref_set,
            authority_notice_ref=cycle.authority_notice_ref,
            payload_ref_set=(cycle.work_ref,),
        )

        self.assertEqual((), validate_manager_handoff_record(handoff))
        self.assertFalse(handoff.dispatch_authorized)
        self.assertFalse(handoff.live_effect_performed)

    def test_generated_path_policy_refuses_source_expected_and_mailbox_mutation(self) -> None:
        accepted = validate_generated_manager_output_path(
            "tests/fixtures/generated/ir8_integrated_manager/reports/report.json",
            workspace_root=PROJECT_ROOT,
        )
        escape = validate_generated_manager_output_path("outside/report.json", workspace_root=PROJECT_ROOT)
        source_mutation = validate_generated_manager_output_path("docs/reviews/not_allowed.json", workspace_root=PROJECT_ROOT)
        expected_mutation = validate_generated_manager_output_path(
            "tests/fixtures/expected/ir8_integrated_manager/not_allowed.sop",
            workspace_root=PROJECT_ROOT,
        )
        mailbox_mutation = validate_generated_manager_output_path(
            "platform/coordination/mailboxes/conversation.inbox/1.sop",
            workspace_root=PROJECT_ROOT,
        )

        self.assertTrue(accepted.accepted)
        self.assertFalse(escape.accepted)
        self.assertEqual("generated_manager_path_escape", escape.refusal_reason)
        self.assertFalse(source_mutation.accepted)
        self.assertEqual("source_expected_or_mailbox_mutation_refusal", source_mutation.refusal_reason)
        self.assertFalse(expected_mutation.accepted)
        self.assertEqual("source_expected_or_mailbox_mutation_refusal", expected_mutation.refusal_reason)
        self.assertFalse(mailbox_mutation.accepted)
        self.assertEqual("source_expected_or_mailbox_mutation_refusal", mailbox_mutation.refusal_reason)

    def test_generated_report_is_disposable_and_mailboxes_are_not_created(self) -> None:
        result = run_manager_fixture_corpus(workspace_root=PROJECT_ROOT)[0]
        generated_path = "tests/fixtures/generated/ir8_integrated_manager/reports/proof_report.json"
        policy = write_generated_manager_output(
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
        self.assertFalse(any(path.startswith("tests/fixtures/generated/ir8_integrated_manager/") for path in discovered_paths))
        self.assertFalse(PLATFORM_MAILBOX_ROOT.exists())

        shutil.rmtree(GENERATED_ROOT)
        rebuilt = run_manager_fixture_corpus(workspace_root=PROJECT_ROOT)
        self.assertEqual(12, len(rebuilt))
        self.assertTrue(all(item.comparison_report.passed for item in rebuilt))


def _manager_cycle(
    cycle_id: str,
    *,
    source_authority_state: str = "accepted_and_fresh",
    support_state: str = "complete",
    coordination_state: str = "uncontested",
    model_route: ManagerModelRoute = ManagerModelRoute.GPT_5_3_CODEX_SPARK_SUITABLE,
    model_route_state: str = "declared",
):
    return manager_cycle_input_from_parts(
        cycle_id=cycle_id,
        work_ref=cycle_id.lower(),
        source_ref_set=("docs/canonical/LangSOP_IR8_Implementation_Activation.canonical.sop",),
        authority_notice_ref="docs/reviews/IR8_IA05_Completion_Review.v1.sop",
        source_authority_state=source_authority_state,
        support_state=support_state,
        coordination_state=coordination_state,
        model_route=model_route,
        model_route_state=model_route_state,
        completion_review_ref="docs/reviews/IR8_IA05_Completion_Review.v1.sop",
    )


if __name__ == "__main__":
    unittest.main()
