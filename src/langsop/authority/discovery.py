"""SOP authority artifact discovery.

This module only discovers candidate source artifacts. It does not classify
authority, validate signatures, or write generated projections.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from hashlib import sha256
from pathlib import Path
from typing import Iterable


DEFAULT_INCLUDE_GLOBS: tuple[str, ...] = (
    "docs/**/*.sop",
    "tests/fixtures/sop/**/*.sop",
    "tests/fixtures/expected/**/*.sop",
)

DEFAULT_EXCLUDE_GLOBS: tuple[str, ...] = (
    ".git/**",
    ".langsop/**",
    ".venv/**",
    "__pycache__/**",
    ".pytest_cache/**",
    ".mypy_cache/**",
    ".ruff_cache/**",
    "dist/**",
    "build/**",
    "*.egg-info/**",
    "tests/fixtures/generated/**",
    "*.sqlite3",
    "*.db",
)


@dataclass(frozen=True)
class DiscoveryConfig:
    """Configuration for candidate SOP artifact discovery."""

    include_globs: tuple[str, ...] = DEFAULT_INCLUDE_GLOBS
    exclude_globs: tuple[str, ...] = DEFAULT_EXCLUDE_GLOBS
    follow_symlinks: bool = False


@dataclass(frozen=True)
class DiscoveredArtifact:
    """A discovered SOP file that may be examined by later validation."""

    root_path: str
    source_path: str
    source_hash: str
    path_role: str
    discovery_rule_version: str = "ir2-sop-artifact-discovery-v1"


@dataclass(frozen=True)
class DiscoveryDiagnostic:
    """A non-fatal discovery diagnostic."""

    source_path: str
    diagnostic_kind: str
    message: str


@dataclass(frozen=True)
class DiscoveryResult:
    """Discovery output with candidates and diagnostics."""

    artifacts: tuple[DiscoveredArtifact, ...] = field(default_factory=tuple)
    diagnostics: tuple[DiscoveryDiagnostic, ...] = field(default_factory=tuple)


def discover_sop_artifacts(
    root_path: str | Path,
    discovery_config: DiscoveryConfig | None = None,
) -> DiscoveryResult:
    """Discover SOP authority candidates under ``root_path``.

    The function is intentionally read-only. It returns candidates, not accepted
    authority records.
    """

    config = discovery_config or DiscoveryConfig()
    root = Path(root_path).resolve()
    diagnostics: list[DiscoveryDiagnostic] = []

    if not root.exists():
        return DiscoveryResult(
            diagnostics=(
                DiscoveryDiagnostic(
                    source_path=_to_posix(root),
                    diagnostic_kind="root_missing",
                    message="Discovery root does not exist.",
                ),
            )
        )

    artifacts: list[DiscoveredArtifact] = []
    for path in _iter_files(root, follow_symlinks=config.follow_symlinks):
        relative_path = _to_posix(path.relative_to(root))
        if not _matches_any(relative_path, config.include_globs):
            continue

        if _matches_any(relative_path, config.exclude_globs):
            diagnostics.append(
                DiscoveryDiagnostic(
                    source_path=relative_path,
                    diagnostic_kind="excluded_candidate",
                    message="Path matched an exclusion rule.",
                )
            )
            continue

        try:
            source_hash = sha256(path.read_bytes()).hexdigest().upper()
        except OSError as exc:
            diagnostics.append(
                DiscoveryDiagnostic(
                    source_path=relative_path,
                    diagnostic_kind="read_failure",
                    message=str(exc),
                )
            )
            continue

        artifacts.append(
            DiscoveredArtifact(
                root_path=_to_posix(root),
                source_path=relative_path,
                source_hash=source_hash,
                path_role=classify_sop_path_role(relative_path),
            )
        )

    artifacts.sort(key=lambda artifact: artifact.source_path)
    return DiscoveryResult(artifacts=tuple(artifacts), diagnostics=tuple(diagnostics))


def classify_sop_path_role(source_path: str) -> str:
    """Classify a discovered SOP path by repository role."""

    normalized = source_path.replace("\\", "/")
    if normalized.startswith("tests/fixtures/sop/"):
        return "fixture_source"
    if normalized.startswith("tests/fixtures/expected/"):
        return "fixture_expected_ledger"
    if normalized.startswith("docs/source/"):
        return "preserved_source_or_manifest"
    if normalized.startswith("docs/canonical/"):
        return "signed_canonical_candidate"
    if normalized.startswith("docs/slices/"):
        return "slice_surface_candidate"
    if normalized.startswith("docs/planning/"):
        return "planning_pack_or_readiness_candidate"
    if normalized.startswith("docs/schema/"):
        return "schema_candidate"
    if normalized.startswith("docs/operators/"):
        return "operator_contract_candidate"
    if normalized.startswith("docs/decisions/"):
        return "decision_candidate"
    if normalized.startswith("docs/reviews/"):
        return "completion_or_proof_review_candidate"
    if normalized.startswith("docs/fixtures/"):
        return "fixture_plan_or_index_candidate"
    if normalized.startswith("docs/runtime/"):
        return "runtime_contract_candidate"
    if normalized.startswith("docs/surfaces/"):
        return "surface_contract_candidate"
    if normalized.startswith("docs/operations/"):
        return "operations_safety_contract_candidate"
    if normalized.startswith("docs/coordination/"):
        return "coordination_contract_candidate"
    if normalized.startswith("docs/state/"):
        return "derived_current_state_candidate"
    if normalized.startswith("docs/"):
        return "sop_document_candidate"
    return "unknown_sop_candidate"


def _iter_files(root: Path, *, follow_symlinks: bool) -> Iterable[Path]:
    for path in root.rglob("*"):
        if path.is_symlink() and not follow_symlinks:
            continue
        if path.is_file():
            yield path


def _matches_any(source_path: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatchcase(source_path, pattern) for pattern in patterns)


def _to_posix(path: Path) -> str:
    return path.as_posix()
