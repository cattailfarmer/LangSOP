"""Contract-driven runner for bounded IR3 operator invocations.

The runner is intentionally pure. It validates a request, classifies the
outcome, and returns generated projection records plus a trace envelope without
writing files or controlling external processes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Mapping, Sequence

from .contracts import (
    ContractIssue,
    ContractIssueKind,
    ContractValidationResult,
    IssueSeverity,
    OperatorContract,
    OperatorRequest,
    OutcomeKind,
    request_from_mapping,
    validate_operator_request,
)
from .traces import NON_AUTHORITY_WARNING, OperatorTraceEvent, build_trace_event


OperatorFunction = Callable[[tuple[object, ...]], Mapping[str, object] | object]


@dataclass(frozen=True)
class OperatorResult:
    """Generated success record from an accepted in-process operator call."""

    result_id: str
    output_record_kind: str
    payload: Mapping[str, object] | object
    generated_output_ref_set: tuple[str, ...] = ()
    result_status: str = "generated_projection_only"
    non_authority_warning: str = NON_AUTHORITY_WARNING


@dataclass(frozen=True)
class RunnerRefusal:
    """Positive blocked output for incomplete or stale support."""

    refusal_id: str
    blocked_reason: str
    required_resolution: str
    input_ref_set: tuple[str, ...]
    authority_basis_ref_set: tuple[str, ...]
    operator_trace_ref: str
    outcome_kind: OutcomeKind = OutcomeKind.BLOCKED_OUTPUT
    non_authority_warning: str = NON_AUTHORITY_WARNING


@dataclass(frozen=True)
class FaultRecord:
    """Positive fault output for invalid or unsafe requests."""

    fault_id: str
    fault_kind: str
    reason: str
    evidence_ref_set: tuple[str, ...]
    operator_trace_ref: str
    outcome_kind: OutcomeKind = OutcomeKind.FAULT_OUTPUT
    non_authority_warning: str = NON_AUTHORITY_WARNING


@dataclass(frozen=True)
class SopFirstInterrupt:
    """Interrupt output when semantic judgment exceeds the runner contract."""

    interrupt_id: str
    interrupt_kind: str
    reason: str
    required_judgment: str
    operator_trace_ref: str
    outcome_kind: OutcomeKind = OutcomeKind.SOP_FIRST_INTERRUPT
    non_authority_warning: str = NON_AUTHORITY_WARNING


@dataclass(frozen=True)
class OperatorRunResult:
    """Complete pure runner result for one operator request."""

    request_ref: str
    accepted: bool
    outcome_kind: OutcomeKind
    operator_trace: OperatorTraceEvent
    issue_set: tuple[ContractIssue, ...] = ()
    operator_result: OperatorResult | None = None
    runner_refusal: RunnerRefusal | None = None
    fault_record: FaultRecord | None = None
    sop_first_interrupt: SopFirstInterrupt | None = None
    generated_output_ref_set: tuple[str, ...] = field(default_factory=tuple)


def run_contract_operator(
    request: OperatorRequest | Mapping[str, object],
    contract: OperatorContract,
    *,
    operator_function: OperatorFunction | None = None,
    input_records: Sequence[object] = (),
    run_id: str = "ir3-operator-run",
    event_id: str = "ir3-operator-event",
    parent_event_id: str | None = None,
    source_ref_set: Sequence[str] | None = None,
    operator_request_ref: str | None = None,
    accepted_scope: str = "accepted_activation_boundary",
) -> OperatorRunResult:
    """Run a contract-bound operator request without external side effects."""

    resolved_request = _resolve_request(request)
    if isinstance(resolved_request, ContractValidationResult):
        context = _request_context_from_mapping(request)
        outcome_kind = _outcome_from_validation(resolved_request)
        trace = _trace_from_parts(
            contract=contract,
            request_ref=context.request_ref,
            slice_id=context.slice_id,
            input_ref_set=context.input_ref_set,
            authority_basis_ref_set=context.authority_basis_ref_set,
            source_ref_set=tuple(source_ref_set or context.source_ref_set),
            outcome_kind=outcome_kind,
            run_id=run_id,
            event_id=event_id,
            parent_event_id=parent_event_id,
            issue_set=resolved_request.issues,
        )
        return _blocked_or_fault_result(
            request_ref=context.request_ref,
            outcome_kind=outcome_kind,
            trace=trace,
            issues=resolved_request.issues,
            input_ref_set=context.input_ref_set,
            authority_basis_ref_set=context.authority_basis_ref_set,
        )

    validation = validate_operator_request(
        resolved_request,
        contract,
        accepted_scope=accepted_scope,
    )
    request_ref = operator_request_ref or resolved_request.request_id
    requested_sources = tuple(
        source_ref_set
        if source_ref_set is not None
        else resolved_request.authority_basis_ref_set + resolved_request.input_ref_set
    )

    if not validation.accepted:
        outcome_kind = _outcome_from_validation(validation)
        trace = _trace_from_parts(
            contract=contract,
            request_ref=request_ref,
            slice_id=resolved_request.slice_id,
            input_ref_set=resolved_request.input_ref_set,
            authority_basis_ref_set=resolved_request.authority_basis_ref_set,
            source_ref_set=requested_sources,
            outcome_kind=outcome_kind,
            run_id=run_id,
            event_id=event_id,
            parent_event_id=parent_event_id,
            issue_set=validation.issues,
        )
        return _blocked_or_fault_result(
            request_ref=request_ref,
            outcome_kind=outcome_kind,
            trace=trace,
            issues=validation.issues,
            input_ref_set=resolved_request.input_ref_set,
            authority_basis_ref_set=resolved_request.authority_basis_ref_set,
        )

    try:
        payload = operator_function(tuple(input_records)) if operator_function else {}
    except Exception as exc:  # pragma: no cover - fixture tests will pin exact cases later.
        issue = ContractIssue(
            ContractIssueKind.INVALID_FIELD,
            IssueSeverity.FAULT,
            f"operator function raised {type(exc).__name__}: {exc}",
            "operator_function",
        )
        trace = _trace_from_parts(
            contract=contract,
            request_ref=request_ref,
            slice_id=resolved_request.slice_id,
            input_ref_set=resolved_request.input_ref_set,
            authority_basis_ref_set=resolved_request.authority_basis_ref_set,
            source_ref_set=requested_sources,
            outcome_kind=OutcomeKind.FAULT_OUTPUT,
            run_id=run_id,
            event_id=event_id,
            parent_event_id=parent_event_id,
            issue_set=(issue,),
        )
        return _blocked_or_fault_result(
            request_ref=request_ref,
            outcome_kind=OutcomeKind.FAULT_OUTPUT,
            trace=trace,
            issues=(issue,),
            input_ref_set=resolved_request.input_ref_set,
            authority_basis_ref_set=resolved_request.authority_basis_ref_set,
        )

    output_kind = _success_output_kind(resolved_request, contract)
    generated_output_ref_set = _generated_output_refs(payload)
    trace = _trace_from_parts(
        contract=contract,
        request_ref=request_ref,
        slice_id=resolved_request.slice_id,
        input_ref_set=resolved_request.input_ref_set,
        authority_basis_ref_set=resolved_request.authority_basis_ref_set,
        source_ref_set=requested_sources,
        outcome_kind=OutcomeKind.SUCCESS,
        run_id=run_id,
        event_id=event_id,
        parent_event_id=parent_event_id,
        generated_output_ref_set=generated_output_ref_set,
    )
    result = OperatorResult(
        result_id=f"operator_result:{trace.trace_id}",
        output_record_kind=output_kind,
        payload=payload,
        generated_output_ref_set=generated_output_ref_set,
    )
    return OperatorRunResult(
        request_ref=request_ref,
        accepted=True,
        outcome_kind=OutcomeKind.SUCCESS,
        operator_trace=trace,
        operator_result=result,
        generated_output_ref_set=generated_output_ref_set,
    )


@dataclass(frozen=True)
class _RequestContext:
    request_ref: str
    slice_id: str
    input_ref_set: tuple[str, ...]
    authority_basis_ref_set: tuple[str, ...]
    source_ref_set: tuple[str, ...]


def _resolve_request(request: OperatorRequest | Mapping[str, object]) -> OperatorRequest | ContractValidationResult:
    if isinstance(request, OperatorRequest):
        return request
    return request_from_mapping(request)


def _request_context_from_mapping(request: OperatorRequest | Mapping[str, object]) -> _RequestContext:
    if isinstance(request, OperatorRequest):
        input_ref_set = request.input_ref_set
        authority_basis_ref_set = request.authority_basis_ref_set
        return _RequestContext(
            request_ref=request.request_id,
            slice_id=request.slice_id,
            input_ref_set=input_ref_set,
            authority_basis_ref_set=authority_basis_ref_set,
            source_ref_set=authority_basis_ref_set + input_ref_set,
        )

    request_ref = str(request.get("request_id", "invalid_operator_request"))
    slice_id = str(request.get("slice_id", "unknown_slice"))
    input_ref_set = _string_tuple(request.get("input_ref_set", ()))
    authority_basis_ref_set = _string_tuple(request.get("authority_basis_ref_set", ()))
    return _RequestContext(
        request_ref=request_ref,
        slice_id=slice_id,
        input_ref_set=input_ref_set,
        authority_basis_ref_set=authority_basis_ref_set,
        source_ref_set=authority_basis_ref_set + input_ref_set,
    )


def _trace_from_parts(
    *,
    contract: OperatorContract,
    request_ref: str,
    slice_id: str,
    input_ref_set: tuple[str, ...],
    authority_basis_ref_set: tuple[str, ...],
    source_ref_set: tuple[str, ...],
    outcome_kind: OutcomeKind,
    run_id: str,
    event_id: str,
    parent_event_id: str | None,
    generated_output_ref_set: tuple[str, ...] = (),
    issue_set: tuple[ContractIssue, ...] = (),
) -> OperatorTraceEvent:
    return build_trace_event(
        run_id=run_id,
        event_id=event_id,
        parent_event_id=parent_event_id,
        slice_id=slice_id,
        operator_contract_id=contract.operator_id,
        operator_contract_version=contract.operator_version,
        operator_request_ref=request_ref,
        input_ref_set=input_ref_set,
        authority_basis_ref_set=authority_basis_ref_set,
        source_ref_set=source_ref_set,
        outcome_kind=outcome_kind,
        generated_output_ref_set=generated_output_ref_set,
        issue_set=issue_set,
    )


def _blocked_or_fault_result(
    *,
    request_ref: str,
    outcome_kind: OutcomeKind,
    trace: OperatorTraceEvent,
    issues: tuple[ContractIssue, ...],
    input_ref_set: tuple[str, ...],
    authority_basis_ref_set: tuple[str, ...],
) -> OperatorRunResult:
    primary_issue = issues[0] if issues else ContractIssue(
        ContractIssueKind.INVALID_FIELD,
        IssueSeverity.FAULT,
        "operator request was not accepted",
    )
    if outcome_kind == OutcomeKind.SOP_FIRST_INTERRUPT:
        interrupt = SopFirstInterrupt(
            interrupt_id=f"sop_first_interrupt:{trace.trace_id}",
            interrupt_kind=_issue_public_kind(primary_issue),
            reason=primary_issue.reason,
            required_judgment="return to SOP authority for semantic or identity judgment",
            operator_trace_ref=trace.trace_id,
        )
        return OperatorRunResult(
            request_ref=request_ref,
            accepted=False,
            outcome_kind=outcome_kind,
            operator_trace=trace,
            issue_set=issues,
            sop_first_interrupt=interrupt,
        )

    if outcome_kind == OutcomeKind.BLOCKED_OUTPUT:
        refusal = RunnerRefusal(
            refusal_id=f"runner_refusal:{trace.trace_id}",
            blocked_reason=_issue_public_kind(primary_issue),
            required_resolution=_required_resolution(primary_issue),
            input_ref_set=input_ref_set,
            authority_basis_ref_set=authority_basis_ref_set,
            operator_trace_ref=trace.trace_id,
        )
        return OperatorRunResult(
            request_ref=request_ref,
            accepted=False,
            outcome_kind=outcome_kind,
            operator_trace=trace,
            issue_set=issues,
            runner_refusal=refusal,
        )

    fault = FaultRecord(
        fault_id=f"fault_record:{trace.trace_id}",
        fault_kind=_issue_public_kind(primary_issue),
        reason=primary_issue.reason,
        evidence_ref_set=authority_basis_ref_set + input_ref_set,
        operator_trace_ref=trace.trace_id,
    )
    return OperatorRunResult(
        request_ref=request_ref,
        accepted=False,
        outcome_kind=OutcomeKind.FAULT_OUTPUT,
        operator_trace=trace,
        issue_set=issues,
        fault_record=fault,
    )


def _outcome_from_validation(validation: ContractValidationResult) -> OutcomeKind:
    if validation.has_fault:
        return OutcomeKind.FAULT_OUTPUT
    if validation.has_interrupt:
        return OutcomeKind.SOP_FIRST_INTERRUPT
    if validation.has_blocker:
        return OutcomeKind.BLOCKED_OUTPUT
    return OutcomeKind.SUCCESS


def _success_output_kind(request: OperatorRequest, contract: OperatorContract) -> str:
    if "operator_result" in request.expected_output_kind_set:
        return "operator_result"
    for output_kind in request.expected_output_kind_set:
        if output_kind in contract.output_record_kind_set and output_kind != "operator_trace":
            return output_kind
    return "operator_result"


def _generated_output_refs(payload: Mapping[str, object] | object) -> tuple[str, ...]:
    if not isinstance(payload, Mapping):
        return ()
    value = payload.get("generated_output_ref_set", ())
    return _string_tuple(value)


def _string_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Sequence):
        return tuple(str(item) for item in value)
    return (str(value),)


def _issue_public_kind(issue: ContractIssue) -> str:
    if issue.issue_kind == ContractIssueKind.STALE_AUTHORITY:
        return "stale_refusal"
    if issue.issue_kind == ContractIssueKind.MISSING_FIELD and issue.field_name == "requested_operator_version":
        return "missing_contract_version"
    if issue.issue_kind == ContractIssueKind.UNSUPPORTED_SCOPE:
        return "unsupported_scope"
    if issue.issue_kind == ContractIssueKind.GENERATED_AUTHORITY:
        return "generated_trace_authority_confusion"
    if issue.issue_kind == ContractIssueKind.UNDECLARED_OUTPUT:
        return "operator_contract_violation"
    if issue.issue_kind == ContractIssueKind.UNSAFE_OPERATION:
        return "unsupported_operations_control"
    if issue.issue_kind == ContractIssueKind.AMBIGUOUS_IDENTITY:
        return "ambiguous_identity"
    if issue.issue_kind in {ContractIssueKind.INVALID_FIELD, ContractIssueKind.MISSING_FIELD}:
        return "invalid_input_shape"
    return issue.issue_kind.value


def _required_resolution(issue: ContractIssue) -> str:
    if issue.issue_kind == ContractIssueKind.STALE_AUTHORITY:
        return "refresh authority basis and rerun from accepted source"
    if issue.issue_kind == ContractIssueKind.MISSING_FIELD:
        return f"supply required field {issue.field_name or 'unknown'} from accepted authority"
    if issue.issue_kind == ContractIssueKind.UNSUPPORTED_SCOPE:
        return "narrow request to the accepted activation boundary or open a new slice"
    return "repair request according to accepted SOP authority before retry"
