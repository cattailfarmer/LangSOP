"""SQLite projection rebuild orchestration."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from langsop.authority.validation import ValidationReport

from .sqlite_projection import ProjectionWriteReport, write_validation_report


ALLOWED_GENERATED_ROOTS: tuple[str, ...] = (
    ".langsop/",
    "tests/fixtures/generated/",
)


@dataclass(frozen=True)
class ProjectionRebuildReport:
    """Report for a SQLite projection rebuild."""

    output_path: str
    write_report: ProjectionWriteReport
    rebuild_status: str
    authority_notice: str = "generated_sqlite_non_authority"


def rebuild_sqlite_projection(
    validated_projection_input: ValidationReport,
    output_path: str | Path,
) -> ProjectionRebuildReport:
    """Rebuild a generated SQLite projection at an allowed output path."""

    output = Path(output_path)
    if not is_allowed_generated_output_path(output):
        raise ValueError(f"Refusing projection write outside generated roots: {output}")

    output.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(output) as connection:
        write_report = write_validation_report(connection, validated_projection_input)
    return ProjectionRebuildReport(
        output_path=output.as_posix(),
        write_report=write_report,
        rebuild_status="written",
    )


def rebuild_sqlite_projection_in_memory(
    validated_projection_input: ValidationReport,
) -> tuple[sqlite3.Connection, ProjectionWriteReport]:
    """Build a projection in memory for tests and review smoke checks."""

    connection = sqlite3.connect(":memory:")
    write_report = write_validation_report(connection, validated_projection_input)
    return connection, write_report


def is_allowed_generated_output_path(output_path: str | Path) -> bool:
    """Return whether ``output_path`` is inside accepted generated roots."""

    normalized = Path(output_path).as_posix()
    return any(normalized.startswith(root) for root in ALLOWED_GENERATED_ROOTS)
