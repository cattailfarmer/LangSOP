"""IR2 parser/projection contract tests."""

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
from langsop.authority.extraction import extract_kernel_record_candidates  # noqa: E402
from langsop.authority.sop_parser import parse_sop_document  # noqa: E402
from langsop.authority.validation import validate_kernel_record_candidates  # noqa: E402
from langsop.projections.rebuild import (  # noqa: E402
    rebuild_sqlite_projection,
    rebuild_sqlite_projection_in_memory,
)


FIXTURE_ROOT = "tests/fixtures/sop/ir2_parser_projection/"
GENERATED_ROOT = PROJECT_ROOT / "tests" / "fixtures" / "generated" / "ir2_parser_projection"


class IR2ParserProjectionContractTests(unittest.TestCase):
    def tearDown(self) -> None:
        if GENERATED_ROOT.exists():
            shutil.rmtree(GENERATED_ROOT)

    def test_discovery_finds_fixture_sources_and_excludes_generated_outputs(self) -> None:
        GENERATED_ROOT.mkdir(parents=True, exist_ok=True)
        generated_source = GENERATED_ROOT / "generated_projection_non_authority.sop"
        generated_source.write_text("Subject: Generated\n", encoding="utf-8")

        result = discover_sop_artifacts(PROJECT_ROOT)
        fixture_paths = {artifact.source_path for artifact in result.artifacts if artifact.source_path.startswith(FIXTURE_ROOT)}

        self.assertEqual(10, len(fixture_paths))
        self.assertNotIn("tests/fixtures/generated/ir2_parser_projection/generated_projection_non_authority.sop", fixture_paths)

    def test_parser_preserves_malformed_fixture_fault(self) -> None:
        fixture = _artifact("malformed_sop_structure.sop")
        parsed = parse_sop_document(fixture)

        self.assertEqual(1, len(parsed.faults))
        self.assertEqual("unknown_marker", parsed.faults[0].fault_kind)
        self.assertTrue(any(event.parse_status == "fault" for event in parsed.events))

    def test_extraction_and_validation_preserve_fixture_outcomes(self) -> None:
        report = _validation_report()
        outcomes = {
            result.candidate.payload.get("fixture_id"): result
            for result in report.candidate_results
        }

        self.assertEqual(10, len(outcomes))
        self.assertEqual("signed_sjs_authority_candidate", outcomes["valid_signed_canonical_artifact"].authority_classification)
        self.assertEqual("source_only", outcomes["source_only_unprocessed_artifact"].authority_classification)
        self.assertEqual("wrong_protocol", outcomes["wrong_protocol_signature"].fault_or_interrupt)
        self.assertEqual("stale", outcomes["stale_source_hash"].freshness_check_status)
        self.assertEqual("malformed_line", outcomes["malformed_sop_structure"].fault_or_interrupt)
        self.assertEqual("source_mutation_forbidden", outcomes["source_mutation_refusal"].fault_or_interrupt)
        self.assertEqual(1, len(report.stale_projection_refs))

    def test_in_memory_projection_keeps_non_authority_notice(self) -> None:
        connection, write_report = rebuild_sqlite_projection_in_memory(_validation_report())
        try:
            candidate_rows = connection.execute("select count(*) from kernel_record_candidates").fetchone()[0]
            notice = connection.execute("select value from projection_metadata where key='authority_notice'").fetchone()[0]
        finally:
            connection.close()

        self.assertEqual(10, write_report.candidate_rows_written)
        self.assertEqual(10, candidate_rows)
        self.assertEqual("generated_sqlite_non_authority", notice)

    def test_rebuild_refuses_outputs_outside_generated_roots(self) -> None:
        with self.assertRaises(ValueError):
            rebuild_sqlite_projection(_validation_report(), PROJECT_ROOT / "docs" / "forbidden.sqlite3")

    def test_rebuild_writes_only_ignored_generated_fixture_output(self) -> None:
        output_path = pathlib.Path("tests/fixtures/generated/ir2_parser_projection/test_projection.sqlite3")
        rebuild_report = rebuild_sqlite_projection(_validation_report(), output_path)

        self.assertEqual("written", rebuild_report.rebuild_status)
        self.assertTrue((PROJECT_ROOT / output_path).exists())
        discovered_paths = {artifact.source_path for artifact in discover_sop_artifacts(PROJECT_ROOT).artifacts}
        self.assertNotIn(output_path.as_posix(), discovered_paths)


def _artifact(file_name: str):
    artifacts = discover_sop_artifacts(PROJECT_ROOT).artifacts
    source_path = f"{FIXTURE_ROOT}{file_name}"
    for artifact in artifacts:
        if artifact.source_path == source_path:
            return artifact
    raise AssertionError(f"Fixture not discovered: {source_path}")


def _validation_report():
    candidates = []
    for artifact in discover_sop_artifacts(PROJECT_ROOT).artifacts:
        if artifact.source_path.startswith(FIXTURE_ROOT):
            parsed = parse_sop_document(artifact)
            candidates.extend(extract_kernel_record_candidates(parsed).candidates)
    return validate_kernel_record_candidates(candidates)


if __name__ == "__main__":
    unittest.main()
