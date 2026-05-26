"""KernelRecord candidate extraction from parsed SOP evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any

from .sop_parser import ParsedSOPDocument, ParseEvent


EXTRACTION_RULE_VERSION = "ir2-kernel-record-extraction-v1"


@dataclass(frozen=True)
class KernelRecordCandidate:
    """A candidate KernelRecord envelope before authority validation."""

    record_id: str
    record_kind: str
    natural_key: str
    natural_key_state: str
    subject_ref: str
    authority_state: str
    source_ref_set: tuple[str, ...]
    lineage_edge_set: tuple[str, ...]
    freshness_state: str
    status: str
    blocked_or_fault_reason: str
    payload: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ExtractionFault:
    """Extraction fault preserved for manager review."""

    fault_id: str
    fault_kind: str
    source_path: str
    reason: str


@dataclass(frozen=True)
class ExtractionResult:
    """KernelRecord extraction result."""

    candidates: tuple[KernelRecordCandidate, ...] = field(default_factory=tuple)
    faults: tuple[ExtractionFault, ...] = field(default_factory=tuple)


def extract_kernel_record_candidates(
    parse_document: ParsedSOPDocument,
    extraction_rules: Any | None = None,
) -> ExtractionResult:
    """Extract KernelRecord candidates from structural parse events.

    The implementation emits candidate envelopes and blocked/fault states. It
    does not validate signatures or accept authority.
    """

    del extraction_rules
    field_map = _extract_field_map(parse_document.events)
    fixture_id = field_map.get("fixture_id", _stem_identifier(parse_document.source_path))
    record_kind = _record_kind_for(parse_document.source_path, field_map)
    natural_key = field_map.get("natural_key", f"source:{parse_document.source_path}")
    natural_key_state = "unresolved" if natural_key in {"", "unresolved"} else "resolved"
    authority_state = field_map.get("authority_state", _authority_state_for_path(parse_document.source_path))
    status, reason = _status_and_reason(field_map, parse_document)
    freshness_state = _freshness_state(field_map, parse_document)
    subject_ref = _subject_ref(parse_document, fixture_id)
    source_ref_set = (
        f"source_path:{parse_document.source_path}",
        f"source_hash:{parse_document.source_hash}",
        f"extraction_rule_version:{EXTRACTION_RULE_VERSION}",
    )
    lineage_edge_set = (
        f"derived_from:{parse_document.source_path}",
        f"source_of:{subject_ref}",
    )
    payload = dict(field_map)
    payload["parse_fault_count"] = str(len(parse_document.faults))

    candidate = KernelRecordCandidate(
        record_id=_record_id(record_kind, parse_document.source_path, parse_document.source_hash, fixture_id),
        record_kind=record_kind,
        natural_key=natural_key,
        natural_key_state=natural_key_state,
        subject_ref=subject_ref,
        authority_state=authority_state,
        source_ref_set=source_ref_set,
        lineage_edge_set=lineage_edge_set,
        freshness_state=freshness_state,
        status=status,
        blocked_or_fault_reason=reason,
        payload=payload,
    )

    faults = tuple(_candidate_faults(candidate, parse_document))
    return ExtractionResult(candidates=(candidate,), faults=faults)


def _extract_field_map(events: tuple[ParseEvent, ...]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for event in events:
        if event.marker_kind != "directive" or not event.bracket_label:
            continue
        fields[event.bracket_label] = _tail_value(event.tail_text)
    return fields


def _tail_value(tail_text: str) -> str:
    if tail_text.startswith("is "):
        return tail_text[3:].strip()
    return tail_text.strip()


def _record_kind_for(source_path: str, fields: dict[str, str]) -> str:
    field_kind = fields.get("record_kind")
    if field_kind:
        return field_kind
    if source_path.startswith("tests/fixtures/expected/"):
        return "expected_output_ledger"
    if source_path.startswith("tests/fixtures/sop/"):
        return "fixture_source"
    if source_path.startswith("docs/reviews/"):
        return "completion_review"
    if source_path.startswith("docs/canonical/"):
        return "canonical_specification"
    return "source_log"


def _authority_state_for_path(source_path: str) -> str:
    if source_path.startswith("tests/fixtures/expected/"):
        return "expected_output_authority_candidate"
    if source_path.startswith("tests/fixtures/sop/"):
        return "fixture_source_candidate"
    return "source_only"


def _status_and_reason(fields: dict[str, str], parse_document: ParsedSOPDocument) -> tuple[str, str]:
    expected_status = fields.get("expected_record_status", "")
    if parse_document.faults:
        return "blocked", "parser_fault"
    if expected_status.startswith("blocked"):
        return "blocked", expected_status.removeprefix("blocked_")
    if expected_status in {"parser_fault_preserved", "source_mutation_refused"}:
        return "blocked", expected_status
    if expected_status in {"source_only_not_authority", "projection_only_not_authority"}:
        return "draft", expected_status
    if expected_status == "accepted_authority_candidate":
        return "draft", "awaiting_validation"
    return "draft", expected_status or "awaiting_validation"


def _freshness_state(fields: dict[str, str], parse_document: ParsedSOPDocument) -> str:
    if parse_document.faults:
        return "unknown"
    expected_status = fields.get("expected_record_status", "")
    if "stale" in expected_status:
        return "stale"
    return "current"


def _subject_ref(parse_document: ParsedSOPDocument, fixture_id: str) -> str:
    for event in parse_document.events:
        if event.bracket_label:
            return f"{parse_document.source_path}:{event.line_number}:{event.bracket_label}"
    return f"{parse_document.source_path}:fixture:{fixture_id}"


def _record_id(record_kind: str, source_path: str, source_hash: str, fixture_id: str) -> str:
    raw = "|".join((record_kind, source_path, source_hash, fixture_id, EXTRACTION_RULE_VERSION))
    return sha256(raw.encode("utf-8")).hexdigest().upper()


def _candidate_faults(
    candidate: KernelRecordCandidate,
    parse_document: ParsedSOPDocument,
) -> list[ExtractionFault]:
    faults: list[ExtractionFault] = []
    if candidate.natural_key_state == "unresolved":
        faults.append(
            ExtractionFault(
                fault_id=f"{candidate.record_id}:unresolved_natural_key",
                fault_kind="unresolved_natural_key",
                source_path=parse_document.source_path,
                reason="Candidate natural key is unresolved.",
            )
        )
    for parse_fault in parse_document.faults:
        faults.append(
            ExtractionFault(
                fault_id=f"{candidate.record_id}:{parse_fault.fault_kind}:{parse_fault.line_number}",
                fault_kind=parse_fault.fault_kind,
                source_path=parse_document.source_path,
                reason=parse_fault.downstream_effect,
            )
        )
    if not candidate.source_ref_set:
        faults.append(
            ExtractionFault(
                fault_id=f"{candidate.record_id}:missing_source_ref",
                fault_kind="missing_source_ref",
                source_path=parse_document.source_path,
                reason="Candidate has no source references.",
            )
        )
    if not candidate.lineage_edge_set:
        faults.append(
            ExtractionFault(
                fault_id=f"{candidate.record_id}:missing_lineage_edge",
                fault_kind="missing_lineage_edge",
                source_path=parse_document.source_path,
                reason="Candidate has no lineage edges.",
            )
        )
    return faults


def _stem_identifier(source_path: str) -> str:
    return source_path.replace("\\", "/").rsplit("/", maxsplit=1)[-1].removesuffix(".sop")
