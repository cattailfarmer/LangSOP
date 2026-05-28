"""P6 surface implementation contract and generated-projection boundary tests."""

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
from langsop.surfaces_p6.fixture_runner import run_p6_surface_fixture_corpus  # noqa: E402
from langsop.surfaces_p6.generated_paths import (  # noqa: E402
    NON_AUTHORITY_WARNING,
    validate_generated_p6_surface_output_path,
    validate_p6_surface_expected_ledger_path,
    validate_tracked_p6_surface_fixture_source_path,
    write_generated_p6_surface_output,
)


FIXTURE_ROOT = PROJECT_ROOT / "tests" / "fixtures" / "sop" / "p6_surface_projection"
EXPECTED_ROOT = PROJECT_ROOT / "tests" / "fixtures" / "expected" / "p6_surface_projection"
GENERATED_ROOT = PROJECT_ROOT / "tests" / "fixtures" / "generated" / "p6_surface_implementation"
POLICY_DOC = PROJECT_ROOT / "docs" / "implementation" / (
    "P6_Generated_Projection_Path_Policy_And_Fixture_Runner_Contract.v1.sop"
)
PROOF_DOC = PROJECT_ROOT / "docs" / "reviews" / (
    "P6_Surface_Generated_Projection_Nonpromotion_And_No_Live_Effect_Proof.v1.sop"
)


class P6SurfaceImplementationContractTests(unittest.TestCase):
    def tearDown(self) -> None:
        if GENERATED_ROOT.exists():
            shutil.rmtree(GENERATED_ROOT)

    def test_surface_fixture_runner_classifies_accepted_fixture_material(self) -> None:
        results = {result.fixture_source.fixture_id: result for result in run_p6_surface_fixture_corpus(workspace_root=PROJECT_ROOT)}

        self.assertEqual(
            {
                "generated_projection_non_authority",
                "inbound_action_mutation_refusal",
                "manager_authority_notice_projection",
                "stale_surface_projection",
            },
            set(results),
        )
        self.assertTrue(all(result.comparison_report.passed for result in results.values()))

        manager = results["manager_authority_notice_projection"].projection_record
        self.assertEqual("visible_authority_notice", manager.projection_state)
        self.assertEqual("ready", manager.projected_status)
        self.assertFalse(manager.source_authority_promoted)

        stale = results["stale_surface_projection"].projection_record
        self.assertEqual("visible_stale_notice", stale.projection_state)
        self.assertEqual("stale", stale.projected_status)
        self.assertFalse(stale.surface_mutation_authority)

        inbound = results["inbound_action_mutation_refusal"].projection_record
        self.assertEqual("refused", inbound.action_result)
        self.assertIn("surface_cannot_mutate_source_authority", inbound.refusal_kind_set)
        self.assertFalse(inbound.dispatch_authorized)

        generated = results["generated_projection_non_authority"].projection_record
        self.assertEqual("faulted", generated.projection_state)
        self.assertIn("generated_projection_promoted_to_authority", generated.fault_kind_set)
        self.assertFalse(generated.generated_projection_authority)

    def test_path_policy_accepts_only_p6_fixture_ledgers_and_generated_roots(self) -> None:
        fixture_policy = validate_tracked_p6_surface_fixture_source_path(
            "tests/fixtures/sop/p6_surface_projection/manager_authority_notice_projection.sop",
            workspace_root=PROJECT_ROOT,
        )
        ledger_policy = validate_p6_surface_expected_ledger_path(
            "tests/fixtures/expected/p6_surface_projection/authority_projection_expected.sop",
            workspace_root=PROJECT_ROOT,
        )
        generated_policy = validate_generated_p6_surface_output_path(
            "tests/fixtures/generated/p6_surface_implementation/proof_results/generated_surface_probe.sop",
            workspace_root=PROJECT_ROOT,
        )

        self.assertTrue(fixture_policy.accepted)
        self.assertTrue(ledger_policy.accepted)
        self.assertTrue(generated_policy.accepted)

        for refused_path in (
            "docs/reviews/generated_surface_probe.sop",
            "src/langsop/surfaces_p6/generated_surface_probe.py",
            "tests/fixtures/sop/p6_surface_projection/generated_surface_probe.sop",
            "tests/fixtures/expected/p6_surface_projection/generated_surface_probe.sop",
            "platform/coordination/mailboxes/generated_surface_probe.sop",
            ".git/config",
        ):
            with self.subTest(refused_path=refused_path):
                policy = validate_generated_p6_surface_output_path(refused_path, workspace_root=PROJECT_ROOT)
                self.assertFalse(policy.accepted)

    def test_generated_projection_policy_document_refuses_authority_and_live_effect_targets(self) -> None:
        contract = _read(POLICY_DOC)

        for accepted_root in (
            "tests/fixtures/generated/p6_surface_projection/",
            "tests/fixtures/generated/p6_surface_projection/projections/",
            "tests/fixtures/generated/p6_surface_projection/reports/",
            "tests/fixtures/generated/p6_surface_implementation/proof_results/",
            "tests/fixtures/generated/p6_surface_implementation/reports/",
            ".langsop/projections/p6_surface_projection/",
            ".langsop/reports/p6_surface_projection/",
        ):
            self.assertIn(f"[accepted_generated_projection_root] is {accepted_root}", contract)

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
            "network_path",
            "destructive_filesystem_target",
            "assignment_record",
            "dispatch_record",
            "operations_target",
            "live_control_target",
        ):
            self.assertIn(refused, contract)

    def test_generated_outputs_are_ignored_disposable_and_not_authority(self) -> None:
        self.assertIn("tests/fixtures/generated/", _read(PROJECT_ROOT / ".gitignore"))

        report_path = GENERATED_ROOT / "proof_results" / "generated_surface_probe.sop"
        policy = write_generated_p6_surface_output(
            report_path,
            {
                "subject": "Generated P6 Surface Probe",
                "authority": "generated_output_non_authority",
                "nonpromotion_notice": NON_AUTHORITY_WARNING,
                "source_authority_status": False,
                "assignment_authorized": False,
                "dispatch_authorized": False,
                "operations_control_authorized": False,
                "live_machine_control_authorized": False,
            },
            workspace_root=PROJECT_ROOT,
        )
        self.assertTrue(policy.accepted)
        self.assertTrue(report_path.exists())

        discovered_paths = {artifact.source_path for artifact in discover_sop_artifacts(PROJECT_ROOT).artifacts}
        self.assertFalse(any(path.startswith("tests/fixtures/generated/") for path in discovered_paths))

        shutil.rmtree(GENERATED_ROOT)
        for fixture_path in FIXTURE_ROOT.glob("*.sop"):
            self.assertTrue(fixture_path.exists(), fixture_path)
        for ledger_path in EXPECTED_ROOT.glob("*.sop"):
            self.assertTrue(ledger_path.exists(), ledger_path)

    def test_generated_projection_proof_preserves_no_live_effect_boundary(self) -> None:
        proof = _read(PROOF_DOC)

        self.assertIn("[generated_projection_authority_status] is false", proof)
        self.assertIn("[source_authority_status] is false", proof)
        self.assertIn("[surface_mutation_authority] is false", proof)
        self.assertIn("[assignment_authorized] is false", proof)
        self.assertIn("[dispatch_authorized] is false", proof)
        self.assertIn("[operations_control_authorized] is false", proof)
        self.assertIn("[live_machine_control_authorized] is false", proof)
        self.assertIn("reject generated projection promotion", proof)
        self.assertIn("reject surface action mutation", proof)
        self.assertIn("reject fixture success as authority", proof)


def _read(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
