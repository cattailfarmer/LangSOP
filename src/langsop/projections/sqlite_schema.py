"""SQLite projection schema declaration for LangSOP IR2."""

from __future__ import annotations

from dataclasses import dataclass, field


DEFAULT_SCHEMA_VERSION = "ir2-sqlite-projection-v1"


@dataclass(frozen=True)
class ColumnDefinition:
    name: str
    type_sql: str
    constraints: str = ""

    def sql(self) -> str:
        parts = [self.name, self.type_sql, self.constraints]
        return " ".join(part for part in parts if part)


@dataclass(frozen=True)
class TableDefinition:
    name: str
    columns: tuple[ColumnDefinition, ...]

    def create_sql(self) -> str:
        column_sql = ", ".join(column.sql() for column in self.columns)
        return f"CREATE TABLE IF NOT EXISTS {self.name} ({column_sql})"


@dataclass(frozen=True)
class IndexDefinition:
    name: str
    table_name: str
    columns: tuple[str, ...]

    def create_sql(self) -> str:
        column_sql = ", ".join(self.columns)
        return f"CREATE INDEX IF NOT EXISTS {self.name} ON {self.table_name} ({column_sql})"


@dataclass(frozen=True)
class SQLiteProjectionSchema:
    schema_version: str
    tables: tuple[TableDefinition, ...] = field(default_factory=tuple)
    indexes: tuple[IndexDefinition, ...] = field(default_factory=tuple)


def define_sqlite_projection_schema(schema_version: str = DEFAULT_SCHEMA_VERSION) -> SQLiteProjectionSchema:
    """Return the IR2 SQLite projection schema."""

    tables = (
        _table(
            "projection_metadata",
            ("key", "TEXT", "PRIMARY KEY"),
            ("value", "TEXT", ""),
            ("projection_schema_version", "TEXT", "NOT NULL"),
        ),
        _table(
            "source_artifacts",
            ("source_path", "TEXT", "PRIMARY KEY"),
            ("source_hash", "TEXT", "NOT NULL"),
            ("source_hash_algorithm", "TEXT", "NOT NULL"),
            ("source_role", "TEXT", "NOT NULL"),
            ("freshness_state", "TEXT", "NOT NULL"),
            ("projection_schema_version", "TEXT", "NOT NULL"),
        ),
        _table(
            "parse_events",
            ("source_path", "TEXT", "NOT NULL"),
            ("source_hash", "TEXT", "NOT NULL"),
            ("line_number", "INTEGER", "NOT NULL"),
            ("raw_text_hash", "TEXT", "NOT NULL"),
            ("marker_kind", "TEXT", "NOT NULL"),
            ("bracket_label", "TEXT", "NOT NULL"),
            ("parent_line_ref", "INTEGER", ""),
            ("parse_status", "TEXT", "NOT NULL"),
            ("parse_fault_refs", "TEXT", "NOT NULL"),
            ("projection_schema_version", "TEXT", "NOT NULL"),
            ("PRIMARY KEY", "(source_path, line_number)", ""),
        ),
        _table(
            "parse_faults",
            ("fault_id", "TEXT", "PRIMARY KEY"),
            ("source_path", "TEXT", "NOT NULL"),
            ("source_hash", "TEXT", "NOT NULL"),
            ("line_number", "INTEGER", "NOT NULL"),
            ("fault_kind", "TEXT", "NOT NULL"),
            ("fault_severity", "TEXT", "NOT NULL"),
            ("recovery_action", "TEXT", "NOT NULL"),
            ("downstream_effect", "TEXT", "NOT NULL"),
        ),
        _table(
            "kernel_record_candidates",
            ("record_id", "TEXT", "PRIMARY KEY"),
            ("record_kind", "TEXT", "NOT NULL"),
            ("natural_key_value", "TEXT", "NOT NULL"),
            ("natural_key_state", "TEXT", "NOT NULL"),
            ("subject_id", "TEXT", "NOT NULL"),
            ("authority_state", "TEXT", "NOT NULL"),
            ("freshness_state", "TEXT", "NOT NULL"),
            ("record_status", "TEXT", "NOT NULL"),
            ("projection_status", "TEXT", "NOT NULL"),
            ("payload_json", "TEXT", "NOT NULL"),
            ("projection_schema_version", "TEXT", "NOT NULL"),
        ),
        _table(
            "source_refs",
            ("record_id", "TEXT", "NOT NULL"),
            ("source_ref", "TEXT", "NOT NULL"),
            ("projection_schema_version", "TEXT", "NOT NULL"),
        ),
        _table(
            "lineage_edges",
            ("record_id", "TEXT", "NOT NULL"),
            ("edge_ref", "TEXT", "NOT NULL"),
            ("edge_kind", "TEXT", "NOT NULL"),
            ("projection_schema_version", "TEXT", "NOT NULL"),
        ),
        _table(
            "validation_results",
            ("record_id", "TEXT", "PRIMARY KEY"),
            ("hash_check_status", "TEXT", "NOT NULL"),
            ("signature_check_status", "TEXT", "NOT NULL"),
            ("lineage_check_status", "TEXT", "NOT NULL"),
            ("freshness_check_status", "TEXT", "NOT NULL"),
            ("classification", "TEXT", "NOT NULL"),
            ("proof_status", "TEXT", "NOT NULL"),
            ("fault_or_interrupt", "TEXT", "NOT NULL"),
            ("projection_schema_version", "TEXT", "NOT NULL"),
        ),
        _table(
            "proof_results",
            ("proof_id", "TEXT", "PRIMARY KEY"),
            ("proof_subject_ref", "TEXT", "NOT NULL"),
            ("proof_kind", "TEXT", "NOT NULL"),
            ("proof_status", "TEXT", "NOT NULL"),
            ("proof_scope", "TEXT", "NOT NULL"),
            ("proof_limit", "TEXT", "NOT NULL"),
            ("projection_schema_version", "TEXT", "NOT NULL"),
        ),
        _table(
            "projection_faults",
            ("fault_id", "TEXT", "PRIMARY KEY"),
            ("fault_kind", "TEXT", "NOT NULL"),
            ("fault_subject_ref", "TEXT", "NOT NULL"),
            ("fault_severity", "TEXT", "NOT NULL"),
            ("reason", "TEXT", "NOT NULL"),
            ("projection_schema_version", "TEXT", "NOT NULL"),
        ),
        _table(
            "freshness_events",
            ("stale_record_ref", "TEXT", "PRIMARY KEY"),
            ("required_recompute_ref", "TEXT", "NOT NULL"),
            ("projection_schema_version", "TEXT", "NOT NULL"),
        ),
    )
    indexes = (
        IndexDefinition("idx_source_artifacts_source_hash", "source_artifacts", ("source_hash",)),
        IndexDefinition("idx_kernel_record_kind", "kernel_record_candidates", ("record_kind",)),
        IndexDefinition("idx_kernel_natural_key", "kernel_record_candidates", ("natural_key_value",)),
        IndexDefinition("idx_kernel_authority_state", "kernel_record_candidates", ("authority_state",)),
        IndexDefinition("idx_kernel_freshness_status", "kernel_record_candidates", ("freshness_state", "record_status")),
        IndexDefinition("idx_lineage_record_kind", "lineage_edges", ("record_id", "edge_kind")),
        IndexDefinition("idx_validation_classification", "validation_results", ("classification", "proof_status")),
        IndexDefinition("idx_projection_fault_kind", "projection_faults", ("fault_kind", "fault_subject_ref")),
    )
    return SQLiteProjectionSchema(schema_version=schema_version, tables=tables, indexes=indexes)


def _table(name: str, *columns: tuple[str, str, str]) -> TableDefinition:
    return TableDefinition(
        name=name,
        columns=tuple(ColumnDefinition(column[0], column[1], column[2]) for column in columns),
    )
