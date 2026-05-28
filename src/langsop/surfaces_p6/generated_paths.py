"""Generated path policy for P6 surface projection fixture work."""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
import json
from pathlib import Path
from typing import Mapping, Sequence

from .envelope import NON_AUTHORITY_WARNING


FIXTURE_SOURCE_ROOT = Path("tests/fixtures/sop/p6_surface_projection")
EXPECTED_LEDGER_ROOT = Path("tests/fixtures/expected/p6_surface_projection")
PLATFORM_MAILBOX_ROOT = Path("platform/coordination/mailboxes")
ACCEPTED_GENERATED_ROOTS: tuple[Path, ...] = (
    Path(".langsop/projections/p6_surface_projection"),
    Path(".langsop/reports/p6_surface_projection"),
    Path("tests/fixtures/generated/p6_surface_projection"),
    Path("tests/fixtures/generated/p6_surface_projection/projections"),
    Path("tests/fixtures/generated/p6_surface_projection/reports"),
    Path("tests/fixtures/generated/p6_surface_implementation/proof_results"),
    Path("tests/fixtures/generated/p6_surface_implementation/reports"),
)
FORBIDDEN_WRITE_ROOTS: tuple[Path, ...] = (
    Path("docs"),
    Path("src"),
    Path("platform"),
    Path(".git"),
    FIXTURE_SOURCE_ROOT,
    EXPECTED_LEDGER_ROOT,
    PLATFORM_MAILBOX_ROOT,
)


@dataclass(frozen=True)
class P6SurfacePathPolicyResult:
    """Result of validating a P6 surface fixture or generated path."""

    requested_path: str
    accepted: bool
    normalized_path: str | None = None
    matched_root: str | None = None
    refusal_reason: str | None = None
    non_authority_warning: str = NON_AUTHORITY_WARNING


def validate_tracked_p6_surface_fixture_source_path(
    path: str | Path,
    *,
    workspace_root: str | Path = ".",
) -> P6SurfacePathPolicyResult:
    """Accept only tracked P6 surface fixture source files."""

    return _validate_read_path(
        path,
        allowed_root=FIXTURE_SOURCE_ROOT,
        refusal_reason="p6_surface_fixture_source_path_outside_policy",
        workspace_root=workspace_root,
    )


def validate_p6_surface_expected_ledger_path(
    path: str | Path,
    *,
    workspace_root: str | Path = ".",
) -> P6SurfacePathPolicyResult:
    """Accept only tracked P6 surface expected ledger files."""

    return _validate_read_path(
        path,
        allowed_root=EXPECTED_LEDGER_ROOT,
        refusal_reason="p6_surface_expected_ledger_path_outside_policy",
        workspace_root=workspace_root,
    )


def validate_generated_p6_surface_output_path(
    path: str | Path,
    *,
    workspace_root: str | Path = ".",
    accepted_roots: Sequence[Path] = ACCEPTED_GENERATED_ROOTS,
) -> P6SurfacePathPolicyResult:
    """Accept generated P6 surface outputs only under accepted ignored roots."""

    workspace = Path(workspace_root).resolve()
    candidate = _resolve_under_workspace(path, workspace)
    forbidden = _matched_root(candidate, FORBIDDEN_WRITE_ROOTS, workspace)
    if forbidden is not None:
        return P6SurfacePathPolicyResult(
            requested_path=str(path),
            accepted=False,
            normalized_path=str(candidate),
            matched_root=str(forbidden),
            refusal_reason="source_expected_or_mailbox_mutation_refusal",
        )

    matched = _matched_root(candidate, accepted_roots, workspace)
    return P6SurfacePathPolicyResult(
        requested_path=str(path),
        accepted=matched is not None,
        normalized_path=str(candidate),
        matched_root=str(matched) if matched is not None else None,
        refusal_reason=None if matched is not None else "generated_p6_surface_path_escape",
    )


def write_generated_p6_surface_output(
    path: str | Path,
    content: Mapping[str, object] | object | str,
    *,
    workspace_root: str | Path = ".",
) -> P6SurfacePathPolicyResult:
    """Write generated P6 output only after path-policy acceptance."""

    policy = validate_generated_p6_surface_output_path(path, workspace_root=workspace_root)
    if not policy.accepted or policy.normalized_path is None:
        return policy

    target = Path(policy.normalized_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, str):
        text = content
    elif isinstance(content, Mapping):
        text = json.dumps(_jsonable(dict(content)), sort_keys=True, indent=2)
    elif is_dataclass(content):
        text = json.dumps(_jsonable(asdict(content)), sort_keys=True, indent=2)
    else:
        text = json.dumps(_jsonable(content), sort_keys=True, indent=2)
    target.write_text(text, encoding="utf-8")
    return policy


def display_path(path: str | Path, *, workspace_root: str | Path) -> str:
    """Return a workspace-relative display path when possible."""

    workspace = Path(workspace_root).resolve()
    resolved = _resolve_under_workspace(path, workspace)
    try:
        return str(resolved.relative_to(workspace)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _validate_read_path(
    path: str | Path,
    *,
    allowed_root: Path,
    refusal_reason: str,
    workspace_root: str | Path,
) -> P6SurfacePathPolicyResult:
    workspace = Path(workspace_root).resolve()
    candidate = _resolve_under_workspace(path, workspace)
    matched = _matched_root(candidate, (allowed_root,), workspace)
    exists = candidate.exists() and candidate.is_file()
    return P6SurfacePathPolicyResult(
        requested_path=str(path),
        accepted=matched is not None and exists,
        normalized_path=str(candidate),
        matched_root=str(matched) if matched is not None else None,
        refusal_reason=None if matched is not None and exists else refusal_reason,
    )


def _matched_root(path: Path, roots: Sequence[Path], workspace: Path) -> Path | None:
    for root in roots:
        resolved_root = _resolve_under_workspace(root, workspace)
        if _is_relative_to(path, resolved_root):
            return resolved_root
    return None


def _resolve_under_workspace(path: str | Path, workspace: Path) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = workspace / candidate
    return candidate.resolve(strict=False)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _jsonable(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_jsonable(item) for item in value]
    if hasattr(value, "value"):
        return value.value  # type: ignore[no-any-return]
    return value


__all__ = (
    "ACCEPTED_GENERATED_ROOTS",
    "EXPECTED_LEDGER_ROOT",
    "FIXTURE_SOURCE_ROOT",
    "FORBIDDEN_WRITE_ROOTS",
    "NON_AUTHORITY_WARNING",
    "P6SurfacePathPolicyResult",
    "display_path",
    "validate_generated_p6_surface_output_path",
    "validate_p6_surface_expected_ledger_path",
    "validate_tracked_p6_surface_fixture_source_path",
    "write_generated_p6_surface_output",
)
