"""Generated path policy for IR8 manager fixture projections."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Mapping, Sequence


NON_AUTHORITY_WARNING = "manager output is generated-projection-only and does not replace signed SOP authority"

FIXTURE_SOURCE_ROOT = Path("tests/fixtures/sop/ir8_integrated_manager")
EXPECTED_LEDGER_ROOT = Path("tests/fixtures/expected/ir8_integrated_manager")
PLATFORM_MAILBOX_ROOT = Path("platform/coordination/mailboxes")
ACCEPTED_GENERATED_ROOTS: tuple[Path, ...] = (
    Path(".langsop/projections/ir8_integrated_manager"),
    Path(".langsop/reports/ir8_integrated_manager"),
    Path("tests/fixtures/generated/ir8_integrated_manager"),
    Path("tests/fixtures/generated/ir8_integrated_manager/projections"),
    Path("tests/fixtures/generated/ir8_integrated_manager/reports"),
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
class ManagerPathPolicyResult:
    """Result of validating an IR8 manager path."""

    requested_path: str
    accepted: bool
    normalized_path: str | None = None
    matched_root: str | None = None
    refusal_reason: str | None = None
    non_authority_warning: str = NON_AUTHORITY_WARNING


def validate_tracked_manager_fixture_source_path(
    path: str | Path,
    *,
    workspace_root: str | Path = ".",
) -> ManagerPathPolicyResult:
    """Accept only tracked IR8 manager fixture source files."""

    return _validate_read_path(
        path,
        allowed_root=FIXTURE_SOURCE_ROOT,
        refusal_reason="manager_fixture_source_path_outside_policy",
        workspace_root=workspace_root,
    )


def validate_manager_expected_ledger_path(
    path: str | Path,
    *,
    workspace_root: str | Path = ".",
) -> ManagerPathPolicyResult:
    """Accept only tracked IR8 manager expected ledger files."""

    return _validate_read_path(
        path,
        allowed_root=EXPECTED_LEDGER_ROOT,
        refusal_reason="manager_expected_ledger_path_outside_policy",
        workspace_root=workspace_root,
    )


def validate_generated_manager_output_path(
    path: str | Path,
    *,
    workspace_root: str | Path = ".",
    accepted_roots: Sequence[Path] = ACCEPTED_GENERATED_ROOTS,
) -> ManagerPathPolicyResult:
    """Accept generated manager output paths only under accepted roots."""

    workspace = Path(workspace_root).resolve()
    candidate = _resolve_under_workspace(path, workspace)
    forbidden = _matched_root(candidate, FORBIDDEN_WRITE_ROOTS, workspace)
    if forbidden is not None:
        return ManagerPathPolicyResult(
            requested_path=str(path),
            accepted=False,
            normalized_path=str(candidate),
            matched_root=str(forbidden),
            refusal_reason="source_expected_or_mailbox_mutation_refusal",
        )

    matched = _matched_root(candidate, accepted_roots, workspace)
    return ManagerPathPolicyResult(
        requested_path=str(path),
        accepted=matched is not None,
        normalized_path=str(candidate),
        matched_root=str(matched) if matched is not None else None,
        refusal_reason=None if matched is not None else "generated_manager_path_escape",
    )


def write_generated_manager_output(
    path: str | Path,
    content: Mapping[str, object] | object | str,
    *,
    workspace_root: str | Path = ".",
) -> ManagerPathPolicyResult:
    """Write generated manager output only after path-policy acceptance."""

    policy = validate_generated_manager_output_path(path, workspace_root=workspace_root)
    if not policy.accepted or policy.normalized_path is None:
        return policy

    target = Path(policy.normalized_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, str):
        text = content
    elif isinstance(content, Mapping):
        text = json.dumps(_jsonable(dict(content)), sort_keys=True, indent=2)
    else:
        text = json.dumps(_jsonable(asdict(content)), sort_keys=True, indent=2)
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
) -> ManagerPathPolicyResult:
    workspace = Path(workspace_root).resolve()
    candidate = _resolve_under_workspace(path, workspace)
    matched = _matched_root(candidate, (allowed_root,), workspace)
    exists = candidate.exists() and candidate.is_file()
    return ManagerPathPolicyResult(
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
