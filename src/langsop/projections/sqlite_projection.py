"""SQLite projection writer for validated IR2 records."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass

from langsop.authority.validation import ValidationReport

from .sqlite_schema import DEFAULT_SCHEMA_VERSION, SQLiteProjectionSchema, define_sqlite_projection_schema


@dataclass(frozen=True)
class ProjectionWriteReport:
    """Report for a connection-level projection write."""

    projection_schema_version: str
    candidate_rows_written: int
    validation_rows_written: int
    proof_rows_written: int
    fault_rows_written: int
    stale_rows_written: int
    projection_status: str
    authority_notice: str = "generated_sqlite_non_authority"


def initialize_projection_schema(
    connection: sqlite3.Connection,
    schema: SQLiteProjectionSchema | None = None,
) -> SQLiteProjectionSchema:
    """Create projection tables and indexes on an existing connection."""

    active_schema = schema or define_sqlite_projection_schema()
    for table in active_schema.tables:
        connection.execute(table.create_sql())
    for index in active_schema.indexes:
        connection.execute(index.create_sql())
    connection.execute(
        "INSERT OR REPLACE INTO projection_metadata (key, value, projection_schema_version) VALUES (?, ?, ?)",
        ("authority_notice", "generated_sqlite_non_authority", active_schema.schema_version),
    )
    return active_schema


def write_validation_report(
    connection: sqlite3.Connection,
    validation_report: ValidationReport,
    schema: SQLiteProjectionSchema | None = None,
) -> ProjectionWriteReport:
    """Write validation report rows to an initialized SQLite connection."""

    active_schema = initialize_projection_schema(connection, schema)
    candidate_rows = 0
    validation_rows = 0
    proof_rows = 0
    fault_rows = 0
    stale_rows = 0

    with connection:
        for result in validation_report.candidate_results:
            candidate = result.candidate
            _write_candidate(connection, candidate, active_schema.schema_version)
            _write_source_refs(connection, candidate, active_schema.schema_version)
            _write_lineage_edges(connection, candidate, active_schema.schema_version)
            _write_validation_result(connection, result, active_schema.schema_version)
            candidate_rows += 1
            validation_rows += 1

        for proof in validation_report.proof_results:
            connection.execute(
                """
                INSERT OR REPLACE INTO proof_results
                (proof_id, proof_subject_ref, proof_kind, proof_status, proof_scope, proof_limit, projection_schema_version)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    proof.proof_id,
                    proof.proof_subject_ref,
                    proof.proof_kind,
                    proof.proof_status,
                    proof.proof_scope,
                    proof.proof_limit,
                    active_schema.schema_version,
                ),
            )
            proof_rows += 1

        for fault in validation_report.faults:
            connection.execute(
                """
                INSERT OR REPLACE INTO projection_faults
                (fault_id, fault_kind, fault_subject_ref, fault_severity, reason, projection_schema_version)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    fault.fault_id,
                    fault.fault_kind,
                    fault.fault_subject_ref,
                    fault.fault_severity,
                    fault.reason,
                    active_schema.schema_version,
                ),
            )
            fault_rows += 1

        for stale_ref in validation_report.stale_projection_refs:
            connection.execute(
                """
                INSERT OR REPLACE INTO freshness_events
                (stale_record_ref, required_recompute_ref, projection_schema_version)
                VALUES (?, ?, ?)
                """,
                (stale_ref, "projection_rebuild_required", active_schema.schema_version),
            )
            stale_rows += 1

    return ProjectionWriteReport(
        projection_schema_version=active_schema.schema_version,
        candidate_rows_written=candidate_rows,
        validation_rows_written=validation_rows,
        proof_rows_written=proof_rows,
        fault_rows_written=fault_rows,
        stale_rows_written=stale_rows,
        projection_status="written",
    )


def _write_candidate(connection: sqlite3.Connection, candidate, schema_version: str) -> None:
    source_path, source_hash = _source_path_and_hash(candidate.source_ref_set)
    connection.execute(
        """
        INSERT OR REPLACE INTO source_artifacts
        (source_path, source_hash, source_hash_algorithm, source_role, freshness_state, projection_schema_version)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (source_path, source_hash, "SHA256", candidate.record_kind, candidate.freshness_state, schema_version),
    )
    connection.execute(
        """
        INSERT OR REPLACE INTO kernel_record_candidates
        (record_id, record_kind, natural_key_value, natural_key_state, subject_id, authority_state,
         freshness_state, record_status, projection_status, payload_json, projection_schema_version)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            candidate.record_id,
            candidate.record_kind,
            candidate.natural_key,
            candidate.natural_key_state,
            candidate.subject_ref,
            candidate.authority_state,
            candidate.freshness_state,
            candidate.status,
            "projection_only",
            json.dumps(candidate.payload, sort_keys=True),
            schema_version,
        ),
    )


def _write_source_refs(connection: sqlite3.Connection, candidate, schema_version: str) -> None:
    for source_ref in candidate.source_ref_set:
        connection.execute(
            "INSERT INTO source_refs (record_id, source_ref, projection_schema_version) VALUES (?, ?, ?)",
            (candidate.record_id, source_ref, schema_version),
        )


def _write_lineage_edges(connection: sqlite3.Connection, candidate, schema_version: str) -> None:
    for edge_ref in candidate.lineage_edge_set:
        edge_kind = edge_ref.split(":", maxsplit=1)[0]
        connection.execute(
            "INSERT INTO lineage_edges (record_id, edge_ref, edge_kind, projection_schema_version) VALUES (?, ?, ?, ?)",
            (candidate.record_id, edge_ref, edge_kind, schema_version),
        )


def _write_validation_result(connection: sqlite3.Connection, result, schema_version: str) -> None:
    connection.execute(
        """
        INSERT OR REPLACE INTO validation_results
        (record_id, hash_check_status, signature_check_status, lineage_check_status, freshness_check_status,
         classification, proof_status, fault_or_interrupt, projection_schema_version)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            result.candidate.record_id,
            result.hash_check_status,
            result.signature_check_status,
            result.lineage_check_status,
            result.freshness_check_status,
            result.authority_classification,
            result.proof_result_status,
            result.fault_or_interrupt,
            schema_version,
        ),
    )


def _source_path_and_hash(source_ref_set: tuple[str, ...]) -> tuple[str, str]:
    source_path = ""
    source_hash = ""
    for source_ref in source_ref_set:
        if source_ref.startswith("source_path:"):
            source_path = source_ref.removeprefix("source_path:")
        elif source_ref.startswith("source_hash:"):
            source_hash = source_ref.removeprefix("source_hash:")
    return source_path, source_hash
