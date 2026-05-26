"""Trace models for the bounded IR3 operator harness.

Trace records are generated projection evidence only. This module performs no
filesystem writes and does not create runtime state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from typing import Mapping

from .contracts import ContractIssue, OutcomeKind


TRACE_SCHEMA_VERSION = "ir3-operator-trace-event-v1"
NON_AUTHORITY_WARNING = (
    "generated operator traces are projection-only evidence and do not replace signed SOP authority"
)


@dataclass(frozen=True)
class OperatorTraceEvent:
    """Non-authoritative trace event for a future operator invocation."""

    trace_id: str
    trace_uuid: str
    run_id: str
    event_id: str
    slice_id: str
    operator_contract_id: str
    operator_contract_version: str
    operator_request_ref: str
    input_ref_set: tuple[str, ...]
    authority_basis_ref_set: tuple[str, ...]
    source_ref_set: tuple[str, ...]
    outcome_kind: OutcomeKind
    generated_output_ref_set: tuple[str, ...] = ()
    parent_event_id: str | None = None
    refusal_reason: str | None = None
    fault_code: str | None = None
    trace_schema_version: str = TRACE_SCHEMA_VERSION
    trace_status: str = "generated_projection_only"
    non_authority_warning: str = NON_AUTHORITY_WARNING


@dataclass(frozen=True)
class GeneratedOutputManifest:
    """Manifest for generated outputs referenced by trace events."""

    manifest_id: str
    generated_output_root: str
    generated_output_ref_set: tuple[str, ...]
    non_authority_warning: str = NON_AUTHORITY_WARNING
    manifest_status: str = "generated_projection_only"


@dataclass(frozen=True)
class TraceValidationResult:
    """Pure validation result for trace record shape."""

    accepted: bool
    missing_field_set: tuple[str, ...] = ()


REQUIRED_TRACE_FIELDS: tuple[str, ...] = (
    "trace_id",
    "trace_uuid",
    "run_id",
    "event_id",
    "slice_id",
    "operator_contract_id",
    "operator_contract_version",
    "operator_request_ref",
    "input_ref_set",
    "authority_basis_ref_set",
    "source_ref_set",
    "outcome_kind",
    "generated_output_ref_set",
    "non_authority_warning",
)


def deterministic_trace_id(
    *,
    operator_contract_id: str,
    operator_contract_version: str,
    operator_request_ref: str,
    source_ref_set: tuple[str, ...],
    trace_schema_version: str = TRACE_SCHEMA_VERSION,
) -> str:
    """Return a stable trace id for fixed request, contract, and sources."""

    payload = {
        "operator_contract_id": operator_contract_id,
        "operator_contract_version": operator_contract_version,
        "operator_request_ref": operator_request_ref,
        "source_ref_set": sorted(source_ref_set),
        "trace_schema_version": trace_schema_version,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_trace_event(
    *,
    run_id: str,
    event_id: str,
    slice_id: str,
    operator_contract_id: str,
    operator_contract_version: str,
    operator_request_ref: str,
    input_ref_set: tuple[str, ...],
    authority_basis_ref_set: tuple[str, ...],
    source_ref_set: tuple[str, ...],
    outcome_kind: OutcomeKind,
    generated_output_ref_set: tuple[str, ...] = (),
    parent_event_id: str | None = None,
    issue_set: tuple[ContractIssue, ...] = (),
) -> OperatorTraceEvent:
    """Build a trace event from explicit inputs and validation issues."""

    trace_id = deterministic_trace_id(
        operator_contract_id=operator_contract_id,
        operator_contract_version=operator_contract_version,
        operator_request_ref=operator_request_ref,
        source_ref_set=source_ref_set,
    )
    fault_issue = next((issue for issue in issue_set if issue.severity.value == "fault"), None)
    refusal_issue = next((issue for issue in issue_set if issue.severity.value in {"blocked", "interrupt"}), None)
    return OperatorTraceEvent(
        trace_id=trace_id,
        trace_uuid=trace_id[:32],
        run_id=run_id,
        event_id=event_id,
        parent_event_id=parent_event_id,
        slice_id=slice_id,
        operator_contract_id=operator_contract_id,
        operator_contract_version=operator_contract_version,
        operator_request_ref=operator_request_ref,
        input_ref_set=input_ref_set,
        authority_basis_ref_set=authority_basis_ref_set,
        source_ref_set=source_ref_set,
        outcome_kind=outcome_kind,
        generated_output_ref_set=generated_output_ref_set,
        refusal_reason=refusal_issue.reason if refusal_issue else None,
        fault_code=fault_issue.issue_kind.value if fault_issue else None,
    )


def validate_trace_mapping(trace: Mapping[str, object]) -> TraceValidationResult:
    """Validate trace shape from a mapping without trusting it as authority."""

    missing = tuple(field for field in REQUIRED_TRACE_FIELDS if field not in trace)
    warning = trace.get("non_authority_warning")
    if warning != NON_AUTHORITY_WARNING and "non_authority_warning" not in missing:
        missing = missing + ("non_authority_warning",)
    return TraceValidationResult(not missing, missing)


def build_generated_output_manifest(
    *,
    manifest_id: str,
    generated_output_root: str,
    generated_output_ref_set: tuple[str, ...],
) -> GeneratedOutputManifest:
    """Build a non-authoritative generated output manifest."""

    return GeneratedOutputManifest(
        manifest_id=manifest_id,
        generated_output_root=generated_output_root,
        generated_output_ref_set=generated_output_ref_set,
    )
