"""IR6 coordination mailbox contract and no-mailbox-IO tests."""

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
from langsop.coordination import (  # noqa: E402
    ClaimIssueKind,
    ClaimProjectionStatus,
    WorkBoundaryStatus,
    claim_identity_envelope_from_parts,
    classify_coordination_action,
    classify_mailbox_freshness,
    coordination_conflict_context_from_parts,
    mailbox_carrier_envelope_from_parts,
    review_coordination_conflict,
    run_coordination_mailbox_fixture_corpus,
    validate_claim_identity_envelope,
    validate_generated_coordination_output_path,
    validate_mailbox_carrier_envelope,
    validate_work_boundary_projection_envelope,
    work_boundary_projection_envelope_from_parts,
    write_generated_coordination_output,
)


GENERATED_ROOT = PROJECT_ROOT / "tests" / "fixtures" / "generated" / "ir6_coordination_mailbox"
PLATFORM_MAILBOX_ROOT = PROJECT_ROOT / "platform" / "coordination" / "mailboxes"


class IR6CoordinationMailboxContractTests(unittest.TestCase):
    def tearDown(self) -> None:
        if GENERATED_ROOT.exists():
            shutil.rmtree(GENERATED_ROOT)

    def test_coordination_fixture_corpus_matches_expected_ledgers(self) -> None:
        results = run_coordination_mailbox_fixture_corpus(workspace_root=PROJECT_ROOT)
        failed = [result.fixture_source.fixture_id for result in results if not result.comparison_report.passed]

        self.assertEqual([], failed)
        self.assertEqual(13, len(results))

    def test_claim_identity_rejects_missing_authority_and_identity_collapse(self) -> None:
        envelope = claim_identity_envelope_from_parts(
            claim_id="claim-invalid",
            claimant_ref="same-ref",
            conversation_ref="same-ref",
            work_packet_ref="IR6-IA03",
            scope_subject_ref_set=("src/langsop/coordination/claims.py",),
            authority_basis_ref_set=(),
            authority_notice_ref="",
            freshness_state="fresh",
            permitted_action_set=("create_fixture_source",),
            forbidden_action_set=("direct_agent_dispatch",),
            trust_limit="invalid until repaired",
        )

        result = validate_claim_identity_envelope(envelope)

        self.assertFalse(result.accepted)
        self.assertTrue(any(issue.issue_kind == ClaimIssueKind.MISSING_AUTHORITY_BASIS for issue in result.issues))
        self.assertTrue(any(issue.issue_kind == ClaimIssueKind.MISSING_AUTHORITY_NOTICE for issue in result.issues))
        self.assertTrue(any(issue.issue_kind == ClaimIssueKind.IDENTITY_COLLAPSE for issue in result.issues))

    def test_work_boundary_rejects_dependency_closed_with_stop_evidence(self) -> None:
        envelope = work_boundary_projection_envelope_from_parts(
            projection_id="boundary-with-conflict",
            claim_ref="claim-conflict",
            scope_subject_ref_set=("tests/fixtures/sop/ir6_coordination_mailbox/",),
            authority_basis_ref_set=("docs/reviews/IR6_IA02_Completion_Review.v1.sop",),
            authority_notice_ref="authority_notice_ref",
            freshness_state="fresh",
            boundary_status=WorkBoundaryStatus.DEPENDENCY_CLOSED,
            compatibility_relation="overlapping_write_scope",
            required_route_set=("coordination_conflict_signal",),
            forbidden_action_set=("completion_acceptance",),
            contested_claim_ref_set=("claim-a", "claim-b"),
        )

        result = validate_claim_identity_envelope(
            claim_identity_envelope_from_parts(
                claim_id="claim-valid",
                claimant_ref="agent-a",
                conversation_ref="conversation-a",
                work_packet_ref="IR6-IA03",
                scope_subject_ref_set=("tests/fixtures/sop/ir6_coordination_mailbox/",),
                authority_basis_ref_set=("docs/reviews/IR6_IA02_Completion_Review.v1.sop",),
                authority_notice_ref="authority_notice_ref",
                freshness_state="fresh",
                permitted_action_set=("create_fixture_source",),
                forbidden_action_set=("direct_agent_dispatch",),
                trust_limit="fixture only",
                claim_status=ClaimProjectionStatus.ACCEPTED,
            )
        )
        boundary_result = validate_work_boundary_projection_envelope(envelope)

        self.assertTrue(result.accepted)
        self.assertFalse(boundary_result.accepted)
        self.assertTrue(any(issue.issue_kind.value == "ready_with_stop_evidence" for issue in boundary_result.issues))

    def test_mailbox_carrier_refuses_authority_promotion_and_dispatch(self) -> None:
        envelope = mailbox_carrier_envelope_from_parts(
            message_ref="msg-001",
            carrier_surface="SOP_mailbox",
            sender_ref="agent-a",
            addressed_to_ref="agent-b",
            authority_notice_ref="authority_notice_ref",
            freshness_state="pending_review",
            required_route_set=("review_unread_notice",),
            forbidden_action_set=("mailbox_file_write", "direct_agent_dispatch"),
            attempted_effect_set=("assign_agent", "directly_activate_claim"),
        )

        result = validate_mailbox_carrier_envelope(envelope)

        self.assertFalse(result.accepted)
        self.assertTrue(result.has_refusal)

    def test_mailbox_freshness_and_conflict_review_block_ready_state(self) -> None:
        freshness = classify_mailbox_freshness(mailbox_last_modified_ms=1800000000100, read_cursor_ms=1800000000000)
        review = review_coordination_conflict(
            coordination_conflict_context_from_parts(
                contested_claim_ref_set=("claim-a", "claim-b"),
                authority_notice_ref="authority_notice_ref",
            )
        )

        self.assertEqual("pending_review", freshness.freshness_state.value)
        self.assertEqual("block", review.decision.value)
        self.assertIn("completion_review", review.required_route_set)

    def test_action_route_refuses_mailbox_io_dispatch_and_live_control(self) -> None:
        mailbox_io = classify_coordination_action(
            {
                "action_id": "mailbox",
                "action_kind": "mailbox_file_write",
                "projected_subject_ref": "fixture:mailbox_carrier_authority_refusal",
                "authority_notice_ref": "authority_notice_ref",
                "freshness_state": "fresh",
            }
        )
        dispatch = classify_coordination_action(
            {
                "action_id": "dispatch",
                "action_kind": "agent_dispatch",
                "projected_subject_ref": "fixture:human_override_scope_review",
                "authority_notice_ref": "authority_notice_ref",
                "freshness_state": "fresh",
            }
        )
        live = classify_coordination_action(
            {
                "action_id": "live",
                "action_kind": "gpu_control",
                "projected_subject_ref": "fixture:hidden_scope_expansion_fault",
                "authority_notice_ref": "authority_notice_ref",
                "freshness_state": "fresh",
            }
        )

        self.assertEqual("refused", mailbox_io.decision_status.value)
        self.assertIn("mailbox_io_requested", mailbox_io.refusal_reason_set)
        self.assertEqual("refused", dispatch.decision_status.value)
        self.assertIn("agent_dispatch_requested", dispatch.refusal_reason_set)
        self.assertEqual("refused", live.decision_status.value)
        self.assertIn("live_control_requested", live.refusal_reason_set)

    def test_generated_path_policy_refuses_source_and_mailbox_mutation(self) -> None:
        accepted = validate_generated_coordination_output_path(
            "tests/fixtures/generated/ir6_coordination_mailbox/reports/report.json",
            workspace_root=PROJECT_ROOT,
        )
        escape = validate_generated_coordination_output_path("outside/report.json", workspace_root=PROJECT_ROOT)
        source_mutation = validate_generated_coordination_output_path("docs/reviews/not_allowed.json", workspace_root=PROJECT_ROOT)
        mailbox_mutation = validate_generated_coordination_output_path(
            "platform/coordination/mailboxes/conversation.inbox/1.sop",
            workspace_root=PROJECT_ROOT,
        )

        self.assertTrue(accepted.accepted)
        self.assertFalse(escape.accepted)
        self.assertEqual("generated_coordination_path_escape", escape.refusal_reason)
        self.assertFalse(source_mutation.accepted)
        self.assertEqual("source_or_mailbox_mutation_refusal", source_mutation.refusal_reason)
        self.assertFalse(mailbox_mutation.accepted)
        self.assertEqual("source_or_mailbox_mutation_refusal", mailbox_mutation.refusal_reason)

    def test_generated_report_is_disposable_and_mailboxes_are_not_created(self) -> None:
        result = run_coordination_mailbox_fixture_corpus(workspace_root=PROJECT_ROOT)[0]
        generated_path = "tests/fixtures/generated/ir6_coordination_mailbox/reports/proof_report.json"
        policy = write_generated_coordination_output(
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
        self.assertFalse(any(path.startswith("tests/fixtures/generated/ir6_coordination_mailbox/") for path in discovered_paths))
        self.assertFalse(PLATFORM_MAILBOX_ROOT.exists())

        shutil.rmtree(GENERATED_ROOT)
        rebuilt = run_coordination_mailbox_fixture_corpus(workspace_root=PROJECT_ROOT)
        self.assertEqual(13, len(rebuilt))
        self.assertTrue(all(item.comparison_report.passed for item in rebuilt))


if __name__ == "__main__":
    unittest.main()
