"""Contract and request models for the bounded IR3 operator harness.

This module is intentionally side-effect free. It validates record shapes and
returns explicit refusal or fault classifications for later runner code to use.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Sequence


class OutcomeKind(str, Enum):
    """Allowed outcome kinds from the accepted operator contract template."""

    SUCCESS = "success"
    BLOCKED_OUTPUT = "blocked_output"
    FAULT_OUTPUT = "fault_output"
    SOP_FIRST_INTERRUPT = "sop_first_interrupt"


class ContractIssueKind(str, Enum):
    """Validation issue classes produced before any operator execution."""

    MISSING_FIELD = "missing_field"
    INVALID_FIELD = "invalid_field"
    STALE_AUTHORITY = "stale_authority"
    UNDECLARED_OUTPUT = "undeclared_output"
    UNSAFE_OPERATION = "unsafe_operation"
    GENERATED_AUTHORITY = "generated_authority"
    UNSUPPORTED_SCOPE = "unsupported_scope"
    AMBIGUOUS_IDENTITY = "ambiguous_identity"


class IssueSeverity(str, Enum):
    """How the future runner should treat a validation issue."""

    BLOCKED = "blocked"
    FAULT = "fault"
    INTERRUPT = "interrupt"


REQUIRED_REQUEST_FIELDS: tuple[str, ...] = (
    "request_id",
    "request_uuid",
    "slice_id",
    "requested_operator_id",
    "requested_operator_version",
    "requested_outcome_kind",
    "input_ref_set",
    "authority_basis_ref_set",
    "expected_output_kind_set",
    "generated_output_policy_ref",
    "safety_limit_ref",
    "refusal_allowed",
)

UNSAFE_OPERATION_MARKERS: frozenset[str] = frozenset(
    {
        "credential_access",
        "destructive_filesystem",
        "dispatch",
        "gpu_control",
        "job_control",
        "live_dispatch",
        "live_machine_control",
        "network_control",
        "operations_control",
        "process_control",
    }
)


@dataclass(frozen=True)
class OperatorContract:
    """Accepted operator contract metadata needed for shape validation."""

    operator_id: str
    operator_version: str
    output_record_kind_set: frozenset[str]
    authority_basis_ref_set: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class OperatorRequest:
    """Contract-bound request for a future operator runner invocation."""

    request_id: str
    request_uuid: str
    slice_id: str
    requested_operator_id: str
    requested_operator_version: str
    requested_outcome_kind: OutcomeKind
    input_ref_set: tuple[str, ...]
    authority_basis_ref_set: tuple[str, ...]
    expected_output_kind_set: tuple[str, ...]
    generated_output_policy_ref: str
    safety_limit_ref: str
    refusal_allowed: bool
    completion_review_ref: str | None = None
    model_route: str | None = None
    authority_basis_state: str = "current"
    input_identity_state: str = "resolved"
    requested_scope: str = "accepted_activation_boundary"
    unsafe_operation_set: frozenset[str] = field(default_factory=frozenset)
    generated_projection_presented_as_authority: bool = False


@dataclass(frozen=True)
class ContractIssue:
    """One blocked, fault, or interrupt reason from request validation."""

    issue_kind: ContractIssueKind
    severity: IssueSeverity
    reason: str
    field_name: str | None = None


@dataclass(frozen=True)
class ContractValidationResult:
    """Result of pure request validation."""

    accepted: bool
    issues: tuple[ContractIssue, ...] = ()

    @property
    def has_fault(self) -> bool:
        return any(issue.severity == IssueSeverity.FAULT for issue in self.issues)

    @property
    def has_interrupt(self) -> bool:
        return any(issue.severity == IssueSeverity.INTERRUPT for issue in self.issues)

    @property
    def has_blocker(self) -> bool:
        return any(issue.severity == IssueSeverity.BLOCKED for issue in self.issues)


def request_from_mapping(data: Mapping[str, object]) -> OperatorRequest | ContractValidationResult:
    """Build an OperatorRequest or return shape issues without throwing."""

    missing = [
        ContractIssue(
            ContractIssueKind.MISSING_FIELD,
            IssueSeverity.FAULT,
            f"missing required request field: {field_name}",
            field_name,
        )
        for field_name in REQUIRED_REQUEST_FIELDS
        if field_name not in data
    ]
    if missing:
        return ContractValidationResult(False, tuple(missing))

    try:
        return OperatorRequest(
            request_id=str(data["request_id"]),
            request_uuid=str(data["request_uuid"]),
            slice_id=str(data["slice_id"]),
            requested_operator_id=str(data["requested_operator_id"]),
            requested_operator_version=str(data["requested_operator_version"]),
            requested_outcome_kind=OutcomeKind(str(data["requested_outcome_kind"])),
            input_ref_set=tuple(_as_string_sequence(data["input_ref_set"])),
            authority_basis_ref_set=tuple(_as_string_sequence(data["authority_basis_ref_set"])),
            expected_output_kind_set=tuple(_as_string_sequence(data["expected_output_kind_set"])),
            generated_output_policy_ref=str(data["generated_output_policy_ref"]),
            safety_limit_ref=str(data["safety_limit_ref"]),
            refusal_allowed=_as_bool(data["refusal_allowed"]),
            completion_review_ref=_optional_str(data.get("completion_review_ref")),
            model_route=_optional_str(data.get("model_route")),
            authority_basis_state=str(data.get("authority_basis_state", "current")),
            input_identity_state=str(data.get("input_identity_state", "resolved")),
            requested_scope=str(data.get("requested_scope", "accepted_activation_boundary")),
            unsafe_operation_set=frozenset(_as_string_sequence(data.get("unsafe_operation_set", ()))),
            generated_projection_presented_as_authority=_as_bool(
                data.get("generated_projection_presented_as_authority", False)
            ),
        )
    except (TypeError, ValueError) as exc:
        return ContractValidationResult(
            False,
            (
                ContractIssue(
                    ContractIssueKind.INVALID_FIELD,
                    IssueSeverity.FAULT,
                    str(exc),
                ),
            ),
        )


def validate_operator_request(
    request: OperatorRequest,
    contract: OperatorContract,
    *,
    accepted_scope: str = "accepted_activation_boundary",
) -> ContractValidationResult:
    """Validate a request against an accepted contract without executing it."""

    issues: list[ContractIssue] = []

    if request.requested_operator_id != contract.operator_id:
        issues.append(
            ContractIssue(
                ContractIssueKind.INVALID_FIELD,
                IssueSeverity.FAULT,
                "requested operator id does not match contract",
                "requested_operator_id",
            )
        )

    if request.requested_operator_version != contract.operator_version:
        issues.append(
            ContractIssue(
                ContractIssueKind.MISSING_FIELD,
                IssueSeverity.BLOCKED,
                "requested operator version is missing or not accepted",
                "requested_operator_version",
            )
        )

    if not request.refusal_allowed:
        issues.append(
            ContractIssue(
                ContractIssueKind.INVALID_FIELD,
                IssueSeverity.FAULT,
                "operator requests must allow refusal",
                "refusal_allowed",
            )
        )

    undeclared_outputs = set(request.expected_output_kind_set) - set(contract.output_record_kind_set)
    for output_kind in sorted(undeclared_outputs):
        issues.append(
            ContractIssue(
                ContractIssueKind.UNDECLARED_OUTPUT,
                IssueSeverity.FAULT,
                f"undeclared output kind requested: {output_kind}",
                "expected_output_kind_set",
            )
        )

    if request.authority_basis_state != "current":
        issues.append(
            ContractIssue(
                ContractIssueKind.STALE_AUTHORITY,
                IssueSeverity.BLOCKED,
                "authority basis is not current",
                "authority_basis_state",
            )
        )

    if request.generated_projection_presented_as_authority:
        issues.append(
            ContractIssue(
                ContractIssueKind.GENERATED_AUTHORITY,
                IssueSeverity.FAULT,
                "generated projection was presented as source authority",
                "authority_basis_ref_set",
            )
        )

    if request.input_identity_state == "ambiguous":
        issues.append(
            ContractIssue(
                ContractIssueKind.AMBIGUOUS_IDENTITY,
                IssueSeverity.INTERRUPT,
                "input identity is ambiguous",
                "input_identity_state",
            )
        )

    if request.requested_scope != accepted_scope:
        issues.append(
            ContractIssue(
                ContractIssueKind.UNSUPPORTED_SCOPE,
                IssueSeverity.BLOCKED,
                "requested scope is outside accepted activation boundary",
                "requested_scope",
            )
        )

    unsafe = request.unsafe_operation_set & UNSAFE_OPERATION_MARKERS
    for marker in sorted(unsafe):
        issues.append(
            ContractIssue(
                ContractIssueKind.UNSAFE_OPERATION,
                IssueSeverity.FAULT,
                f"unsafe operation requested: {marker}",
                "unsafe_operation_set",
            )
        )

    return ContractValidationResult(not issues, tuple(issues))


def _as_string_sequence(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Sequence):
        return tuple(str(item) for item in value)
    raise TypeError(f"expected sequence of strings, got {type(value).__name__}")


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "1"}:
            return True
        if lowered in {"false", "no", "0"}:
            return False
    raise TypeError(f"expected boolean value, got {value!r}")


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text or None
