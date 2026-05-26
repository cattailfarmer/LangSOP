"""Structural SOP parser.

The parser preserves structural evidence and recoverable faults. It does not
validate authority, resolve identities, or write generated artifacts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any


MARKER_KIND_BY_TEXT: dict[str, str] = {
    "&": "local_term",
    "+": "directive",
    "=": "constraint",
    "-": "constraint",
    "^": "function_declaration",
    "?": "condition",
    "@": "anchor",
    "!": "claim",
    "~": "assumption",
    "|": "enum_declaration",
    "/": "pants_decomposition",
    "*": "pants_composition",
    "#": "comment",
}


@dataclass(frozen=True)
class ParseFault:
    """Recoverable structural parse fault."""

    fault_id: str
    source_path: str
    source_hash: str
    line_number: int
    raw_text: str
    fault_kind: str
    fault_severity: str
    recovery_action: str
    downstream_effect: str


@dataclass(frozen=True)
class ParseEvent:
    """A structural SOP line event."""

    source_path: str
    source_hash: str
    line_number: int
    raw_text: str
    indentation_column: int
    marker_text: str
    marker_kind: str
    bracket_label: str
    tail_text: str
    parent_line_ref: int | None
    active_range_ref: int | None
    parse_status: str
    parse_fault_ref_set: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ParsedSOPDocument:
    """A parsed SOP document with events and recoverable faults."""

    source_path: str
    source_hash: str
    events: tuple[ParseEvent, ...] = field(default_factory=tuple)
    faults: tuple[ParseFault, ...] = field(default_factory=tuple)


def parse_sop_document(source_artifact: Any, parser_profile: Any | None = None) -> ParsedSOPDocument:
    """Parse a SOP document from a path or discovery artifact.

    ``parser_profile`` is accepted for API compatibility with the IR2 public
    boundary. The active implementation uses the accepted structural profile.
    """

    del parser_profile
    source_path = getattr(source_artifact, "source_path", source_artifact)
    root_path = getattr(source_artifact, "root_path", None)
    path = Path(root_path) / Path(source_path) if root_path is not None else Path(source_path)
    text = path.read_text(encoding="utf-8")
    source_hash = getattr(source_artifact, "source_hash", sha256(text.encode("utf-8")).hexdigest().upper())
    return parse_sop_text(text, source_path=str(source_path).replace("\\", "/"), source_hash=source_hash)


def parse_sop_text(
    text: str,
    *,
    source_path: str = "<memory>",
    source_hash: str | None = None,
) -> ParsedSOPDocument:
    """Parse SOP text into structural events and recoverable faults."""

    stable_hash = source_hash or sha256(text.encode("utf-8")).hexdigest().upper()
    events: list[ParseEvent] = []
    faults: list[ParseFault] = []
    parent_stack: list[tuple[int, int]] = []

    for line_number, raw_text in enumerate(text.splitlines(), start=1):
        indentation_column = _indentation_column(raw_text)
        stripped = raw_text[indentation_column:]
        marker_text, marker_kind, bracket_label, tail_text, line_faults = _parse_line(
            stripped=stripped,
            source_path=source_path,
            source_hash=stable_hash,
            line_number=line_number,
            raw_text=raw_text,
        )
        faults.extend(line_faults)
        parse_fault_refs = tuple(fault.fault_id for fault in line_faults)
        parent_line_ref = _parent_for(indentation_column, parent_stack)
        parse_status = "fault" if parse_fault_refs else "ok"

        event = ParseEvent(
            source_path=source_path,
            source_hash=stable_hash,
            line_number=line_number,
            raw_text=raw_text,
            indentation_column=indentation_column,
            marker_text=marker_text,
            marker_kind=marker_kind,
            bracket_label=bracket_label,
            tail_text=tail_text,
            parent_line_ref=parent_line_ref,
            active_range_ref=None,
            parse_status=parse_status,
            parse_fault_ref_set=parse_fault_refs,
        )
        events.append(event)

        if marker_kind not in {"blank", "comment"}:
            _push_parent(line_number, indentation_column, parent_stack)

    return ParsedSOPDocument(
        source_path=source_path,
        source_hash=stable_hash,
        events=tuple(events),
        faults=tuple(faults),
    )


def _parse_line(
    *,
    stripped: str,
    source_path: str,
    source_hash: str,
    line_number: int,
    raw_text: str,
) -> tuple[str, str, str, str, tuple[ParseFault, ...]]:
    if stripped == "":
        return "", "blank", "", "", ()

    if stripped.startswith("Subject:"):
        return "Subject:", "subject_declaration", "", stripped[len("Subject:") :].strip(), ()

    if stripped.startswith("Date:"):
        return "Date:", "directive", "", stripped[len("Date:") :].strip(), ()

    key, separator, value = stripped.partition(":")
    if separator and all(part.isidentifier() for part in key.split()):
        return f"{key}:", "directive", "", value.strip(), ()

    marker_text = stripped[0]
    marker_kind = MARKER_KIND_BY_TEXT.get(marker_text)
    if marker_kind is None:
        fault = ParseFault(
            fault_id=f"{source_path}:{line_number}:unknown_marker",
            source_path=source_path,
            source_hash=source_hash,
            line_number=line_number,
            raw_text=raw_text,
            fault_kind="unknown_marker",
            fault_severity="recoverable",
            recovery_action="preserve_line_as_unknown_event",
            downstream_effect="block_authority_classification_for_affected_line",
        )
        return "", "unknown", "", stripped, (fault,)

    tail_source = stripped[1:].lstrip()
    bracket_label, tail_text, label_fault = _split_bracket_label(
        tail_source=tail_source,
        source_path=source_path,
        source_hash=source_hash,
        line_number=line_number,
        raw_text=raw_text,
    )
    faults = (label_fault,) if label_fault is not None else ()
    return marker_text, marker_kind, bracket_label, tail_text, faults


def _split_bracket_label(
    *,
    tail_source: str,
    source_path: str,
    source_hash: str,
    line_number: int,
    raw_text: str,
) -> tuple[str, str, ParseFault | None]:
    if not tail_source.startswith("["):
        return "", tail_source, None

    closing_index = tail_source.find("]")
    if closing_index == -1:
        fault = ParseFault(
            fault_id=f"{source_path}:{line_number}:bracket_label_parse_failure",
            source_path=source_path,
            source_hash=source_hash,
            line_number=line_number,
            raw_text=raw_text,
            fault_kind="bracket_label_parse_failure",
            fault_severity="recoverable",
            recovery_action="preserve_tail_text_without_label",
            downstream_effect="block_identity_resolution_for_affected_line",
        )
        return "", tail_source, fault

    return tail_source[1:closing_index], tail_source[closing_index + 1 :].strip(), None


def _indentation_column(raw_text: str) -> int:
    column = 0
    for char in raw_text:
        if char == " ":
            column += 1
        elif char == "\t":
            column += 4
        else:
            break
    return column


def _parent_for(indentation_column: int, parent_stack: list[tuple[int, int]]) -> int | None:
    while parent_stack and parent_stack[-1][1] >= indentation_column:
        parent_stack.pop()
    if not parent_stack:
        return None
    return parent_stack[-1][0]


def _push_parent(line_number: int, indentation_column: int, parent_stack: list[tuple[int, int]]) -> None:
    parent_stack.append((line_number, indentation_column))
