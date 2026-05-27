"""IR7 operations dry-run contract and no-live-effect tests."""

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
from langsop.operations import (  # noqa: E402
    OperationActionDecisionStatus,
    OperationRefusalReason,
    ResourceRiskLevel,
    classify_operation_action,
    dry_run_result_from_operation_request,
    operation_request_envelope_from_parts,
    refusal_record_from_request_validation,
    review_resource_safety,
    run_operations_dry_run_fixture_corpus,
    validate_dry_run_result_record,
    validate_generated_operations_output_path,
    validate_operation_refusal_record,
    validate_operation_request_envelope,
    write_generated_operations_output,
)


GENERATED_ROOT = PROJECT_ROOT / "tests" / "fixtures" / "generated" / "ir7_operations_dry_run"
PLATFORM_MAILBOX_ROOT = PROJECT_ROOT / "platform" / "coordination" / "mailboxes"


class IR7OperationsDryRunContractTests(unittest.TestCase):
    def tearDown(self) -> None:
        if GENERATED_ROOT.exists():
            shutil.rmtree(GENERATED_ROOT)

    def test_operations_fixture_corpus_matches_expected_ledgers(self) -> None:
        results = run_operations_dry_run_fixture_corpus(workspace_root=PROJECT_ROOT)
        failed = [result.fixture_source.fixture_id for result in results if not result.comparison_report.passed]

        self.assertEqual([], failed)
        self.assertEqual(13, len(results))

    def test_operation_request_and_dry_run_result_stay_non_authoritative(self) -> None:
        request = _operation_request(
            operation_request_id="ir7x-001",
            intended_effect="estimate_resource_use",
            resource_target="gpu",
            risk_classification="bounded_dry_run",
            blast_radius="bounded",
        )

        validation = validate_operation_request_envelope(request)
        result = dry_run_result_from_operation_request(request, validation)
        result_validation = validate_dry_run_result_record(result)

        self.assertTrue(validation.accepted)
        self.assertTrue(result.is_non_authoritative)
        self.assertTrue(result_validation.accepted)
        self.assertFalse(result.live_effect_performed)
        self.assertTrue(result.completion_review_required)

    def test_live_gpu_and_destructive_requests_become_refusal_records(self) -> None:
        gpu_request = _operation_request(
            operation_request_id="ir7x-002",
            intended_effect="gpu_workload_launch",
            resource_target="gpu",
        )
        destructive_request = _operation_request(
            operation_request_id="ir7x-007",
            intended_effect="destructive_filesystem_action",
            resource_target="filesystem_destructive_target",
        )

        gpu_validation = validate_operation_request_envelope(gpu_request)
        destructive_validation = validate_operation_request_envelope(destructive_request)
        gpu_refusal = refusal_record_from_request_validation(gpu_request, gpu_validation)
        destructive_refusal = refusal_record_from_request_validation(destructive_request, destructive_validation)

        self.assertFalse(gpu_validation.accepted)
        self.assertEqual(OperationRefusalReason.LIVE_EFFECT_REQUESTED, gpu_refusal.refusal_reason)
        self.assertTrue(validate_operation_refusal_record(gpu_refusal).accepted)
        self.assertFalse(gpu_refusal.live_effect_performed)
        self.assertFalse(destructive_validation.accepted)
        self.assertIn("refused_destructive_filesystem_control", destructive_refusal.refused_effect_set)

    def test_resource_safety_requires_review_without_live_authority(self) -> None:
        request = _operation_request(
            operation_request_id="ir7x-003",
            intended_effect="estimate_resource_use",
            resource_target="gpu",
            risk_classification="high",
            blast_radius="uncertain",
            predicted_side_effect_set=("gpu_contention",),
        )

        review = review_resource_safety(request)

        self.assertEqual(ResourceRiskLevel.CRITICAL, review.risk_level)
        self.assertTrue(review.required_human_review)
        self.assertFalse(review.live_control_authorized)
        self.assertTrue(review.issues)

    def test_operation_action_route_refuses_live_and_boundary_mutation(self) -> None:
        live = classify_operation_action(
            {
                "action_id": "live",
                "action_kind": "gpu_workload_launch",
                "operation_request_ref": "ir7x-002",
                "authority_notice_ref": "authority",
                "freshness_state": "fresh",
                "resource_target": "gpu",
                "risk_classification": "high",
            }
        )
        credential = classify_operation_action(
            {
                "action_id": "credential",
                "action_kind": "credential_access_or_mutation",
                "operation_request_ref": "ir7x-005",
                "authority_notice_ref": "authority",
                "freshness_state": "fresh",
                "resource_target": "credential_or_secret",
                "risk_classification": "critical",
            }
        )
        network = classify_operation_action(
            {
                "action_id": "network",
                "action_kind": "network_exposure_mutation",
                "operation_request_ref": "ir7x-006",
                "authority_notice_ref": "authority",
                "freshness_state": "fresh",
                "resource_target": "network_service",
                "risk_classification": "critical",
            }
        )

        self.assertEqual(OperationActionDecisionStatus.REFUSED, live.decision_status)
        self.assertIn("live_control_requested", live.refusal_reason_set)
        self.assertEqual(OperationActionDecisionStatus.REFUSED, credential.decision_status)
        self.assertIn("credential_access_requested", credential.refusal_reason_set)
        self.assertEqual(OperationActionDecisionStatus.REFUSED, network.decision_status)
        self.assertIn("network_mutation_requested", network.refusal_reason_set)

    def test_generated_path_policy_refuses_source_expected_and_mailbox_mutation(self) -> None:
        accepted = validate_generated_operations_output_path(
            "tests/fixtures/generated/ir7_operations_dry_run/reports/report.json",
            workspace_root=PROJECT_ROOT,
        )
        escape = validate_generated_operations_output_path("outside/report.json", workspace_root=PROJECT_ROOT)
        source_mutation = validate_generated_operations_output_path("docs/reviews/not_allowed.json", workspace_root=PROJECT_ROOT)
        expected_mutation = validate_generated_operations_output_path(
            "tests/fixtures/expected/ir7_operations_dry_run/not_allowed.sop",
            workspace_root=PROJECT_ROOT,
        )
        mailbox_mutation = validate_generated_operations_output_path(
            "platform/coordination/mailboxes/conversation.inbox/1.sop",
            workspace_root=PROJECT_ROOT,
        )

        self.assertTrue(accepted.accepted)
        self.assertFalse(escape.accepted)
        self.assertEqual("generated_operations_path_escape", escape.refusal_reason)
        self.assertFalse(source_mutation.accepted)
        self.assertEqual("source_expected_or_mailbox_mutation_refusal", source_mutation.refusal_reason)
        self.assertFalse(expected_mutation.accepted)
        self.assertEqual("source_expected_or_mailbox_mutation_refusal", expected_mutation.refusal_reason)
        self.assertFalse(mailbox_mutation.accepted)
        self.assertEqual("source_expected_or_mailbox_mutation_refusal", mailbox_mutation.refusal_reason)

    def test_generated_report_is_disposable_and_mailboxes_are_not_created(self) -> None:
        result = run_operations_dry_run_fixture_corpus(workspace_root=PROJECT_ROOT)[0]
        generated_path = "tests/fixtures/generated/ir7_operations_dry_run/reports/proof_report.json"
        policy = write_generated_operations_output(
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
        self.assertFalse(any(path.startswith("tests/fixtures/generated/ir7_operations_dry_run/") for path in discovered_paths))
        self.assertFalse(PLATFORM_MAILBOX_ROOT.exists())

        shutil.rmtree(GENERATED_ROOT)
        rebuilt = run_operations_dry_run_fixture_corpus(workspace_root=PROJECT_ROOT)
        self.assertEqual(13, len(rebuilt))
        self.assertTrue(all(item.comparison_report.passed for item in rebuilt))


def _operation_request(
    *,
    operation_request_id: str,
    intended_effect: str,
    resource_target: str,
    risk_classification: str = "bounded_dry_run",
    blast_radius: str = "bounded",
    predicted_side_effect_set: tuple[str, ...] = (),
):
    return operation_request_envelope_from_parts(
        operation_request_id=operation_request_id,
        operation_request_uuid=f"{operation_request_id}-uuid",
        request_created_at="2026-05-27",
        requested_by="codex",
        conversation_uuid="conversation-ir7-tests",
        carrier_surface="Codex thread state",
        source_ref_set=("docs/operations/IR7_Dry_Run_Request_Result_And_Refusal_Contract.v1.sop",),
        authority_notice_ref="docs/reviews/IR7_IA05_Completion_Review.v1.sop",
        authority_tier="operations_planning_record",
        freshness_state="fresh",
        parent_request_ref="none",
        completion_review_ref="docs/reviews/IR7_IA05_Completion_Review.v1.sop",
        supersedes_request_ref_set=(),
        source_projection_boundary_ref="IR7-S02",
        intended_effect=intended_effect,
        resource_target=resource_target,
        resource_target_classification="classified",
        risk_classification=risk_classification,
        blast_radius=blast_radius,
        dry_run_required=True,
        rollback_or_abort_route="abort_before_live_effect",
        credential_boundary_ref="no_secret_access",
        network_boundary_ref="no_network_mutation",
        human_approval_ref="empty_until_explicit_fresh_scoped_approval_exists",
        predicted_side_effect_set=predicted_side_effect_set,
        stale_after="boundary_change",
        refusal_policy_ref="IR7-S02",
        no_live_effect_rule_ref="IR7-S02",
    )


if __name__ == "__main__":
    unittest.main()
