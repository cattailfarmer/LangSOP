"""P8 fixture material contract and generated-output boundary tests."""

from __future__ import annotations

import pathlib
import shutil
import sys
import unittest


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from langsop.authority.discovery import discover_sop_artifacts  # noqa: E402


GENERATED_ROOT = PROJECT_ROOT / "tests" / "fixtures" / "generated" / "p8_fixture_material"
PLATFORM_MAILBOX_ROOT = PROJECT_ROOT / "platform" / "coordination" / "mailboxes"

FIXTURE_SOURCE_PATHS = (
    "tests/fixtures/sop/p2_authority_kernel/valid_signed_authority_record.sop",
    "tests/fixtures/sop/p2_authority_kernel/stale_source_hash_blocks_ready.sop",
    "tests/fixtures/sop/p2_authority_kernel/generated_projection_promotion_fault.sop",
    "tests/fixtures/sop/p2_authority_kernel/missing_sjs_signature_refusal.sop",
    "tests/fixtures/sop/p3_operator_contracts/valid_signature_validation_operator.sop",
    "tests/fixtures/sop/p3_operator_contracts/unsupported_operator_scope_refusal.sop",
    "tests/fixtures/sop/p3_operator_contracts/deterministic_replay_mismatch_fault.sop",
    "tests/fixtures/sop/p3_operator_contracts/generated_output_as_authority_fault.sop",
    "tests/fixtures/sop/p4_packetization/ready_packet_candidate.sop",
    "tests/fixtures/sop/p4_packetization/blocked_requirement_packet.sop",
    "tests/fixtures/sop/p4_packetization/false_ready_packet_fault.sop",
    "tests/fixtures/sop/p4_packetization/no_dispatch_packet_boundary.sop",
    "tests/fixtures/sop/p5_runtime_proof/valid_runtime_transition_trace.sop",
    "tests/fixtures/sop/p5_runtime_proof/checkpoint_non_authority.sop",
    "tests/fixtures/sop/p5_runtime_proof/sop_interrupt_handoff.sop",
    "tests/fixtures/sop/p5_runtime_proof/stale_checkpoint_rebake_required.sop",
    "tests/fixtures/sop/p6_surface_projection/manager_authority_notice_projection.sop",
    "tests/fixtures/sop/p6_surface_projection/stale_surface_projection.sop",
    "tests/fixtures/sop/p6_surface_projection/inbound_action_mutation_refusal.sop",
    "tests/fixtures/sop/p6_surface_projection/generated_projection_non_authority.sop",
    "tests/fixtures/sop/p8_proof_fixtures/fixture_path_policy_valid.sop",
    "tests/fixtures/sop/p8_proof_fixtures/proof_ledger_acceptance.sop",
    "tests/fixtures/sop/p8_proof_fixtures/expected_ledger_non_authority.sop",
    "tests/fixtures/sop/p8_proof_fixtures/negative_oracle_fault_route.sop",
)

EXPECTED_LEDGER_PATHS = (
    "tests/fixtures/expected/p2_authority_kernel/authority_validation_expected.sop",
    "tests/fixtures/expected/p2_authority_kernel/stale_and_signature_refusal_expected.sop",
    "tests/fixtures/expected/p3_operator_contracts/operator_trace_expected.sop",
    "tests/fixtures/expected/p3_operator_contracts/operator_fault_refusal_expected.sop",
    "tests/fixtures/expected/p4_packetization/readiness_packet_expected.sop",
    "tests/fixtures/expected/p4_packetization/no_dispatch_boundary_expected.sop",
    "tests/fixtures/expected/p5_runtime_proof/runtime_transition_expected.sop",
    "tests/fixtures/expected/p5_runtime_proof/interrupt_and_checkpoint_expected.sop",
    "tests/fixtures/expected/p6_surface_projection/authority_projection_expected.sop",
    "tests/fixtures/expected/p6_surface_projection/nonpromotion_and_action_refusal_expected.sop",
    "tests/fixtures/expected/p8_proof_fixtures/fixture_policy_expected.sop",
    "tests/fixtures/expected/p8_proof_fixtures/proof_ledger_acceptance_expected.sop",
    "tests/fixtures/expected/p8_proof_fixtures/negative_oracle_expected.sop",
)

PROOF_LEDGER_PATHS = (
    "docs/proofs/p8_fixture_material/P8_Fixture_Material_Source_File_Inventory_Ledger.v1.sop",
    "docs/proofs/p8_fixture_material/P8_Fixture_Material_Expected_Ledger_Index.v1.sop",
    "docs/proofs/p8_fixture_material/P8_Fixture_Material_Generated_Output_Index.v1.sop",
    "docs/proofs/p8_fixture_material/P8_Fixture_Material_No_Dispatch_And_No_Live_Effect_Ledger.v1.sop",
    "docs/proofs/p8_fixture_material/P8_Fixture_Material_Validation_Result_Ledger.v1.sop",
)

NEGATIVE_ORACLE_CASES = (
    "stale source hash blocks ready",
    "missing SJS signature refusal",
    "generated projection promotion fault",
    "unsupported operator scope refusal",
    "deterministic replay mismatch fault",
    "generated operator output as authority",
    "blocked requirement packet",
    "false ready packet",
    "no dispatch packet boundary",
    "checkpoint not authority",
    "stale checkpoint rebake required",
    "surface action mutation refusal",
    "generated projection non authority",
    "expected ledger non authority",
    "fixture success promoted to live control",
)


class P8FixtureMaterialContractTests(unittest.TestCase):
    def tearDown(self) -> None:
        if GENERATED_ROOT.exists():
            shutil.rmtree(GENERATED_ROOT)

    def test_fixture_source_expected_ledgers_and_proof_ledgers_are_present(self) -> None:
        self.assertEqual(24, len(FIXTURE_SOURCE_PATHS))
        self.assertEqual(13, len(EXPECTED_LEDGER_PATHS))
        self.assertEqual(5, len(PROOF_LEDGER_PATHS))

        for relative_path in (*FIXTURE_SOURCE_PATHS, *EXPECTED_LEDGER_PATHS, *PROOF_LEDGER_PATHS):
            path = PROJECT_ROOT / relative_path
            self.assertTrue(path.exists(), relative_path)
            self.assertIn("Subject:", path.read_text(encoding="utf-8"))

    def test_generated_path_contract_refuses_authority_and_live_effect_targets(self) -> None:
        contract = _read("docs/implementation/P8_Generated_Path_Policy_And_Proof_Runner_Contract.v1.sop")

        for accepted_root in (
            "tests/fixtures/generated/p2_authority_kernel/",
            "tests/fixtures/generated/p3_operator_contracts/",
            "tests/fixtures/generated/p4_packetization/",
            "tests/fixtures/generated/p5_runtime_proof/",
            "tests/fixtures/generated/p6_surface_projection/",
            "tests/fixtures/generated/p8_proof_fixtures/",
            "tests/fixtures/generated/p8_fixture_material/proof_results/",
            "tests/fixtures/generated/p8_fixture_material/reports/",
        ):
            self.assertIn(f"[accepted_generated_output_root] is {accepted_root}", contract)

        for refused in (
            "docs/source/",
            "docs/canonical/",
            "docs/slices/",
            "docs/reviews/",
            "docs/proofs/",
            "src/",
            "tests/fixtures/sop/",
            "tests/fixtures/expected/",
            "platform/coordination/mailboxes/",
            ".git/",
            "credential_file",
            "assignment_record",
            "dispatch_record",
            "operations_target",
            "live_control_target",
        ):
            self.assertIn(refused, contract)

        self.assertIn("[proof_runner_code_creation_authorized] is false_by_this_slice", contract)
        self.assertFalse((PROJECT_ROOT / "src" / "langsop" / "fixtures").exists())

    def test_negative_oracle_cases_preserve_fault_and_nonpromotion_routes(self) -> None:
        oracle = _read("docs/fixtures/P8_Negative_Oracle_Source_Material_And_Fault_Route_Refinement.v1.sop")
        contract = _read("docs/implementation/P8_Generated_Path_Policy_And_Proof_Runner_Contract.v1.sop")

        self.assertEqual(15, oracle.count("+ [oracle_case] is "))
        for case_name in NEGATIVE_ORACLE_CASES:
            self.assertIn(case_name, oracle)

        self.assertIn("fixture_success_as_live_control_authority", oracle)
        self.assertIn("expected_ledger_as_canonical_authority", oracle)
        self.assertIn("generated_output_promoted_to_authority", oracle)
        self.assertIn("fail validation when any negative oracle case is accepted as ready", contract)

    def test_generated_outputs_are_ignored_disposable_and_rebuildable(self) -> None:
        self.assertIn("tests/fixtures/generated/", _read(".gitignore"))

        report_path = GENERATED_ROOT / "proof_results" / "generated_boundary_probe.sop"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            "\n".join(
                (
                    "Subject: Generated P8 Boundary Probe",
                    "Authority: generated_output_non_authority",
                    "Notice: not_source_authority",
                    "Notice: not_dispatch_authority",
                    "Notice: not_operations_authority",
                    "Notice: not_live_control_authority",
                    "",
                )
            ),
            encoding="utf-8",
        )

        discovered_paths = {artifact.source_path for artifact in discover_sop_artifacts(PROJECT_ROOT).artifacts}
        self.assertFalse(any(path.startswith("tests/fixtures/generated/") for path in discovered_paths))
        self.assertFalse(PLATFORM_MAILBOX_ROOT.exists())

        shutil.rmtree(GENERATED_ROOT)
        for relative_path in FIXTURE_SOURCE_PATHS:
            self.assertTrue((PROJECT_ROOT / relative_path).exists(), relative_path)

    def test_proof_ledgers_refuse_dispatch_operations_and_live_control_authority(self) -> None:
        generated_index = _read(
            "docs/proofs/p8_fixture_material/P8_Fixture_Material_Generated_Output_Index.v1.sop"
        )
        no_live_ledger = _read(
            "docs/proofs/p8_fixture_material/P8_Fixture_Material_No_Dispatch_And_No_Live_Effect_Ledger.v1.sop"
        )

        self.assertIn("[authority_class] is generated_output_non_authority", generated_index)
        self.assertIn("[source_authority_status] is false", generated_index)
        self.assertIn("[rebuildability_required] is true", generated_index)
        self.assertIn("[assignment_authorized] is false", no_live_ledger)
        self.assertIn("[dispatch_authorized] is false", no_live_ledger)
        self.assertIn("[operations_control_authorized] is false", no_live_ledger)
        self.assertIn("[live_machine_control_authorized] is false", no_live_ledger)
        self.assertIn("reject fixture success as authority", no_live_ledger)


def _read(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
