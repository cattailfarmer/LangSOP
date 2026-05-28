"""P5 runtime implementation contract and generated-trace boundary tests."""

from __future__ import annotations

import pathlib
import re
import shutil
import sys
import unittest


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from langsop.authority.discovery import discover_sop_artifacts  # noqa: E402
from langsop.runtime import (  # noqa: E402
    NO_DISPATCH_NOTICE,
    NO_LIVE_EFFECT_NOTICE,
    NO_OPERATIONS_CONTROL_NOTICE,
    P5RuntimeIssueKind,
    P5RuntimeState,
    build_p5_transition_evidence,
    evaluate_p5_runtime_fields,
    runtime_evaluation_fact_set,
)


FIXTURE_ROOT = PROJECT_ROOT / "tests" / "fixtures" / "sop" / "p5_runtime_proof"
GENERATED_ROOT = PROJECT_ROOT / "tests" / "fixtures" / "generated" / "p5_runtime_implementation"
POLICY_DOC = PROJECT_ROOT / "docs" / "implementation" / (
    "P5_Generated_Trace_Path_Policy_And_Fixture_Runner_Contract.v1.sop"
)
PROOF_DOC = PROJECT_ROOT / "docs" / "reviews" / (
    "P5_Runtime_Generated_Trace_Nonpromotion_And_No_Live_Effect_Proof.v1.sop"
)
FIELD_RE = re.compile(r"^\s*\+ \[(?P<name>[^\]]+)\] is (?P<value>.*)$")


class P5RuntimeImplementationContractTests(unittest.TestCase):
    def tearDown(self) -> None:
        if GENERATED_ROOT.exists():
            shutil.rmtree(GENERATED_ROOT)

    def test_runtime_fixture_model_classifies_accepted_fixture_material(self) -> None:
        valid = evaluate_p5_runtime_fields(_fields("valid_runtime_transition_trace.sop"))
        checkpoint = evaluate_p5_runtime_fields(_fields("checkpoint_non_authority.sop"))
        interrupt = evaluate_p5_runtime_fields(_fields("sop_interrupt_handoff.sop"))
        stale = evaluate_p5_runtime_fields(_fields("stale_checkpoint_rebake_required.sop"))

        self.assertTrue(valid.accepted)
        self.assertTrue(valid.authority_safe)
        self.assertEqual(P5RuntimeState.TRANSITION_ACCEPTED, valid.runtime_state)

        self.assertFalse(checkpoint.accepted)
        self.assertFalse(checkpoint.authority_safe)
        self.assertEqual(P5RuntimeState.REFUSED, checkpoint.runtime_state)
        self.assertEqual(P5RuntimeIssueKind.CHECKPOINT_NOT_AUTHORITY, checkpoint.issue_kind)

        self.assertEqual(P5RuntimeState.INTERRUPTED, interrupt.runtime_state)
        self.assertEqual(P5RuntimeIssueKind.AMBIGUOUS_AUTHORITY, interrupt.issue_kind)
        self.assertEqual(NO_DISPATCH_NOTICE, interrupt.no_dispatch_notice)
        self.assertEqual(NO_LIVE_EFFECT_NOTICE, interrupt.no_live_effect_notice)

        self.assertEqual(P5RuntimeState.REBAKE_REQUIRED, stale.runtime_state)
        self.assertEqual(P5RuntimeIssueKind.STALE_CHECKPOINT, stale.issue_kind)
        self.assertTrue(stale.rebake_required)

    def test_transition_evidence_is_deterministic_and_non_authoritative(self) -> None:
        evaluation = evaluate_p5_runtime_fields(_fields("valid_runtime_transition_trace.sop"))
        first = build_p5_transition_evidence(
            evaluation,
            input_ref_set=("tests/fixtures/sop/p5_runtime_proof/valid_runtime_transition_trace.sop",),
            authority_basis_ref_set=("docs/reviews/P5_IA03_Completion_Review.v1.sop",),
        )
        second = build_p5_transition_evidence(
            evaluation,
            input_ref_set=("tests/fixtures/sop/p5_runtime_proof/valid_runtime_transition_trace.sop",),
            authority_basis_ref_set=("docs/reviews/P5_IA03_Completion_Review.v1.sop",),
        )
        facts = runtime_evaluation_fact_set(evaluation)

        self.assertEqual(first.transition_id, second.transition_id)
        self.assertIn("checkpoint_authority is false", facts)
        self.assertIn("dispatch_authority is false", facts)
        self.assertIn("operations_control_authority is false", facts)
        self.assertIn("live_control_authority is false", facts)
        self.assertIn(f"no_dispatch_notice is {NO_DISPATCH_NOTICE}", facts)
        self.assertIn(f"no_operations_control_notice is {NO_OPERATIONS_CONTROL_NOTICE}", facts)
        self.assertIn(f"no_live_effect_notice is {NO_LIVE_EFFECT_NOTICE}", facts)

    def test_generated_trace_policy_refuses_authority_and_live_effect_targets(self) -> None:
        contract = _read(POLICY_DOC)

        for accepted_root in (
            "tests/fixtures/generated/p5_runtime_proof/checkpoints/",
            "tests/fixtures/generated/p5_runtime_proof/traces/",
            "tests/fixtures/generated/p5_runtime_proof/reports/",
            "tests/fixtures/generated/p5_runtime_implementation/proof_results/",
            "tests/fixtures/generated/p5_runtime_implementation/reports/",
            ".langsop/checkpoints/p5_runtime_proof/",
            ".langsop/traces/p5_runtime_proof/",
            ".langsop/reports/p5_runtime_proof/",
        ):
            self.assertIn(f"[accepted_generated_trace_root] is {accepted_root}", contract)

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

        report_path = GENERATED_ROOT / "proof_results" / "generated_runtime_probe.sop"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            "\n".join(
                (
                    "Subject: Generated P5 Runtime Probe",
                    "Authority: generated_output_non_authority",
                    "Notice: not_source_authority",
                    "Notice: not_assignment_authority",
                    "Notice: not_dispatch_authority",
                    "Notice: not_operations_control_authority",
                    "Notice: not_live_control_authority",
                    "",
                )
            ),
            encoding="utf-8",
        )

        discovered_paths = {artifact.source_path for artifact in discover_sop_artifacts(PROJECT_ROOT).artifacts}
        self.assertNotIn(
            "tests/fixtures/generated/p5_runtime_implementation/proof_results/generated_runtime_probe.sop",
            discovered_paths,
        )

        shutil.rmtree(GENERATED_ROOT)
        for fixture_path in FIXTURE_ROOT.glob("*.sop"):
            self.assertTrue(fixture_path.exists(), fixture_path)

    def test_generated_trace_proof_preserves_no_live_effect_boundary(self) -> None:
        proof = _read(PROOF_DOC)

        self.assertIn("[generated_trace_authority_status] is false", proof)
        self.assertIn("[assignment_authorized] is false", proof)
        self.assertIn("[dispatch_authorized] is false", proof)
        self.assertIn("[operations_control_authorized] is false", proof)
        self.assertIn("[live_machine_control_authorized] is false", proof)
        self.assertIn("reject checkpoint or generated trace promotion", proof)


def _fields(fixture_name: str) -> dict[str, tuple[str, ...]]:
    fields: dict[str, tuple[str, ...]] = {}
    for line in _read(FIXTURE_ROOT / fixture_name).splitlines():
        match = FIELD_RE.match(line)
        if match is None:
            continue
        name = match.group("name")
        value = match.group("value").strip()
        fields[name] = fields.get(name, ()) + (value,)
    return fields


def _read(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
