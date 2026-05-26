"""Bounded operator harness APIs for SOP-to-runtime duties."""

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
from .runner import (
    FaultRecord,
    OperatorResult,
    OperatorRunResult,
    RunnerRefusal,
    SopFirstInterrupt,
    run_contract_operator,
)
from .traces import (
    GeneratedOutputManifest,
    OperatorTraceEvent,
    TraceValidationResult,
    build_generated_output_manifest,
    build_trace_event,
    deterministic_trace_id,
    validate_trace_mapping,
)

__all__ = (
    "ContractIssue",
    "ContractIssueKind",
    "ContractValidationResult",
    "FaultRecord",
    "GeneratedOutputManifest",
    "IssueSeverity",
    "OperatorContract",
    "OperatorRequest",
    "OperatorResult",
    "OperatorRunResult",
    "OperatorTraceEvent",
    "OutcomeKind",
    "RunnerRefusal",
    "SopFirstInterrupt",
    "TraceValidationResult",
    "build_generated_output_manifest",
    "build_trace_event",
    "deterministic_trace_id",
    "request_from_mapping",
    "run_contract_operator",
    "validate_operator_request",
    "validate_trace_mapping",
)
