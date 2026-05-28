"""P6 surface projection envelope models.

These helpers are pure data and validation utilities for accepted P6 surface
implementation activation. They do not write generated projections, call
adapters, render UI, dispatch work, or control live machine state.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Mapping, Sequence


NON_AUTHORITY_WARNING = (
    "P6 surface projections are display evidence only and do not replace signed SOP authority"
)
NO_ASSIGNMENT_NOTICE = "assignment_not_authorized_by_surface_projection"
NO_DISPATCH_NOTICE = "dispatch_not_authorized_by_surface_projection"
NO_OPERATIONS_CONTROL_NOTICE = "operations_control_not_authorized_by_surface_projection"
NO_LIVE_EFFECT_NOTICE = "live_effect_not_authorized_by_surface_projection"
DEFAULT_MUTATION_BOUNDARY_REF = "projection_only_no_source_mutation"


class P6AuthorityTier(str, Enum):
    """Accepted authority tiers for P6 projection records."""

    SOURCE_AUTHORITY = "source_authority"
    ACCEPTED_REVIEW_AUTHORITY = "accepted_review_authority"
    ACCEPTED_PROOF_SUPPORT = "accepted_proof_support"
    GENERATED_PROJECTION_EVIDENCE = "generated_projection_evidence"
    CARRIER_CONTEXT = "carrier_context"


class P6FreshnessState(str, Enum):
    """Freshness vocabulary used by P6 authority notices."""

    FRESH = "fresh"
    STALE = "stale"
    UNKNOWN = "unknown"
    CONTESTED = "contested"
    INTERRUPTED = "interrupted"
    BLOCKED = "blocked"
    FAULTED = "faulted"
    PENDING_REVIEW = "pending_review"


class P6ProjectionStatus(str, Enum):
    """Stable status vocabulary for P6 projected surfaces."""

    READY = "ready"
    BLOCKED = "blocked"
    STALE = "stale"
    FAULTED = "faulted"
    INTERRUPTED = "interrupted"
    CONTESTED = "contested"
    PENDING_REVIEW = "pending_review"
    UNSUPPORTED_SCOPE = "unsupported_scope"
    REFUSED = "refused"


class P6SurfaceFamily(str, Enum):
    """Projection carrier families accepted by P6."""

    MANAGER = "manager"
    WORKER = "worker"
    NARRATIVE = "narrative"
    DEBUG = "debug"
    CHAT = "chat"
    CODEX = "Codex"
    TERMINAL = "terminal"
    IRC = "IRC"
    MATRIX = "Matrix"
    WEB = "web"
    LANGFLOW = "Langflow"


class P6ProjectionIssueKind(str, Enum):
    """Issue vocabulary for P6 projection envelope validation."""

    MISSING_FIELD = "missing_field"
    MISSING_SOURCE_REF = "missing_source_ref_set"
    MISSING_SOURCE_HASH = "missing_source_authority_sha256_set"
    MISSING_LINEAGE = "missing_lineage_edge_set"
    MISSING_AUTHORITY_NOTICE = "missing_authority_notice"
    MISSING_NONPROMOTION_NOTICE = "missing_nonpromotion_notice"
    MISSING_FORBIDDEN_ACTION = "missing_forbidden_action_set"
    MISSING_REQUIRED_ROUTE = "missing_required_route_set"
    READY_WITH_STOP_STATE = "ready_with_stop_state"
    READY_WITH_UNFRESH_STATE = "ready_with_unfresh_state"
    LOWER_TIER_PROMOTED = "lower_authority_tier_promoted"
    DIRECT_MUTATION_REQUESTED = "direct_source_mutation_requested"
    ASSIGNMENT_REQUESTED = "assignment_requested"
    DISPATCH_REQUESTED = "dispatch_requested"
    OPERATIONS_CONTROL_REQUESTED = "operations_control_requested"
    LIVE_CONTROL_REQUESTED = "live_control_requested"


class P6ProjectionIssueSeverity(str, Enum):
    """How a future P6 projector should treat an envelope issue."""

    BLOCKED = "blocked"
    STALE = "stale"
    FAULT = "fault"
    INTERRUPT = "interrupt"
    REFUSED = "refused"


REQUIRED_P6_PROJECTION_FIELD_SET: tuple[str, ...] = (
    "projection_id",
    "projection_uuid",
    "projection_kind",
    "surface_family",
    "carrier_surface",
    "projected_subject_ref",
    "source_record_ref_set",
    "source_authority_sha256_set",
    "lineage_edge_set",
    "authority_notice_ref",
    "authority_tier",
    "freshness_state",
    "projected_status",
    "nonpromotion_notice_set",
    "forbidden_action_set",
    "required_route_set",
    "mutation_boundary_ref",
    "generated_at",
)

STOP_STATE_STATUS_SET: frozenset[P6ProjectionStatus] = frozenset(
    {
        P6ProjectionStatus.BLOCKED,
        P6ProjectionStatus.STALE,
        P6ProjectionStatus.FAULTED,
        P6ProjectionStatus.INTERRUPTED,
        P6ProjectionStatus.CONTESTED,
        P6ProjectionStatus.PENDING_REVIEW,
        P6ProjectionStatus.UNSUPPORTED_SCOPE,
        P6ProjectionStatus.REFUSED,
    }
)

LOWER_AUTHORITY_TIER_SET: frozenset[P6AuthorityTier] = frozenset(
    {
        P6AuthorityTier.ACCEPTED_PROOF_SUPPORT,
        P6AuthorityTier.GENERATED_PROJECTION_EVIDENCE,
        P6AuthorityTier.CARRIER_CONTEXT,
    }
)


@dataclass(frozen=True)
class P6ProjectionIssue:
    """One blocked, stale, fault, interrupt, or refusal reason."""

    issue_kind: P6ProjectionIssueKind
    severity: P6ProjectionIssueSeverity
    reason: str
    field_name: str | None = None


@dataclass(frozen=True)
class P6ProjectionValidationResult:
    """Pure validation result for one P6 projection envelope."""

    accepted: bool
    issues: tuple[P6ProjectionIssue, ...] = ()

    @property
    def has_fault(self) -> bool:
        return any(issue.severity == P6ProjectionIssueSeverity.FAULT for issue in self.issues)

    @property
    def has_interrupt(self) -> bool:
        return any(issue.severity == P6ProjectionIssueSeverity.INTERRUPT for issue in self.issues)

    @property
    def has_stale(self) -> bool:
        return any(issue.severity == P6ProjectionIssueSeverity.STALE for issue in self.issues)

    @property
    def has_blocker(self) -> bool:
        return any(issue.severity == P6ProjectionIssueSeverity.BLOCKED for issue in self.issues)

    @property
    def has_refusal(self) -> bool:
        return any(issue.severity == P6ProjectionIssueSeverity.REFUSED for issue in self.issues)


@dataclass(frozen=True)
class P6ProjectionEnvelope:
    """Common P6 projection envelope with visible authority and stop-state data."""

    projection_id: str
    projection_uuid: str
    projection_kind: str
    surface_family: P6SurfaceFamily
    carrier_surface: str
    projected_subject_ref: str
    source_record_ref_set: tuple[str, ...]
    source_authority_sha256_set: tuple[str, ...]
    lineage_edge_set: tuple[str, ...]
    authority_notice_ref: str
    authority_tier: P6AuthorityTier
    freshness_state: P6FreshnessState
    projected_status: P6ProjectionStatus
    nonpromotion_notice_set: tuple[str, ...]
    forbidden_action_set: tuple[str, ...]
    required_route_set: tuple[str, ...]
    mutation_boundary_ref: str
    generated_at: str
    permitted_action_set: tuple[str, ...] = ()
    stop_state_ref_set: tuple[str, ...] = ()
    stale_trigger_set: tuple[str, ...] = ()
    invalidation_ref_set: tuple[str, ...] = ()
    carrier_context_ref: str = ""
    risk_reason: str = ""
    visible_before_action: bool = True
    lower_authority_tier_claimed_as_source: bool = False
    source_authority_mutation_requested: bool = False
    assignment_requested: bool = False
    dispatch_requested: bool = False
    operations_control_requested: bool = False
    live_control_requested: bool = False
    no_assignment_notice: str = NO_ASSIGNMENT_NOTICE
    no_dispatch_notice: str = NO_DISPATCH_NOTICE
    no_operations_control_notice: str = NO_OPERATIONS_CONTROL_NOTICE
    no_live_effect_notice: str = NO_LIVE_EFFECT_NOTICE

    @property
    def is_ready(self) -> bool:
        return self.projected_status == P6ProjectionStatus.READY

    @property
    def has_stop_state(self) -> bool:
        return bool(self.stop_state_ref_set or self.invalidation_ref_set)

    @property
    def authority_safe(self) -> bool:
        return (
            not self.lower_authority_tier_claimed_as_source
            and not self.source_authority_mutation_requested
            and not self.assignment_requested
            and not self.dispatch_requested
            and not self.operations_control_requested
            and not self.live_control_requested
        )


def p6_projection_envelope_from_parts(
    *,
    projection_id: str,
    projection_uuid: str,
    projection_kind: str,
    surface_family: str | P6SurfaceFamily,
    carrier_surface: str,
    projected_subject_ref: str,
    source_record_ref_set: Iterable[str],
    source_authority_sha256_set: Iterable[str],
    lineage_edge_set: Iterable[str],
    authority_notice_ref: str,
    authority_tier: str | P6AuthorityTier,
    freshness_state: str | P6FreshnessState,
    projected_status: str | P6ProjectionStatus,
    nonpromotion_notice_set: Iterable[str],
    forbidden_action_set: Iterable[str],
    required_route_set: Iterable[str],
    generated_at: str,
    mutation_boundary_ref: str = DEFAULT_MUTATION_BOUNDARY_REF,
    permitted_action_set: Iterable[str] = (),
    stop_state_ref_set: Iterable[str] = (),
    stale_trigger_set: Iterable[str] = (),
    invalidation_ref_set: Iterable[str] = (),
    carrier_context_ref: str = "",
    risk_reason: str = "",
    visible_before_action: bool = True,
    lower_authority_tier_claimed_as_source: bool = False,
    source_authority_mutation_requested: bool = False,
    assignment_requested: bool = False,
    dispatch_requested: bool = False,
    operations_control_requested: bool = False,
    live_control_requested: bool = False,
) -> P6ProjectionEnvelope:
    """Build a P6 projection envelope while normalizing enums and iterables."""

    return P6ProjectionEnvelope(
        projection_id=projection_id,
        projection_uuid=projection_uuid,
        projection_kind=projection_kind,
        surface_family=P6SurfaceFamily(surface_family),
        carrier_surface=carrier_surface,
        projected_subject_ref=projected_subject_ref,
        source_record_ref_set=tuple(source_record_ref_set),
        source_authority_sha256_set=tuple(source_authority_sha256_set),
        lineage_edge_set=tuple(lineage_edge_set),
        authority_notice_ref=authority_notice_ref,
        authority_tier=P6AuthorityTier(authority_tier),
        freshness_state=P6FreshnessState(freshness_state),
        projected_status=P6ProjectionStatus(projected_status),
        nonpromotion_notice_set=tuple(nonpromotion_notice_set),
        forbidden_action_set=tuple(forbidden_action_set),
        required_route_set=tuple(required_route_set),
        mutation_boundary_ref=mutation_boundary_ref,
        generated_at=generated_at,
        permitted_action_set=tuple(permitted_action_set),
        stop_state_ref_set=tuple(stop_state_ref_set),
        stale_trigger_set=tuple(stale_trigger_set),
        invalidation_ref_set=tuple(invalidation_ref_set),
        carrier_context_ref=carrier_context_ref,
        risk_reason=risk_reason,
        visible_before_action=visible_before_action,
        lower_authority_tier_claimed_as_source=lower_authority_tier_claimed_as_source,
        source_authority_mutation_requested=source_authority_mutation_requested,
        assignment_requested=assignment_requested,
        dispatch_requested=dispatch_requested,
        operations_control_requested=operations_control_requested,
        live_control_requested=live_control_requested,
    )


def p6_projection_envelope_from_mapping(data: Mapping[str, object]) -> P6ProjectionEnvelope:
    """Build a P6 projection envelope from mapping data."""

    projection_id = str(data.get("projection_id", data.get("fixture_case", "")))
    return p6_projection_envelope_from_parts(
        projection_id=projection_id,
        projection_uuid=str(data.get("projection_uuid", projection_id)),
        projection_kind=str(data.get("projection_kind", "surface_projection")),
        surface_family=str(data.get("surface_family", data.get("surface_kind", P6SurfaceFamily.CHAT.value))),
        carrier_surface=str(data.get("carrier_surface", data.get("surface_kind", ""))),
        projected_subject_ref=str(data.get("projected_subject_ref", projection_id)),
        source_record_ref_set=_as_string_sequence(data.get("source_record_ref_set", data.get("source_ref_set", ()))),
        source_authority_sha256_set=_as_string_sequence(data.get("source_authority_sha256_set", ())),
        lineage_edge_set=_as_string_sequence(data.get("lineage_edge_set", ())),
        authority_notice_ref=str(data.get("authority_notice_ref", data.get("required_notice", ""))),
        authority_tier=str(data.get("authority_tier", P6AuthorityTier.GENERATED_PROJECTION_EVIDENCE.value)),
        freshness_state=_freshness_value(data.get("freshness_state", P6FreshnessState.UNKNOWN.value)),
        projected_status=_projection_status_value(data.get("projected_status", P6ProjectionStatus.BLOCKED.value)),
        nonpromotion_notice_set=_as_string_sequence(data.get("nonpromotion_notice_set", (NON_AUTHORITY_WARNING,))),
        forbidden_action_set=_as_string_sequence(data.get("forbidden_action_set", ())),
        required_route_set=_as_string_sequence(data.get("required_route_set", ())),
        generated_at=str(data.get("generated_at", "projection_time_unset")),
        permitted_action_set=_as_string_sequence(data.get("permitted_action_set", ())),
        stop_state_ref_set=_as_string_sequence(data.get("stop_state_ref_set", ())),
        stale_trigger_set=_as_string_sequence(data.get("stale_trigger_set", ())),
        invalidation_ref_set=_as_string_sequence(data.get("invalidation_ref_set", ())),
        carrier_context_ref=str(data.get("carrier_context_ref", "")),
        risk_reason=str(data.get("risk_reason", "")),
        visible_before_action=_as_bool(data.get("visible_before_action", True)),
        lower_authority_tier_claimed_as_source=_as_bool(
            data.get("lower_authority_tier_claimed_as_source", False)
        ),
        source_authority_mutation_requested=_as_bool(
            data.get("source_authority_mutation_requested", False)
        ),
        assignment_requested=_as_bool(data.get("assignment_requested", False)),
        dispatch_requested=_as_bool(data.get("dispatch_requested", False)),
        operations_control_requested=_as_bool(data.get("operations_control_requested", False)),
        live_control_requested=_as_bool(data.get("live_control_requested", False)),
    )


def validate_p6_projection_envelope(envelope: P6ProjectionEnvelope) -> P6ProjectionValidationResult:
    """Validate a P6 projection envelope against authority and freshness rules."""

    issues: list[P6ProjectionIssue] = []
    for field_name in REQUIRED_P6_PROJECTION_FIELD_SET:
        if not _field_has_value(envelope, field_name):
            issues.append(_missing_field_issue(field_name))

    if not envelope.source_record_ref_set:
        issues.append(
            P6ProjectionIssue(
                P6ProjectionIssueKind.MISSING_SOURCE_REF,
                P6ProjectionIssueSeverity.FAULT,
                "source_record_ref_set is required",
                "source_record_ref_set",
            )
        )
    if not envelope.source_authority_sha256_set:
        issues.append(
            P6ProjectionIssue(
                P6ProjectionIssueKind.MISSING_SOURCE_HASH,
                P6ProjectionIssueSeverity.FAULT,
                "source_authority_sha256_set is required",
                "source_authority_sha256_set",
            )
        )
    if not envelope.lineage_edge_set:
        issues.append(
            P6ProjectionIssue(
                P6ProjectionIssueKind.MISSING_LINEAGE,
                P6ProjectionIssueSeverity.FAULT,
                "lineage_edge_set is required",
                "lineage_edge_set",
            )
        )
    if not envelope.authority_notice_ref:
        issues.append(
            P6ProjectionIssue(
                P6ProjectionIssueKind.MISSING_AUTHORITY_NOTICE,
                P6ProjectionIssueSeverity.FAULT,
                "authority_notice_ref is required",
                "authority_notice_ref",
            )
        )
    if not envelope.nonpromotion_notice_set:
        issues.append(
            P6ProjectionIssue(
                P6ProjectionIssueKind.MISSING_NONPROMOTION_NOTICE,
                P6ProjectionIssueSeverity.FAULT,
                "nonpromotion_notice_set is required",
                "nonpromotion_notice_set",
            )
        )
    if not envelope.forbidden_action_set:
        issues.append(
            P6ProjectionIssue(
                P6ProjectionIssueKind.MISSING_FORBIDDEN_ACTION,
                P6ProjectionIssueSeverity.BLOCKED,
                "forbidden_action_set must be visible before action",
                "forbidden_action_set",
            )
        )
    if not envelope.required_route_set:
        issues.append(
            P6ProjectionIssue(
                P6ProjectionIssueKind.MISSING_REQUIRED_ROUTE,
                P6ProjectionIssueSeverity.BLOCKED,
                "required_route_set must be visible before action",
                "required_route_set",
            )
        )

    if envelope.is_ready and envelope.has_stop_state:
        issues.append(
            P6ProjectionIssue(
                P6ProjectionIssueKind.READY_WITH_STOP_STATE,
                _severity_for_status(envelope.projected_status, envelope.freshness_state),
                "ready projection cannot carry stop-state evidence",
                "projected_status",
            )
        )
    if envelope.is_ready and envelope.freshness_state != P6FreshnessState.FRESH:
        issues.append(
            P6ProjectionIssue(
                P6ProjectionIssueKind.READY_WITH_UNFRESH_STATE,
                _severity_for_freshness(envelope.freshness_state),
                "ready projection requires fresh freshness state",
                "freshness_state",
            )
        )
    if _lower_tier_promoted(envelope):
        issues.append(
            P6ProjectionIssue(
                P6ProjectionIssueKind.LOWER_TIER_PROMOTED,
                P6ProjectionIssueSeverity.FAULT,
                "lower authority tier may not be presented as source authority",
                "authority_tier",
            )
        )
    if envelope.source_authority_mutation_requested:
        issues.append(_refusal_issue(P6ProjectionIssueKind.DIRECT_MUTATION_REQUESTED, "source authority mutation"))
    if envelope.assignment_requested:
        issues.append(_refusal_issue(P6ProjectionIssueKind.ASSIGNMENT_REQUESTED, "assignment"))
    if envelope.dispatch_requested:
        issues.append(_refusal_issue(P6ProjectionIssueKind.DISPATCH_REQUESTED, "dispatch"))
    if envelope.operations_control_requested:
        issues.append(_refusal_issue(P6ProjectionIssueKind.OPERATIONS_CONTROL_REQUESTED, "operations control"))
    if envelope.live_control_requested:
        issues.append(_refusal_issue(P6ProjectionIssueKind.LIVE_CONTROL_REQUESTED, "live machine control"))

    return P6ProjectionValidationResult(not issues, tuple(issues))


def status_for_p6_evidence(
    *,
    stop_state_ref_set: Iterable[str] = (),
    invalidation_ref_set: Iterable[str] = (),
    issue_set: Iterable[P6ProjectionIssue] = (),
) -> P6ProjectionStatus:
    """Classify a projection status from visible evidence."""

    issues = tuple(issue_set)
    if any(issue.severity == P6ProjectionIssueSeverity.FAULT for issue in issues):
        return P6ProjectionStatus.FAULTED
    if any(issue.severity == P6ProjectionIssueSeverity.REFUSED for issue in issues):
        return P6ProjectionStatus.REFUSED
    if any(issue.severity == P6ProjectionIssueSeverity.INTERRUPT for issue in issues):
        return P6ProjectionStatus.INTERRUPTED
    if any(issue.severity == P6ProjectionIssueSeverity.STALE for issue in issues) or tuple(invalidation_ref_set):
        return P6ProjectionStatus.STALE
    if any(issue.severity == P6ProjectionIssueSeverity.BLOCKED for issue in issues) or tuple(stop_state_ref_set):
        return P6ProjectionStatus.BLOCKED
    return P6ProjectionStatus.READY


def p6_projection_fact_set(envelope: P6ProjectionEnvelope) -> frozenset[str]:
    """Return reviewable facts for fixture comparison and future proof ledgers."""

    validation = validate_p6_projection_envelope(envelope)
    facts = {
        f"projection_kind is {envelope.projection_kind}",
        f"surface_family is {envelope.surface_family.value}",
        f"authority_tier is {envelope.authority_tier.value}",
        f"freshness_state is {envelope.freshness_state.value}",
        f"projected_status is {envelope.projected_status.value}",
        f"authority_validation is {_bool_text(validation.accepted)}",
        f"authority_safe is {_bool_text(envelope.authority_safe)}",
        f"visible_before_action is {_bool_text(envelope.visible_before_action)}",
        f"source_authority_mutation_requested is {_bool_text(envelope.source_authority_mutation_requested)}",
        f"assignment_requested is {_bool_text(envelope.assignment_requested)}",
        f"dispatch_requested is {_bool_text(envelope.dispatch_requested)}",
        f"operations_control_requested is {_bool_text(envelope.operations_control_requested)}",
        f"live_control_requested is {_bool_text(envelope.live_control_requested)}",
        f"nonpromotion_notice is {NON_AUTHORITY_WARNING}",
        f"no_assignment_notice is {envelope.no_assignment_notice}",
        f"no_dispatch_notice is {envelope.no_dispatch_notice}",
        f"no_operations_control_notice is {envelope.no_operations_control_notice}",
        f"no_live_effect_notice is {envelope.no_live_effect_notice}",
    }
    for issue in validation.issues:
        facts.add(f"issue_kind is {issue.issue_kind.value}")
        facts.add(f"issue_severity is {issue.severity.value}")
    return frozenset(facts)


def _missing_field_issue(field_name: str) -> P6ProjectionIssue:
    return P6ProjectionIssue(
        P6ProjectionIssueKind.MISSING_FIELD,
        P6ProjectionIssueSeverity.FAULT,
        f"{field_name} is required",
        field_name,
    )


def _refusal_issue(issue_kind: P6ProjectionIssueKind, effect_name: str) -> P6ProjectionIssue:
    return P6ProjectionIssue(
        issue_kind,
        P6ProjectionIssueSeverity.REFUSED,
        f"{effect_name} is not authorized by P6 surface projection",
    )


def _field_has_value(envelope: P6ProjectionEnvelope, field_name: str) -> bool:
    value = getattr(envelope, field_name)
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value)
    if isinstance(value, tuple):
        return True
    return True


def _lower_tier_promoted(envelope: P6ProjectionEnvelope) -> bool:
    if envelope.lower_authority_tier_claimed_as_source and envelope.authority_tier in LOWER_AUTHORITY_TIER_SET:
        return True
    text = " ".join(
        (
            envelope.risk_reason,
            envelope.mutation_boundary_ref,
            *envelope.permitted_action_set,
            *envelope.nonpromotion_notice_set,
        )
    ).lower()
    return envelope.authority_tier in LOWER_AUTHORITY_TIER_SET and (
        "source_authority" in text or "source authority" in text
    )


def _severity_for_status(
    status: P6ProjectionStatus,
    freshness_state: P6FreshnessState,
) -> P6ProjectionIssueSeverity:
    if status == P6ProjectionStatus.FAULTED or freshness_state == P6FreshnessState.FAULTED:
        return P6ProjectionIssueSeverity.FAULT
    if status == P6ProjectionStatus.INTERRUPTED or freshness_state == P6FreshnessState.INTERRUPTED:
        return P6ProjectionIssueSeverity.INTERRUPT
    if status == P6ProjectionStatus.STALE or freshness_state == P6FreshnessState.STALE:
        return P6ProjectionIssueSeverity.STALE
    if status == P6ProjectionStatus.REFUSED:
        return P6ProjectionIssueSeverity.REFUSED
    return P6ProjectionIssueSeverity.BLOCKED


def _severity_for_freshness(freshness_state: P6FreshnessState) -> P6ProjectionIssueSeverity:
    if freshness_state == P6FreshnessState.FAULTED:
        return P6ProjectionIssueSeverity.FAULT
    if freshness_state == P6FreshnessState.INTERRUPTED:
        return P6ProjectionIssueSeverity.INTERRUPT
    if freshness_state == P6FreshnessState.STALE:
        return P6ProjectionIssueSeverity.STALE
    return P6ProjectionIssueSeverity.BLOCKED


def _freshness_value(value: object) -> str:
    text = str(value)
    return {
        "accepted": P6FreshnessState.FRESH.value,
        "current": P6FreshnessState.FRESH.value,
        "present": P6FreshnessState.FRESH.value,
    }.get(text, text)


def _projection_status_value(value: object) -> str:
    text = str(value)
    return {
        "visible_authority_notice": P6ProjectionStatus.READY.value,
        "visible_stale_notice": P6ProjectionStatus.STALE.value,
        "generated_projection_non_authority": P6ProjectionStatus.READY.value,
        "surface_cannot_mutate_source_authority": P6ProjectionStatus.REFUSED.value,
    }.get(text, text)


def _as_string_sequence(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,) if value else ()
    return tuple(str(item) for item in value)  # type: ignore[operator]


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1"}
    return bool(value)


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


__all__ = (
    "DEFAULT_MUTATION_BOUNDARY_REF",
    "NO_ASSIGNMENT_NOTICE",
    "NO_DISPATCH_NOTICE",
    "NO_LIVE_EFFECT_NOTICE",
    "NO_OPERATIONS_CONTROL_NOTICE",
    "NON_AUTHORITY_WARNING",
    "LOWER_AUTHORITY_TIER_SET",
    "REQUIRED_P6_PROJECTION_FIELD_SET",
    "STOP_STATE_STATUS_SET",
    "P6AuthorityTier",
    "P6FreshnessState",
    "P6ProjectionEnvelope",
    "P6ProjectionIssue",
    "P6ProjectionIssueKind",
    "P6ProjectionIssueSeverity",
    "P6ProjectionStatus",
    "P6ProjectionValidationResult",
    "P6SurfaceFamily",
    "p6_projection_envelope_from_mapping",
    "p6_projection_envelope_from_parts",
    "p6_projection_fact_set",
    "status_for_p6_evidence",
    "validate_p6_projection_envelope",
)
