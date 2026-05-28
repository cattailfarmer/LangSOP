"""P6 nonpromotion classification helpers.

Nonpromotion checks keep generated projections, carrier context, checkpoints,
dry-run displays, and human handoff displays from becoming source, assignment,
dispatch, operations, or live-control authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Sequence

from .envelope import (
    NO_ASSIGNMENT_NOTICE,
    NO_DISPATCH_NOTICE,
    NO_LIVE_EFFECT_NOTICE,
    NO_OPERATIONS_CONTROL_NOTICE,
    NON_AUTHORITY_WARNING,
)


class P6NonpromotedClass(str, Enum):
    """Record classes that P6 must render as non-authoritative."""

    GRAPH_CHECKPOINT_STATE = "graph_checkpoint_state"
    GRAPH_TRANSITION_TRACE = "graph_transition_trace"
    GENERATED_OUTPUT_TRACE = "generated_output_trace"
    GENERATED_PROJECTION = "generated_projection"
    SURFACE_SNAPSHOT = "surface_snapshot"
    TERMINAL_OUTPUT_PROJECTION = "terminal_output_projection"
    DRY_RUN_OUTPUT = "dry_run_output"
    HUMAN_HANDOFF_DISPLAY = "human_handoff_display"
    HUMAN_APPROVAL_DISPLAY = "human_approval_display"
    CARRIER_CONTEXT = "carrier_context"


class P6ForbiddenAuthorityClass(str, Enum):
    """Authority classes forbidden for nonpromoted records."""

    SOURCE_AUTHORITY = "source_authority"
    CANONICAL_SPECIFICATION = "canonical_specification"
    COMPLETION_REVIEW = "completion_review"
    ASSIGNMENT_AUTHORITY = "assignment_authority"
    DISPATCH_AUTHORITY = "dispatch_authority"
    OPERATIONS_AUTHORITY = "operations_authority"
    LIVE_CONTROL_AUTHORITY = "live_control_authority"


class P6NonpromotionState(str, Enum):
    """Classification result for nonpromotion evaluation."""

    PRESERVED = "preserved"
    REFUSED = "refused"
    FAULTED = "faulted"
    STALE = "stale"
    BLOCKED = "blocked"


class P6NonpromotionIssueKind(str, Enum):
    """Issue vocabulary for P6 nonpromotion evaluation."""

    MISSING_RECORD_CLASS = "missing_record_class"
    UNSUPPORTED_RECORD_CLASS = "unsupported_record_class"
    MISSING_NONPROMOTION_NOTICE = "missing_nonpromotion_notice"
    GENERATED_PROJECTION_PROMOTED_TO_AUTHORITY = "generated_projection_promoted_to_authority"
    CHECKPOINT_PROMOTED_TO_AUTHORITY = "checkpoint_promoted_to_authority"
    CARRIER_CONTEXT_PROMOTED_TO_AUTHORITY = "carrier_context_promoted_to_authority"
    DRY_RUN_PROMOTED_TO_LIVE_CONTROL = "dry_run_promoted_to_live_control"
    HUMAN_APPROVAL_PROMOTED_TO_LIVE_CONTROL = "human_approval_promoted_to_live_control"
    ASSIGNMENT_AUTHORITY_REQUESTED = "assignment_authority_requested"
    DISPATCH_AUTHORITY_REQUESTED = "dispatch_authority_requested"
    OPERATIONS_CONTROL_REQUESTED = "operations_control_requested"
    LIVE_CONTROL_REQUESTED = "live_control_requested"
    STALE_SOURCE_BASIS = "stale_source_basis"


@dataclass(frozen=True)
class P6NonpromotionEvaluation:
    """Pure nonpromotion classification result for one record."""

    record_class: P6NonpromotedClass | None
    state: P6NonpromotionState
    accepted: bool
    issue_kind: P6NonpromotionIssueKind | None = None
    claimed_authority_class: str = ""
    source_authority_preserved: bool = True
    assignment_authority: bool = False
    dispatch_authority: bool = False
    operations_control_authority: bool = False
    live_control_authority: bool = False
    nonpromotion_notice: str = NON_AUTHORITY_WARNING
    no_assignment_notice: str = NO_ASSIGNMENT_NOTICE
    no_dispatch_notice: str = NO_DISPATCH_NOTICE
    no_operations_control_notice: str = NO_OPERATIONS_CONTROL_NOTICE
    no_live_effect_notice: str = NO_LIVE_EFFECT_NOTICE

    @property
    def authority_safe(self) -> bool:
        return (
            self.source_authority_preserved
            and not self.assignment_authority
            and not self.dispatch_authority
            and not self.operations_control_authority
            and not self.live_control_authority
            and self.nonpromotion_notice == NON_AUTHORITY_WARNING
        )


def evaluate_p6_nonpromotion_fields(field_map: Mapping[str, Sequence[str]]) -> P6NonpromotionEvaluation:
    """Classify P6 nonpromotion fixture fields without writing projections."""

    record_class_text = _first(
        field_map,
        "projection_record_kind",
        _first(field_map, "record_class", _first(field_map, "nonpromoted_class")),
    )
    record_class = _record_class(record_class_text)
    if record_class_text is None:
        return _evaluation(
            record_class=None,
            state=P6NonpromotionState.BLOCKED,
            issue_kind=P6NonpromotionIssueKind.MISSING_RECORD_CLASS,
        )
    if record_class is None:
        return _evaluation(
            record_class=None,
            state=P6NonpromotionState.FAULTED,
            issue_kind=P6NonpromotionIssueKind.UNSUPPORTED_RECORD_CLASS,
        )

    missing_notice = not (
        _first(field_map, "required_notice")
        or _first(field_map, "nonpromotion_notice")
        or _first(field_map, "required_nonpromotion_notice")
    )
    if missing_notice:
        return _evaluation(
            record_class=record_class,
            state=P6NonpromotionState.FAULTED,
            issue_kind=P6NonpromotionIssueKind.MISSING_NONPROMOTION_NOTICE,
        )

    claimed_authority_class = _first(field_map, "claimed_authority_class", "")
    if claimed_authority_class in {item.value for item in P6ForbiddenAuthorityClass}:
        return _authority_promotion_evaluation(record_class, claimed_authority_class)

    if _bool(field_map, "assignment_authority", False):
        return _evaluation(
            record_class=record_class,
            state=P6NonpromotionState.REFUSED,
            issue_kind=P6NonpromotionIssueKind.ASSIGNMENT_AUTHORITY_REQUESTED,
            assignment_authority=True,
        )
    if _bool(field_map, "dispatch_authority", False):
        return _evaluation(
            record_class=record_class,
            state=P6NonpromotionState.REFUSED,
            issue_kind=P6NonpromotionIssueKind.DISPATCH_AUTHORITY_REQUESTED,
            dispatch_authority=True,
        )
    if _bool(field_map, "operations_control_authority", False):
        return _evaluation(
            record_class=record_class,
            state=P6NonpromotionState.REFUSED,
            issue_kind=P6NonpromotionIssueKind.OPERATIONS_CONTROL_REQUESTED,
            operations_control_authority=True,
        )
    if _bool(field_map, "live_control_authority", False) or _bool(field_map, "live_effect", False):
        return _evaluation(
            record_class=record_class,
            state=P6NonpromotionState.REFUSED,
            issue_kind=P6NonpromotionIssueKind.LIVE_CONTROL_REQUESTED,
            live_control_authority=True,
        )

    if _first(field_map, "freshness_state", "") == "stale" or _first(field_map, "source_authority_state", "") == "stale":
        return _evaluation(
            record_class=record_class,
            state=P6NonpromotionState.STALE,
            issue_kind=P6NonpromotionIssueKind.STALE_SOURCE_BASIS,
            accepted=True,
        )

    return _evaluation(record_class=record_class, state=P6NonpromotionState.PRESERVED, accepted=True)


def p6_nonpromotion_fact_set(evaluation: P6NonpromotionEvaluation) -> frozenset[str]:
    """Return reviewable nonpromotion facts for fixture comparison."""

    facts = {
        f"nonpromotion_state is {evaluation.state.value}",
        f"accepted is {_bool_text(evaluation.accepted)}",
        f"authority_safe is {_bool_text(evaluation.authority_safe)}",
        f"source_authority_preserved is {_bool_text(evaluation.source_authority_preserved)}",
        f"assignment_authority is {_bool_text(evaluation.assignment_authority)}",
        f"dispatch_authority is {_bool_text(evaluation.dispatch_authority)}",
        f"operations_control_authority is {_bool_text(evaluation.operations_control_authority)}",
        f"live_control_authority is {_bool_text(evaluation.live_control_authority)}",
        f"nonpromotion_notice is {evaluation.nonpromotion_notice}",
        f"no_assignment_notice is {evaluation.no_assignment_notice}",
        f"no_dispatch_notice is {evaluation.no_dispatch_notice}",
        f"no_operations_control_notice is {evaluation.no_operations_control_notice}",
        f"no_live_effect_notice is {evaluation.no_live_effect_notice}",
    }
    if evaluation.record_class is not None:
        facts.add(f"record_class is {evaluation.record_class.value}")
    if evaluation.issue_kind is not None:
        facts.add(f"issue_kind is {evaluation.issue_kind.value}")
    if evaluation.claimed_authority_class:
        facts.add(f"claimed_authority_class is {evaluation.claimed_authority_class}")
    return frozenset(facts)


def _authority_promotion_evaluation(
    record_class: P6NonpromotedClass,
    claimed_authority_class: str,
) -> P6NonpromotionEvaluation:
    if record_class == P6NonpromotedClass.GENERATED_PROJECTION:
        issue_kind = P6NonpromotionIssueKind.GENERATED_PROJECTION_PROMOTED_TO_AUTHORITY
    elif record_class in {P6NonpromotedClass.GRAPH_CHECKPOINT_STATE, P6NonpromotedClass.GRAPH_TRANSITION_TRACE}:
        issue_kind = P6NonpromotionIssueKind.CHECKPOINT_PROMOTED_TO_AUTHORITY
    elif record_class == P6NonpromotedClass.CARRIER_CONTEXT:
        issue_kind = P6NonpromotionIssueKind.CARRIER_CONTEXT_PROMOTED_TO_AUTHORITY
    elif record_class == P6NonpromotedClass.DRY_RUN_OUTPUT:
        issue_kind = P6NonpromotionIssueKind.DRY_RUN_PROMOTED_TO_LIVE_CONTROL
    elif record_class == P6NonpromotedClass.HUMAN_APPROVAL_DISPLAY:
        issue_kind = P6NonpromotionIssueKind.HUMAN_APPROVAL_PROMOTED_TO_LIVE_CONTROL
    else:
        issue_kind = P6NonpromotionIssueKind.GENERATED_PROJECTION_PROMOTED_TO_AUTHORITY
    return _evaluation(
        record_class=record_class,
        state=P6NonpromotionState.FAULTED,
        issue_kind=issue_kind,
        claimed_authority_class=claimed_authority_class,
    )


def _evaluation(
    *,
    record_class: P6NonpromotedClass | None,
    state: P6NonpromotionState,
    accepted: bool = False,
    issue_kind: P6NonpromotionIssueKind | None = None,
    claimed_authority_class: str = "",
    assignment_authority: bool = False,
    dispatch_authority: bool = False,
    operations_control_authority: bool = False,
    live_control_authority: bool = False,
) -> P6NonpromotionEvaluation:
    return P6NonpromotionEvaluation(
        record_class=record_class,
        state=state,
        accepted=accepted,
        issue_kind=issue_kind,
        claimed_authority_class=claimed_authority_class,
        assignment_authority=assignment_authority,
        dispatch_authority=dispatch_authority,
        operations_control_authority=operations_control_authority,
        live_control_authority=live_control_authority,
    )


def _record_class(value: str | None) -> P6NonpromotedClass | None:
    if value is None:
        return None
    try:
        return P6NonpromotedClass(value)
    except ValueError:
        return None


def _first(fields: Mapping[str, Sequence[str]], name: str | None, default: str | None = None) -> str | None:
    if name is None:
        return default
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
    "P6ForbiddenAuthorityClass",
    "P6NonpromotedClass",
    "P6NonpromotionEvaluation",
    "P6NonpromotionIssueKind",
    "P6NonpromotionState",
    "evaluate_p6_nonpromotion_fields",
    "p6_nonpromotion_fact_set",
)
