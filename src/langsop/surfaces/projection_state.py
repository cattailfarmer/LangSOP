"""Projection state envelope models for IR5 surface projections.

Projection state is display and coordination context only. It cannot create,
accept, mutate, or replace source authority.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable


class ProjectionStatus(str, Enum):
    """Accepted projected status values from the IR5 contract."""

    READY = "ready"
    BLOCKED = "blocked"
    STALE = "stale"
    FAULTED = "faulted"
    INTERRUPTED = "interrupted"
    CONTESTED = "contested"
    PENDING_REVIEW = "pending_review"
    UNSUPPORTED_SCOPE = "unsupported_scope"
    REFUSED = "refused"


class FreshnessState(str, Enum):
    """Accepted freshness states from the IR5 freshness contract."""

    FRESH = "fresh"
    STALE = "stale"
    UNKNOWN = "unknown"
    CONTESTED = "contested"
    INTERRUPTED = "interrupted"
    BLOCKED = "blocked"
    FAULTED = "faulted"
    PENDING_REVIEW = "pending_review"


class ProjectionStateIssueKind(str, Enum):
    """Issue vocabulary for projection state validation."""

    MISSING_FIELD = "missing_field"
    MISSING_SOURCE_REF = "missing_source_ref_set"
    MISSING_LINEAGE = "missing_lineage_edge_set"
    MISSING_AUTHORITY_NOTICE = "missing_authority_notice"
    READY_WITH_STOP_STATE = "ready_with_stop_state"
    READY_WITH_UNFRESH_STATE = "ready_with_unfresh_state"
    GENERATED_AUTHORITY = "generated_authority"
    SOURCE_MUTATION_REQUESTED = "source_authority_mutation_requested"


class ProjectionStateIssueSeverity(str, Enum):
    """How a future surface projector should treat a state issue."""

    BLOCKED = "blocked"
    STALE = "stale"
    FAULT = "fault"
    INTERRUPT = "interrupt"
    REFUSED = "refused"


REQUIRED_PROJECTION_STATE_FIELD_SET: tuple[str, ...] = (
    "projection_id",
    "projection_kind",
    "projected_subject_ref",
    "source_record_ref_set",
    "lineage_edge_set",
    "generated_at",
    "projected_status",
    "freshness_state",
    "invalidation_ref_set",
    "blocker_ref_set",
    "stale_source_ref_set",
    "fault_record_ref_set",
    "interrupt_context_ref_set",
    "contested_claim_ref_set",
    "pending_review_ref_set",
    "supported_action_route_set",
    "refusal_reason_set",
)

STOP_STATE_STATUS_SET: frozenset[ProjectionStatus] = frozenset(
    {
        ProjectionStatus.BLOCKED,
        ProjectionStatus.STALE,
        ProjectionStatus.FAULTED,
        ProjectionStatus.INTERRUPTED,
        ProjectionStatus.CONTESTED,
        ProjectionStatus.PENDING_REVIEW,
        ProjectionStatus.UNSUPPORTED_SCOPE,
        ProjectionStatus.REFUSED,
    }
)


@dataclass(frozen=True)
class ProjectionStateIssue:
    """One blocked, stale, fault, interrupt, or refusal reason."""

    issue_kind: ProjectionStateIssueKind
    severity: ProjectionStateIssueSeverity
    reason: str
    field_name: str | None = None


@dataclass(frozen=True)
class ProjectionStateValidationResult:
    """Pure validation result for a projection state envelope."""

    accepted: bool
    issues: tuple[ProjectionStateIssue, ...] = ()

    @property
    def has_fault(self) -> bool:
        return any(issue.severity == ProjectionStateIssueSeverity.FAULT for issue in self.issues)

    @property
    def has_interrupt(self) -> bool:
        return any(issue.severity == ProjectionStateIssueSeverity.INTERRUPT for issue in self.issues)

    @property
    def has_stale(self) -> bool:
        return any(issue.severity == ProjectionStateIssueSeverity.STALE for issue in self.issues)

    @property
    def has_blocker(self) -> bool:
        return any(issue.severity == ProjectionStateIssueSeverity.BLOCKED for issue in self.issues)

    @property
    def has_refusal(self) -> bool:
        return any(issue.severity == ProjectionStateIssueSeverity.REFUSED for issue in self.issues)


@dataclass(frozen=True)
class StopStateContext:
    """Visible evidence for a stopped projection state."""

    stop_state_kind: ProjectionStatus
    stop_state_ref_set: tuple[str, ...]
    evidence_ref_set: tuple[str, ...]
    required_resolution: str
    allowed_reconsideration_route_set: tuple[str, ...]
    forbidden_action_set: tuple[str, ...]


@dataclass(frozen=True)
class ProjectionRefusalRecord:
    """Projection-only record for a refused or faulty projection."""

    refusal_reason: str
    evidence_ref_set: tuple[str, ...]
    required_resolution: str
    authority_notice_ref: str


@dataclass(frozen=True)
class ProjectionStateEnvelope:
    """State and stop-context metadata for one projected surface record."""

    projection_id: str
    projection_kind: str
    projected_subject_ref: str
    source_record_ref_set: tuple[str, ...]
    lineage_edge_set: tuple[str, ...]
    generated_at: str
    projected_status: ProjectionStatus
    freshness_state: FreshnessState
    invalidation_ref_set: tuple[str, ...] = ()
    blocker_ref_set: tuple[str, ...] = ()
    stale_source_ref_set: tuple[str, ...] = ()
    fault_record_ref_set: tuple[str, ...] = ()
    interrupt_context_ref_set: tuple[str, ...] = ()
    contested_claim_ref_set: tuple[str, ...] = ()
    pending_review_ref_set: tuple[str, ...] = ()
    supported_action_route_set: tuple[str, ...] = ()
    refusal_reason_set: tuple[str, ...] = ()
    authority_notice_ref: str = ""
    stop_state_context_set: tuple[StopStateContext, ...] = ()
    generated_projection_claimed_as_authority: bool = False
    source_authority_mutation_requested: bool = False

    @property
    def stop_evidence_present(self) -> bool:
        return any(
            (
                self.invalidation_ref_set,
                self.blocker_ref_set,
                self.stale_source_ref_set,
                self.fault_record_ref_set,
                self.interrupt_context_ref_set,
                self.contested_claim_ref_set,
                self.pending_review_ref_set,
                self.refusal_reason_set,
                self.stop_state_context_set,
            )
        )

    @property
    def is_ready(self) -> bool:
        return self.projected_status == ProjectionStatus.READY


def projection_state_envelope_from_parts(
    *,
    projection_id: str,
    projection_kind: str,
    projected_subject_ref: str,
    source_record_ref_set: Iterable[str],
    lineage_edge_set: Iterable[str],
    generated_at: str,
    projected_status: str | ProjectionStatus,
    freshness_state: str | FreshnessState,
    invalidation_ref_set: Iterable[str] = (),
    blocker_ref_set: Iterable[str] = (),
    stale_source_ref_set: Iterable[str] = (),
    fault_record_ref_set: Iterable[str] = (),
    interrupt_context_ref_set: Iterable[str] = (),
    contested_claim_ref_set: Iterable[str] = (),
    pending_review_ref_set: Iterable[str] = (),
    supported_action_route_set: Iterable[str] = (),
    refusal_reason_set: Iterable[str] = (),
    authority_notice_ref: str = "",
    stop_state_context_set: Iterable[StopStateContext] = (),
    generated_projection_claimed_as_authority: bool = False,
    source_authority_mutation_requested: bool = False,
) -> ProjectionStateEnvelope:
    """Build a projection state envelope while normalizing enums and sets."""

    return ProjectionStateEnvelope(
        projection_id=projection_id,
        projection_kind=projection_kind,
        projected_subject_ref=projected_subject_ref,
        source_record_ref_set=tuple(source_record_ref_set),
        lineage_edge_set=tuple(lineage_edge_set),
        generated_at=generated_at,
        projected_status=ProjectionStatus(projected_status),
        freshness_state=FreshnessState(freshness_state),
        invalidation_ref_set=tuple(invalidation_ref_set),
        blocker_ref_set=tuple(blocker_ref_set),
        stale_source_ref_set=tuple(stale_source_ref_set),
        fault_record_ref_set=tuple(fault_record_ref_set),
        interrupt_context_ref_set=tuple(interrupt_context_ref_set),
        contested_claim_ref_set=tuple(contested_claim_ref_set),
        pending_review_ref_set=tuple(pending_review_ref_set),
        supported_action_route_set=tuple(supported_action_route_set),
        refusal_reason_set=tuple(refusal_reason_set),
        authority_notice_ref=authority_notice_ref,
        stop_state_context_set=tuple(stop_state_context_set),
        generated_projection_claimed_as_authority=generated_projection_claimed_as_authority,
        source_authority_mutation_requested=source_authority_mutation_requested,
    )


def validate_projection_state_envelope(
    envelope: ProjectionStateEnvelope,
) -> ProjectionStateValidationResult:
    """Validate projection state against IR5 stop-state and freshness rules."""

    issues: list[ProjectionStateIssue] = []

    for field_name in REQUIRED_PROJECTION_STATE_FIELD_SET:
        if not _field_has_value(envelope, field_name):
            issues.append(
                ProjectionStateIssue(
                    ProjectionStateIssueKind.MISSING_FIELD,
                    ProjectionStateIssueSeverity.FAULT,
                    f"{field_name} is required",
                    field_name,
                )
            )

    if not envelope.source_record_ref_set:
        issues.append(
            ProjectionStateIssue(
                ProjectionStateIssueKind.MISSING_SOURCE_REF,
                ProjectionStateIssueSeverity.FAULT,
                "source record refs are required",
                "source_record_ref_set",
            )
        )

    if not envelope.lineage_edge_set:
        issues.append(
            ProjectionStateIssue(
                ProjectionStateIssueKind.MISSING_LINEAGE,
                ProjectionStateIssueSeverity.FAULT,
                "lineage edge refs are required",
                "lineage_edge_set",
            )
        )

    if not envelope.authority_notice_ref:
        issues.append(
            ProjectionStateIssue(
                ProjectionStateIssueKind.MISSING_AUTHORITY_NOTICE,
                ProjectionStateIssueSeverity.FAULT,
                "authority notice ref is required for decision-facing projection state",
                "authority_notice_ref",
            )
        )

    if envelope.is_ready and envelope.stop_evidence_present:
        issues.append(
            ProjectionStateIssue(
                ProjectionStateIssueKind.READY_WITH_STOP_STATE,
                _severity_for_stop_evidence(envelope),
                "ready projection cannot carry blocked, stale, fault, interrupt, pending, contested, or refusal evidence",
                "projected_status",
            )
        )

    if envelope.is_ready and envelope.freshness_state != FreshnessState.FRESH:
        issues.append(
            ProjectionStateIssue(
                ProjectionStateIssueKind.READY_WITH_UNFRESH_STATE,
                _severity_for_freshness(envelope.freshness_state),
                "ready projection requires fresh freshness state",
                "freshness_state",
            )
        )

    if envelope.generated_projection_claimed_as_authority:
        issues.append(
            ProjectionStateIssue(
                ProjectionStateIssueKind.GENERATED_AUTHORITY,
                ProjectionStateIssueSeverity.FAULT,
                "generated projection may not be treated as source authority",
                "generated_projection_claimed_as_authority",
            )
        )

    if envelope.source_authority_mutation_requested:
        issues.append(
            ProjectionStateIssue(
                ProjectionStateIssueKind.SOURCE_MUTATION_REQUESTED,
                ProjectionStateIssueSeverity.REFUSED,
                "projection state may not request source authority mutation",
                "source_authority_mutation_requested",
            )
        )

    return ProjectionStateValidationResult(not issues, tuple(issues))


def projected_status_for_evidence(
    *,
    blocker_ref_set: Iterable[str] = (),
    stale_source_ref_set: Iterable[str] = (),
    fault_record_ref_set: Iterable[str] = (),
    interrupt_context_ref_set: Iterable[str] = (),
    contested_claim_ref_set: Iterable[str] = (),
    pending_review_ref_set: Iterable[str] = (),
    refusal_reason_set: Iterable[str] = (),
) -> ProjectionStatus:
    """Classify a projected status using the IR5 stop-state priority."""

    if tuple(fault_record_ref_set):
        return ProjectionStatus.FAULTED
    if tuple(interrupt_context_ref_set):
        return ProjectionStatus.INTERRUPTED
    if tuple(stale_source_ref_set):
        return ProjectionStatus.STALE
    if tuple(refusal_reason_set):
        return ProjectionStatus.REFUSED
    if tuple(blocker_ref_set):
        return ProjectionStatus.BLOCKED
    if tuple(contested_claim_ref_set):
        return ProjectionStatus.CONTESTED
    if tuple(pending_review_ref_set):
        return ProjectionStatus.PENDING_REVIEW
    return ProjectionStatus.READY


def _field_has_value(envelope: ProjectionStateEnvelope, field_name: str) -> bool:
    value = getattr(envelope, field_name)
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value)
    if isinstance(value, tuple):
        return True
    return True


def _severity_for_stop_evidence(envelope: ProjectionStateEnvelope) -> ProjectionStateIssueSeverity:
    if envelope.fault_record_ref_set:
        return ProjectionStateIssueSeverity.FAULT
    if envelope.interrupt_context_ref_set:
        return ProjectionStateIssueSeverity.INTERRUPT
    if envelope.stale_source_ref_set or envelope.invalidation_ref_set:
        return ProjectionStateIssueSeverity.STALE
    if envelope.refusal_reason_set:
        return ProjectionStateIssueSeverity.REFUSED
    return ProjectionStateIssueSeverity.BLOCKED


def _severity_for_freshness(freshness_state: FreshnessState) -> ProjectionStateIssueSeverity:
    if freshness_state == FreshnessState.FAULTED:
        return ProjectionStateIssueSeverity.FAULT
    if freshness_state == FreshnessState.INTERRUPTED:
        return ProjectionStateIssueSeverity.INTERRUPT
    if freshness_state == FreshnessState.STALE:
        return ProjectionStateIssueSeverity.STALE
    return ProjectionStateIssueSeverity.BLOCKED
