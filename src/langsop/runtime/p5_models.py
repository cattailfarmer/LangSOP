"""P5 runtime model refresh helpers.

These helpers are pure data and classification utilities for the accepted P5
runtime implementation activation. They do not persist checkpoints, write
generated traces, dispatch work, or control live machine state.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from typing import Mapping, Sequence


NON_AUTHORITY_WARNING = (
    "P5 runtime records are runtime evidence only and do not replace signed SOP authority"
)
NO_ASSIGNMENT_NOTICE = "assignment_not_authorized_by_runtime_evidence"
NO_DISPATCH_NOTICE = "dispatch_not_authorized_by_runtime_evidence"
NO_OPERATIONS_CONTROL_NOTICE = "operations_control_not_authorized_by_runtime_evidence"
NO_LIVE_EFFECT_NOTICE = "live_effect_not_authorized_by_runtime_evidence"


class P5RuntimeRecordKind(str, Enum):
    """Accepted P5 runtime proof record kinds."""

    TRANSITION_TRACE = "transition_trace"
    GRAPH_CHECKPOINT = "graph_checkpoint"
    SOP_INTERRUPT = "SOP_interrupt"


class P5RuntimeState(str, Enum):
    """Accepted runtime state vocabulary from P5 planning contracts."""

    TRANSITION_ACCEPTED = "transition_accepted"
    REFUSED = "refused"
    INTERRUPTED = "interrupted"
    REBAKE_REQUIRED = "rebake_required"
    BLOCKED = "blocked"
    FAULTED = "faulted"
    NOT_RUN = "not_run"


class P5RuntimeIssueKind(str, Enum):
    """Issue vocabulary used by P5 runtime model classification."""

    CHECKPOINT_NOT_AUTHORITY = "checkpoint_not_authority"
    STALE_CHECKPOINT = "stale_checkpoint"
    AMBIGUOUS_AUTHORITY = "ambiguous_authority"
    GENERATED_TRACE_NOT_AUTHORITY = "generated_trace_not_authority"
    DISPATCH_NOT_AUTHORIZED = "dispatch_not_authorized"
    OPERATIONS_CONTROL_NOT_AUTHORIZED = "operations_control_not_authorized"
    LIVE_CONTROL_NOT_AUTHORIZED = "live_control_not_authorized"
    MISSING_RUNTIME_RECORD_KIND = "missing_runtime_record_kind"
    UNSUPPORTED_RUNTIME_RECORD_KIND = "unsupported_runtime_record_kind"


class P5RuntimeEdgeKind(str, Enum):
    """Deterministic transition edge kinds for P5 runtime evidence."""

    SUCCESS_EDGE = "success_edge"
    REFUSAL_EDGE = "refusal_edge"
    INTERRUPT_EDGE = "interrupt_edge"
    REBAKE_EDGE = "rebake_edge"
    BLOCKED_EDGE = "blocked_edge"
    FAULT_EDGE = "fault_edge"


@dataclass(frozen=True)
class P5RuntimeEvaluation:
    """Pure classification result for one P5 runtime fixture or model input."""

    runtime_record_kind: P5RuntimeRecordKind | None
    runtime_state: P5RuntimeState
    edge_kind: P5RuntimeEdgeKind
    accepted: bool
    issue_kind: P5RuntimeIssueKind | None = None
    checkpoint_authority: bool = False
    source_authority_preserved: bool = True
    dispatch_authority: bool = False
    operations_control_authority: bool = False
    live_control_authority: bool = False
    rebake_required: bool = False
    interrupt_required: bool = False
    nonpromotion_notice: str = NON_AUTHORITY_WARNING
    no_assignment_notice: str = NO_ASSIGNMENT_NOTICE
    no_dispatch_notice: str = NO_DISPATCH_NOTICE
    no_operations_control_notice: str = NO_OPERATIONS_CONTROL_NOTICE
    no_live_effect_notice: str = NO_LIVE_EFFECT_NOTICE

    @property
    def authority_safe(self) -> bool:
        """Return true when the evaluation does not claim forbidden authority."""

        return (
            not self.checkpoint_authority
            and self.source_authority_preserved
            and not self.dispatch_authority
            and not self.operations_control_authority
            and not self.live_control_authority
            and self.nonpromotion_notice == NON_AUTHORITY_WARNING
        )


@dataclass(frozen=True)
class P5TransitionEvidence:
    """Deterministic transition evidence record without persistence effects."""

    transition_id: str
    runtime_record_kind: P5RuntimeRecordKind | None
    runtime_state: P5RuntimeState
    edge_kind: P5RuntimeEdgeKind
    input_ref_set: tuple[str, ...]
    authority_basis_ref_set: tuple[str, ...]
    issue_kind: P5RuntimeIssueKind | None = None
    nonpromotion_notice: str = NON_AUTHORITY_WARNING
    no_assignment_notice: str = NO_ASSIGNMENT_NOTICE
    no_dispatch_notice: str = NO_DISPATCH_NOTICE
    no_operations_control_notice: str = NO_OPERATIONS_CONTROL_NOTICE
    no_live_effect_notice: str = NO_LIVE_EFFECT_NOTICE


def evaluate_p5_runtime_fields(field_map: Mapping[str, Sequence[str]]) -> P5RuntimeEvaluation:
    """Classify P5 runtime fixture fields without writing traces or checkpoints."""

    record_kind_text = _first(field_map, "runtime_record_kind")
    record_kind = _record_kind(record_kind_text)
    if record_kind_text is None:
        return _evaluation(
            record_kind=None,
            runtime_state=P5RuntimeState.BLOCKED,
            edge_kind=P5RuntimeEdgeKind.BLOCKED_EDGE,
            issue_kind=P5RuntimeIssueKind.MISSING_RUNTIME_RECORD_KIND,
        )
    if record_kind is None:
        return _evaluation(
            record_kind=None,
            runtime_state=P5RuntimeState.FAULTED,
            edge_kind=P5RuntimeEdgeKind.FAULT_EDGE,
            issue_kind=P5RuntimeIssueKind.UNSUPPORTED_RUNTIME_RECORD_KIND,
        )

    dispatch_authority = _bool(field_map, "dispatch_authority", False)
    operations_control_authority = _bool(field_map, "operations_control_authority", False)
    live_control_authority = _bool(field_map, "live_control_authority", False) or _bool(field_map, "live_effect", False)
    if dispatch_authority:
        return _evaluation(
            record_kind=record_kind,
            runtime_state=P5RuntimeState.FAULTED,
            edge_kind=P5RuntimeEdgeKind.FAULT_EDGE,
            issue_kind=P5RuntimeIssueKind.DISPATCH_NOT_AUTHORIZED,
            dispatch_authority=dispatch_authority,
            operations_control_authority=operations_control_authority,
            live_control_authority=live_control_authority,
        )
    if operations_control_authority:
        return _evaluation(
            record_kind=record_kind,
            runtime_state=P5RuntimeState.FAULTED,
            edge_kind=P5RuntimeEdgeKind.FAULT_EDGE,
            issue_kind=P5RuntimeIssueKind.OPERATIONS_CONTROL_NOT_AUTHORIZED,
            dispatch_authority=dispatch_authority,
            operations_control_authority=operations_control_authority,
            live_control_authority=live_control_authority,
        )
    if live_control_authority:
        return _evaluation(
            record_kind=record_kind,
            runtime_state=P5RuntimeState.FAULTED,
            edge_kind=P5RuntimeEdgeKind.FAULT_EDGE,
            issue_kind=P5RuntimeIssueKind.LIVE_CONTROL_NOT_AUTHORIZED,
            dispatch_authority=dispatch_authority,
            operations_control_authority=operations_control_authority,
            live_control_authority=live_control_authority,
        )

    checkpoint_authority = _bool(field_map, "checkpoint_authority", False)
    claimed_authority_class = _first(field_map, "claimed_authority_class", "")
    if checkpoint_authority or claimed_authority_class == "source_authority":
        return _evaluation(
            record_kind=record_kind,
            runtime_state=P5RuntimeState.REFUSED,
            edge_kind=P5RuntimeEdgeKind.REFUSAL_EDGE,
            issue_kind=P5RuntimeIssueKind.CHECKPOINT_NOT_AUTHORITY,
            checkpoint_authority=True,
        )

    if _bool(field_map, "generated_trace_authority", False):
        return _evaluation(
            record_kind=record_kind,
            runtime_state=P5RuntimeState.FAULTED,
            edge_kind=P5RuntimeEdgeKind.FAULT_EDGE,
            issue_kind=P5RuntimeIssueKind.GENERATED_TRACE_NOT_AUTHORITY,
        )

    checkpoint_state = _first(field_map, "checkpoint_state", "")
    source_input_state = _first(field_map, "source_input_state", "")
    if checkpoint_state == "stale" or source_input_state == "changed":
        return _evaluation(
            record_kind=record_kind,
            runtime_state=P5RuntimeState.REBAKE_REQUIRED,
            edge_kind=P5RuntimeEdgeKind.REBAKE_EDGE,
            issue_kind=P5RuntimeIssueKind.STALE_CHECKPOINT,
            rebake_required=True,
        )

    if _bool(field_map, "human_judgment_required", False) or _first(field_map, "interrupt_reason"):
        return _evaluation(
            record_kind=record_kind,
            runtime_state=P5RuntimeState.INTERRUPTED,
            edge_kind=P5RuntimeEdgeKind.INTERRUPT_EDGE,
            issue_kind=P5RuntimeIssueKind.AMBIGUOUS_AUTHORITY,
            interrupt_required=True,
        )

    expected_state = _runtime_state(_first(field_map, "expected_runtime_state"))
    if expected_state is not None and expected_state != P5RuntimeState.TRANSITION_ACCEPTED:
        return _evaluation(
            record_kind=record_kind,
            runtime_state=expected_state,
            edge_kind=_edge_for_state(expected_state),
        )

    if _first(field_map, "operator_result", "") == "accepted" or expected_state == P5RuntimeState.TRANSITION_ACCEPTED:
        return _evaluation(
            record_kind=record_kind,
            runtime_state=P5RuntimeState.TRANSITION_ACCEPTED,
            edge_kind=P5RuntimeEdgeKind.SUCCESS_EDGE,
            accepted=True,
        )

    return _evaluation(
        record_kind=record_kind,
        runtime_state=P5RuntimeState.BLOCKED,
        edge_kind=P5RuntimeEdgeKind.BLOCKED_EDGE,
    )


def build_p5_transition_evidence(
    evaluation: P5RuntimeEvaluation,
    *,
    input_ref_set: Sequence[str],
    authority_basis_ref_set: Sequence[str],
) -> P5TransitionEvidence:
    """Build deterministic transition evidence without persisting it."""

    transition_id = deterministic_transition_id(
        runtime_record_kind=evaluation.runtime_record_kind.value if evaluation.runtime_record_kind else "none",
        runtime_state=evaluation.runtime_state.value,
        edge_kind=evaluation.edge_kind.value,
        input_ref_set=tuple(input_ref_set),
        authority_basis_ref_set=tuple(authority_basis_ref_set),
        issue_kind=evaluation.issue_kind.value if evaluation.issue_kind else "none",
    )
    return P5TransitionEvidence(
        transition_id=transition_id,
        runtime_record_kind=evaluation.runtime_record_kind,
        runtime_state=evaluation.runtime_state,
        edge_kind=evaluation.edge_kind,
        input_ref_set=tuple(input_ref_set),
        authority_basis_ref_set=tuple(authority_basis_ref_set),
        issue_kind=evaluation.issue_kind,
    )


def deterministic_transition_id(
    *,
    runtime_record_kind: str,
    runtime_state: str,
    edge_kind: str,
    input_ref_set: Sequence[str],
    authority_basis_ref_set: Sequence[str],
    issue_kind: str = "none",
) -> str:
    """Return a stable id for fixed P5 runtime transition evidence."""

    payload = {
        "authority_basis_ref_set": sorted(authority_basis_ref_set),
        "edge_kind": edge_kind,
        "input_ref_set": sorted(input_ref_set),
        "issue_kind": issue_kind,
        "runtime_record_kind": runtime_record_kind,
        "runtime_state": runtime_state,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def runtime_evaluation_fact_set(evaluation: P5RuntimeEvaluation) -> frozenset[str]:
    """Return reviewable facts for fixture comparison and future proof ledgers."""

    facts = {
        f"runtime_state is {evaluation.runtime_state.value}",
        f"edge_kind is {evaluation.edge_kind.value}",
        f"accepted is {_bool_text(evaluation.accepted)}",
        f"checkpoint_authority is {_bool_text(evaluation.checkpoint_authority)}",
        f"source_authority_preserved is {_bool_text(evaluation.source_authority_preserved)}",
        f"dispatch_authority is {_bool_text(evaluation.dispatch_authority)}",
        f"operations_control_authority is {_bool_text(evaluation.operations_control_authority)}",
        f"live_control_authority is {_bool_text(evaluation.live_control_authority)}",
        f"rebake_required is {_bool_text(evaluation.rebake_required)}",
        f"interrupt_required is {_bool_text(evaluation.interrupt_required)}",
        f"nonpromotion_notice is {evaluation.nonpromotion_notice}",
        f"no_assignment_notice is {evaluation.no_assignment_notice}",
        f"no_dispatch_notice is {evaluation.no_dispatch_notice}",
        f"no_operations_control_notice is {evaluation.no_operations_control_notice}",
        f"no_live_effect_notice is {evaluation.no_live_effect_notice}",
    }
    if evaluation.runtime_record_kind is not None:
        facts.add(f"runtime_record_kind is {evaluation.runtime_record_kind.value}")
    if evaluation.issue_kind is not None:
        facts.add(f"issue_kind is {evaluation.issue_kind.value}")
    return frozenset(facts)


def _evaluation(
    *,
    record_kind: P5RuntimeRecordKind | None,
    runtime_state: P5RuntimeState,
    edge_kind: P5RuntimeEdgeKind,
    issue_kind: P5RuntimeIssueKind | None = None,
    accepted: bool = False,
    checkpoint_authority: bool = False,
    source_authority_preserved: bool = True,
    dispatch_authority: bool = False,
    operations_control_authority: bool = False,
    live_control_authority: bool = False,
    rebake_required: bool = False,
    interrupt_required: bool = False,
) -> P5RuntimeEvaluation:
    return P5RuntimeEvaluation(
        runtime_record_kind=record_kind,
        runtime_state=runtime_state,
        edge_kind=edge_kind,
        accepted=accepted,
        issue_kind=issue_kind,
        checkpoint_authority=checkpoint_authority,
        source_authority_preserved=source_authority_preserved,
        dispatch_authority=dispatch_authority,
        operations_control_authority=operations_control_authority,
        live_control_authority=live_control_authority,
        rebake_required=rebake_required,
        interrupt_required=interrupt_required,
    )


def _edge_for_state(state: P5RuntimeState) -> P5RuntimeEdgeKind:
    if state == P5RuntimeState.TRANSITION_ACCEPTED:
        return P5RuntimeEdgeKind.SUCCESS_EDGE
    if state == P5RuntimeState.REFUSED:
        return P5RuntimeEdgeKind.REFUSAL_EDGE
    if state == P5RuntimeState.INTERRUPTED:
        return P5RuntimeEdgeKind.INTERRUPT_EDGE
    if state == P5RuntimeState.REBAKE_REQUIRED:
        return P5RuntimeEdgeKind.REBAKE_EDGE
    if state == P5RuntimeState.FAULTED:
        return P5RuntimeEdgeKind.FAULT_EDGE
    return P5RuntimeEdgeKind.BLOCKED_EDGE


def _record_kind(value: str | None) -> P5RuntimeRecordKind | None:
    if value is None:
        return None
    try:
        return P5RuntimeRecordKind(value)
    except ValueError:
        return None


def _runtime_state(value: str | None) -> P5RuntimeState | None:
    if value is None:
        return None
    try:
        return P5RuntimeState(value)
    except ValueError:
        return None


def _first(fields: Mapping[str, Sequence[str]], name: str, default: str | None = None) -> str | None:
    values = fields.get(name, ())
    if values:
        return str(values[0])
    return default


def _bool(fields: Mapping[str, Sequence[str]], name: str, default: bool) -> bool:
    value = _first(fields, name)
    if value is None:
        return default
    return value.strip().lower() in {"true", "yes", "1"}


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


__all__ = (
    "NO_ASSIGNMENT_NOTICE",
    "NO_DISPATCH_NOTICE",
    "NO_LIVE_EFFECT_NOTICE",
    "NO_OPERATIONS_CONTROL_NOTICE",
    "NON_AUTHORITY_WARNING",
    "P5RuntimeEdgeKind",
    "P5RuntimeEvaluation",
    "P5RuntimeIssueKind",
    "P5RuntimeRecordKind",
    "P5RuntimeState",
    "P5TransitionEvidence",
    "build_p5_transition_evidence",
    "deterministic_transition_id",
    "evaluate_p5_runtime_fields",
    "runtime_evaluation_fact_set",
)
