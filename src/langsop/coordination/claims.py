"""Claim identity and work-boundary models for IR6 coordination projections.

These helpers model projection records only. They do not read or write mailbox
files, mutate source authority, dispatch agents, or control operations.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class ClaimFreshnessState(str, Enum):
    """Accepted freshness states for claim and work-boundary projection."""

    FRESH = "fresh"
    STALE = "stale"
    UNKNOWN = "unknown"
    CONTESTED = "contested"
    INTERRUPTED = "interrupted"
    BLOCKED = "blocked"
    FAULTED = "faulted"
    PENDING_REVIEW = "pending_review"


class ClaimProjectionStatus(str, Enum):
    """Claim projection states from the IR6 fixture ledgers."""

    ACCEPTED = "accepted"
    BLOCKED = "blocked"
    CONTESTED = "contested"
    STALE = "stale"
    INTERRUPTED = "interrupted"
    FAULTED = "faulted"
    PENDING_REVIEW = "pending_review"
    REFUSED = "refused"


class ClaimCompatibilityRelation(str, Enum):
    """Compatibility relation between two projected claims."""

    SAME_CLAIM = "same_claim"
    NON_OVERLAPPING_WRITE_SCOPE = "non_overlapping_write_scope"
    READ_ONLY_OVERLAP = "read_only_overlap"
    OVERLAPPING_WRITE_SCOPE = "overlapping_write_scope"
    IDENTICAL_WRITE_SCOPE = "identical_write_scope"
    AMBIGUOUS_SCOPE_RELATION = "ambiguous_scope_relation"


class WorkBoundaryStatus(str, Enum):
    """Projected work-boundary readiness state."""

    DEPENDENCY_CLOSED = "dependency_closed"
    COMPATIBLE_PARALLEL = "compatible_parallel"
    BLOCKED = "blocked"
    STALE = "stale"
    CONTESTED = "contested"
    INTERRUPTED = "interrupted"
    FAULTED = "faulted"
    PENDING_REVIEW = "pending_review"
    REFUSED = "refused"


class ClaimIssueKind(str, Enum):
    """Issue vocabulary for claim and work-boundary validation."""

    MISSING_FIELD = "missing_field"
    MISSING_AUTHORITY_BASIS = "missing_authority_basis"
    MISSING_AUTHORITY_NOTICE = "missing_authority_notice"
    MISSING_FORBIDDEN_ACTION = "missing_forbidden_action_set"
    READY_WITH_STOP_EVIDENCE = "ready_with_stop_evidence"
    READY_WITH_UNFRESH_STATE = "ready_with_unfresh_state"
    IDENTITY_COLLAPSE = "identity_collapse"
    GENERATED_AUTHORITY = "generated_authority"
    SOURCE_MUTATION_REQUESTED = "source_authority_mutation_requested"
    MAILBOX_IO_REQUESTED = "mailbox_io_requested"
    DISPATCH_REQUESTED = "agent_dispatch_requested"
    LIVE_CONTROL_REQUESTED = "live_machine_control_requested"


class ClaimIssueSeverity(str, Enum):
    """How a future projector should treat a claim issue."""

    BLOCKED = "blocked"
    STALE = "stale"
    FAULT = "fault"
    INTERRUPT = "interrupt"
    REFUSED = "refused"


REQUIRED_CLAIM_IDENTITY_FIELD_SET: tuple[str, ...] = (
    "claim_id",
    "claimant_ref",
    "conversation_ref",
    "work_packet_ref",
    "scope_subject_ref_set",
    "authority_basis_ref_set",
    "authority_notice_ref",
    "freshness_state",
    "permitted_action_set",
    "forbidden_action_set",
    "trust_limit",
)

REQUIRED_WORK_BOUNDARY_FIELD_SET: tuple[str, ...] = (
    "projection_id",
    "claim_ref",
    "scope_subject_ref_set",
    "authority_basis_ref_set",
    "authority_notice_ref",
    "freshness_state",
    "boundary_status",
    "compatibility_relation",
    "required_route_set",
    "forbidden_action_set",
)

DIRECT_SOURCE_MUTATION_ACTION_SET: frozenset[str] = frozenset(
    {
        "direct_source_authority_write",
        "direct_source_write",
        "source_authority_mutation",
        "source_mutation",
        "direct_completion_acceptance",
        "completion_acceptance",
        "direct_claim_acceptance",
        "claim_state_transition",
    }
)

MAILBOX_IO_ACTION_SET: frozenset[str] = frozenset(
    {
        "mailbox_file_read",
        "mailbox_file_write",
        "mailbox_file_create",
        "platform_mailbox_mutation",
        "read_cursor_persist",
        "watch_mailbox_directory",
    }
)

DISPATCH_ACTION_SET: frozenset[str] = frozenset(
    {
        "agent_dispatch",
        "direct_agent_dispatch",
        "assign_agent",
        "start_agent",
        "dispatch_work",
    }
)

LIVE_CONTROL_ACTION_SET: frozenset[str] = frozenset(
    {
        "operations_control",
        "live_machine_control",
        "process_control",
        "gpu_control",
        "model_runtime_control",
    }
)

STOP_BOUNDARY_STATUS_SET: frozenset[WorkBoundaryStatus] = frozenset(
    {
        WorkBoundaryStatus.BLOCKED,
        WorkBoundaryStatus.STALE,
        WorkBoundaryStatus.CONTESTED,
        WorkBoundaryStatus.INTERRUPTED,
        WorkBoundaryStatus.FAULTED,
        WorkBoundaryStatus.PENDING_REVIEW,
        WorkBoundaryStatus.REFUSED,
    }
)


@dataclass(frozen=True)
class ClaimValidationIssue:
    """One blocked, stale, fault, interrupt, or refusal reason."""

    issue_kind: ClaimIssueKind
    severity: ClaimIssueSeverity
    reason: str
    field_name: str | None = None


@dataclass(frozen=True)
class ClaimValidationResult:
    """Pure validation result for claim and work-boundary records."""

    accepted: bool
    issues: tuple[ClaimValidationIssue, ...] = ()

    @property
    def has_fault(self) -> bool:
        return any(issue.severity == ClaimIssueSeverity.FAULT for issue in self.issues)

    @property
    def has_blocker(self) -> bool:
        return any(issue.severity == ClaimIssueSeverity.BLOCKED for issue in self.issues)

    @property
    def has_stale(self) -> bool:
        return any(issue.severity == ClaimIssueSeverity.STALE for issue in self.issues)

    @property
    def has_interrupt(self) -> bool:
        return any(issue.severity == ClaimIssueSeverity.INTERRUPT for issue in self.issues)

    @property
    def has_refusal(self) -> bool:
        return any(issue.severity == ClaimIssueSeverity.REFUSED for issue in self.issues)


@dataclass(frozen=True)
class ClaimIdentityEnvelope:
    """Identity and authority envelope for one projected coordination claim."""

    claim_id: str
    claimant_ref: str
    conversation_ref: str
    work_packet_ref: str
    scope_subject_ref_set: tuple[str, ...]
    authority_basis_ref_set: tuple[str, ...]
    authority_notice_ref: str
    freshness_state: ClaimFreshnessState
    permitted_action_set: tuple[str, ...]
    forbidden_action_set: tuple[str, ...]
    trust_limit: str
    claim_status: ClaimProjectionStatus = ClaimProjectionStatus.ACCEPTED
    compatibility_evidence_ref_set: tuple[str, ...] = ()
    unresolved_review_ref_set: tuple[str, ...] = ()
    generated_projection_claimed_as_authority: bool = False
    identity_collapse_detected: bool = False


@dataclass(frozen=True)
class WorkBoundaryProjectionEnvelope:
    """Projected readiness boundary for one claim over a work scope."""

    projection_id: str
    claim_ref: str
    scope_subject_ref_set: tuple[str, ...]
    authority_basis_ref_set: tuple[str, ...]
    authority_notice_ref: str
    freshness_state: ClaimFreshnessState
    boundary_status: WorkBoundaryStatus
    compatibility_relation: ClaimCompatibilityRelation
    required_route_set: tuple[str, ...]
    forbidden_action_set: tuple[str, ...]
    blocker_ref_set: tuple[str, ...] = ()
    stale_trigger_ref_set: tuple[str, ...] = ()
    contested_claim_ref_set: tuple[str, ...] = ()
    ambiguous_identity_ref_set: tuple[str, ...] = ()
    pending_review_ref_set: tuple[str, ...] = ()
    fault_ref_set: tuple[str, ...] = ()
    refusal_reason_set: tuple[str, ...] = ()
    generated_projection_claimed_as_authority: bool = False
    source_authority_mutation_requested: bool = False

    @property
    def is_dependency_closed(self) -> bool:
        return self.boundary_status == WorkBoundaryStatus.DEPENDENCY_CLOSED

    @property
    def stop_evidence_present(self) -> bool:
        return any(
            (
                self.blocker_ref_set,
                self.stale_trigger_ref_set,
                self.contested_claim_ref_set,
                self.ambiguous_identity_ref_set,
                self.pending_review_ref_set,
                self.fault_ref_set,
                self.refusal_reason_set,
            )
        )


@dataclass(frozen=True)
class ClaimCompatibilityResult:
    """Compatibility classification for two projected claim envelopes."""

    relation: ClaimCompatibilityRelation
    compatible: bool
    reason: str
    involved_claim_ref_set: tuple[str, ...]


def claim_identity_envelope_from_parts(
    *,
    claim_id: str,
    claimant_ref: str,
    conversation_ref: str,
    work_packet_ref: str,
    scope_subject_ref_set: Iterable[str],
    authority_basis_ref_set: Iterable[str],
    authority_notice_ref: str,
    freshness_state: str | ClaimFreshnessState,
    permitted_action_set: Iterable[str],
    forbidden_action_set: Iterable[str],
    trust_limit: str,
    claim_status: str | ClaimProjectionStatus = ClaimProjectionStatus.ACCEPTED,
    compatibility_evidence_ref_set: Iterable[str] = (),
    unresolved_review_ref_set: Iterable[str] = (),
    generated_projection_claimed_as_authority: bool = False,
    identity_collapse_detected: bool = False,
) -> ClaimIdentityEnvelope:
    """Build a claim identity envelope while normalizing iterables and enums."""

    return ClaimIdentityEnvelope(
        claim_id=claim_id,
        claimant_ref=claimant_ref,
        conversation_ref=conversation_ref,
        work_packet_ref=work_packet_ref,
        scope_subject_ref_set=tuple(scope_subject_ref_set),
        authority_basis_ref_set=tuple(authority_basis_ref_set),
        authority_notice_ref=authority_notice_ref,
        freshness_state=ClaimFreshnessState(freshness_state),
        permitted_action_set=tuple(permitted_action_set),
        forbidden_action_set=tuple(forbidden_action_set),
        trust_limit=trust_limit,
        claim_status=ClaimProjectionStatus(claim_status),
        compatibility_evidence_ref_set=tuple(compatibility_evidence_ref_set),
        unresolved_review_ref_set=tuple(unresolved_review_ref_set),
        generated_projection_claimed_as_authority=generated_projection_claimed_as_authority,
        identity_collapse_detected=identity_collapse_detected,
    )


def work_boundary_projection_envelope_from_parts(
    *,
    projection_id: str,
    claim_ref: str,
    scope_subject_ref_set: Iterable[str],
    authority_basis_ref_set: Iterable[str],
    authority_notice_ref: str,
    freshness_state: str | ClaimFreshnessState,
    boundary_status: str | WorkBoundaryStatus,
    compatibility_relation: str | ClaimCompatibilityRelation,
    required_route_set: Iterable[str],
    forbidden_action_set: Iterable[str],
    blocker_ref_set: Iterable[str] = (),
    stale_trigger_ref_set: Iterable[str] = (),
    contested_claim_ref_set: Iterable[str] = (),
    ambiguous_identity_ref_set: Iterable[str] = (),
    pending_review_ref_set: Iterable[str] = (),
    fault_ref_set: Iterable[str] = (),
    refusal_reason_set: Iterable[str] = (),
    generated_projection_claimed_as_authority: bool = False,
    source_authority_mutation_requested: bool = False,
) -> WorkBoundaryProjectionEnvelope:
    """Build a work-boundary envelope while normalizing iterables and enums."""

    return WorkBoundaryProjectionEnvelope(
        projection_id=projection_id,
        claim_ref=claim_ref,
        scope_subject_ref_set=tuple(scope_subject_ref_set),
        authority_basis_ref_set=tuple(authority_basis_ref_set),
        authority_notice_ref=authority_notice_ref,
        freshness_state=ClaimFreshnessState(freshness_state),
        boundary_status=WorkBoundaryStatus(boundary_status),
        compatibility_relation=ClaimCompatibilityRelation(compatibility_relation),
        required_route_set=tuple(required_route_set),
        forbidden_action_set=tuple(forbidden_action_set),
        blocker_ref_set=tuple(blocker_ref_set),
        stale_trigger_ref_set=tuple(stale_trigger_ref_set),
        contested_claim_ref_set=tuple(contested_claim_ref_set),
        ambiguous_identity_ref_set=tuple(ambiguous_identity_ref_set),
        pending_review_ref_set=tuple(pending_review_ref_set),
        fault_ref_set=tuple(fault_ref_set),
        refusal_reason_set=tuple(refusal_reason_set),
        generated_projection_claimed_as_authority=generated_projection_claimed_as_authority,
        source_authority_mutation_requested=source_authority_mutation_requested,
    )


def validate_claim_identity_envelope(envelope: ClaimIdentityEnvelope) -> ClaimValidationResult:
    """Validate a claim identity envelope against the accepted IR6 contract."""

    issues: list[ClaimValidationIssue] = []

    for field_name in REQUIRED_CLAIM_IDENTITY_FIELD_SET:
        if not _field_has_value(envelope, field_name):
            issues.append(_missing_field_issue(field_name))

    if not envelope.authority_basis_ref_set:
        issues.append(
            ClaimValidationIssue(
                ClaimIssueKind.MISSING_AUTHORITY_BASIS,
                ClaimIssueSeverity.FAULT,
                "authority basis refs are required before claim projection use",
                "authority_basis_ref_set",
            )
        )

    if not envelope.authority_notice_ref:
        issues.append(
            ClaimValidationIssue(
                ClaimIssueKind.MISSING_AUTHORITY_NOTICE,
                ClaimIssueSeverity.FAULT,
                "authority notice ref is required before claim projection use",
                "authority_notice_ref",
            )
        )

    if not envelope.forbidden_action_set:
        issues.append(
            ClaimValidationIssue(
                ClaimIssueKind.MISSING_FORBIDDEN_ACTION,
                ClaimIssueSeverity.BLOCKED,
                "forbidden action set must be visible before claim action",
                "forbidden_action_set",
            )
        )

    if envelope.identity_collapse_detected or envelope.claimant_ref == envelope.conversation_ref:
        issues.append(
            ClaimValidationIssue(
                ClaimIssueKind.IDENTITY_COLLAPSE,
                ClaimIssueSeverity.INTERRUPT,
                "claimant identity and conversation identity must remain distinct",
                "claimant_ref",
            )
        )

    if envelope.generated_projection_claimed_as_authority:
        issues.append(
            ClaimValidationIssue(
                ClaimIssueKind.GENERATED_AUTHORITY,
                ClaimIssueSeverity.FAULT,
                "generated claim projection may not be treated as source authority",
                "generated_projection_claimed_as_authority",
            )
        )

    issues.extend(_forbidden_permitted_action_issues(envelope.permitted_action_set))
    return ClaimValidationResult(not issues, tuple(issues))


def validate_work_boundary_projection_envelope(
    envelope: WorkBoundaryProjectionEnvelope,
) -> ClaimValidationResult:
    """Validate a work-boundary projection against IR6 readiness rules."""

    issues: list[ClaimValidationIssue] = []

    for field_name in REQUIRED_WORK_BOUNDARY_FIELD_SET:
        if not _field_has_value(envelope, field_name):
            issues.append(_missing_field_issue(field_name))

    if not envelope.authority_basis_ref_set:
        issues.append(
            ClaimValidationIssue(
                ClaimIssueKind.MISSING_AUTHORITY_BASIS,
                ClaimIssueSeverity.FAULT,
                "authority basis refs are required before work-boundary use",
                "authority_basis_ref_set",
            )
        )

    if not envelope.authority_notice_ref:
        issues.append(
            ClaimValidationIssue(
                ClaimIssueKind.MISSING_AUTHORITY_NOTICE,
                ClaimIssueSeverity.FAULT,
                "authority notice ref is required before work-boundary use",
                "authority_notice_ref",
            )
        )

    if envelope.is_dependency_closed and envelope.stop_evidence_present:
        issues.append(
            ClaimValidationIssue(
                ClaimIssueKind.READY_WITH_STOP_EVIDENCE,
                _severity_for_boundary(envelope),
                "dependency-closed boundary cannot carry blocked, stale, contested, interrupt, fault, pending, or refusal evidence",
                "boundary_status",
            )
        )

    if envelope.is_dependency_closed and envelope.freshness_state != ClaimFreshnessState.FRESH:
        issues.append(
            ClaimValidationIssue(
                ClaimIssueKind.READY_WITH_UNFRESH_STATE,
                _severity_for_freshness(envelope.freshness_state),
                "dependency-closed boundary requires fresh freshness state",
                "freshness_state",
            )
        )

    if envelope.generated_projection_claimed_as_authority:
        issues.append(
            ClaimValidationIssue(
                ClaimIssueKind.GENERATED_AUTHORITY,
                ClaimIssueSeverity.FAULT,
                "generated work-boundary projection may not be treated as source authority",
                "generated_projection_claimed_as_authority",
            )
        )

    if envelope.source_authority_mutation_requested:
        issues.append(
            ClaimValidationIssue(
                ClaimIssueKind.SOURCE_MUTATION_REQUESTED,
                ClaimIssueSeverity.REFUSED,
                "work-boundary projection may not request source authority mutation",
                "source_authority_mutation_requested",
            )
        )

    issues.extend(_forbidden_permitted_action_issues(envelope.required_route_set))
    return ClaimValidationResult(not issues, tuple(issues))


def classify_claim_compatibility(
    claim_a: ClaimIdentityEnvelope,
    claim_b: ClaimIdentityEnvelope,
    *,
    claim_a_write_scope_set: Iterable[str] = (),
    claim_b_write_scope_set: Iterable[str] = (),
    claim_a_read_scope_set: Iterable[str] = (),
    claim_b_read_scope_set: Iterable[str] = (),
) -> ClaimCompatibilityResult:
    """Classify two claims without mutating claim state or resolving conflicts."""

    if claim_a.claim_id == claim_b.claim_id:
        return ClaimCompatibilityResult(
            ClaimCompatibilityRelation.SAME_CLAIM,
            True,
            "same claim id",
            (claim_a.claim_id, claim_b.claim_id),
        )

    write_a = set(claim_a_write_scope_set or claim_a.scope_subject_ref_set)
    write_b = set(claim_b_write_scope_set or claim_b.scope_subject_ref_set)
    read_a = set(claim_a_read_scope_set)
    read_b = set(claim_b_read_scope_set)

    if not write_a or not write_b:
        return ClaimCompatibilityResult(
            ClaimCompatibilityRelation.AMBIGUOUS_SCOPE_RELATION,
            False,
            "missing write scope prevents compatibility proof",
            (claim_a.claim_id, claim_b.claim_id),
        )

    if write_a == write_b:
        return ClaimCompatibilityResult(
            ClaimCompatibilityRelation.IDENTICAL_WRITE_SCOPE,
            False,
            "identical write scope requires conflict review",
            (claim_a.claim_id, claim_b.claim_id),
        )

    if write_a & write_b:
        return ClaimCompatibilityResult(
            ClaimCompatibilityRelation.OVERLAPPING_WRITE_SCOPE,
            False,
            "overlapping write scope requires conflict review",
            (claim_a.claim_id, claim_b.claim_id),
        )

    if (write_a & read_b) or (write_b & read_a):
        return ClaimCompatibilityResult(
            ClaimCompatibilityRelation.READ_ONLY_OVERLAP,
            True,
            "write scopes are distinct and only read overlap is present",
            (claim_a.claim_id, claim_b.claim_id),
        )

    return ClaimCompatibilityResult(
        ClaimCompatibilityRelation.NON_OVERLAPPING_WRITE_SCOPE,
        True,
        "write scopes are non-overlapping",
        (claim_a.claim_id, claim_b.claim_id),
    )


def boundary_status_for_claim_evidence(
    *,
    blocker_ref_set: Iterable[str] = (),
    stale_trigger_ref_set: Iterable[str] = (),
    contested_claim_ref_set: Iterable[str] = (),
    ambiguous_identity_ref_set: Iterable[str] = (),
    pending_review_ref_set: Iterable[str] = (),
    fault_ref_set: Iterable[str] = (),
    refusal_reason_set: Iterable[str] = (),
) -> WorkBoundaryStatus:
    """Classify work-boundary status using IR6 stop-state priority."""

    if tuple(fault_ref_set):
        return WorkBoundaryStatus.FAULTED
    if tuple(ambiguous_identity_ref_set):
        return WorkBoundaryStatus.INTERRUPTED
    if tuple(stale_trigger_ref_set):
        return WorkBoundaryStatus.STALE
    if tuple(refusal_reason_set):
        return WorkBoundaryStatus.REFUSED
    if tuple(blocker_ref_set):
        return WorkBoundaryStatus.BLOCKED
    if tuple(contested_claim_ref_set):
        return WorkBoundaryStatus.CONTESTED
    if tuple(pending_review_ref_set):
        return WorkBoundaryStatus.PENDING_REVIEW
    return WorkBoundaryStatus.DEPENDENCY_CLOSED


def _missing_field_issue(field_name: str) -> ClaimValidationIssue:
    return ClaimValidationIssue(
        ClaimIssueKind.MISSING_FIELD,
        ClaimIssueSeverity.FAULT,
        f"{field_name} is required",
        field_name,
    )


def _field_has_value(envelope: object, field_name: str) -> bool:
    value = getattr(envelope, field_name)
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value)
    if isinstance(value, tuple):
        return True
    return True


def _forbidden_permitted_action_issues(action_set: Iterable[str]) -> tuple[ClaimValidationIssue, ...]:
    actions = set(action_set)
    issues: list[ClaimValidationIssue] = []
    if actions & DIRECT_SOURCE_MUTATION_ACTION_SET:
        issues.append(
            ClaimValidationIssue(
                ClaimIssueKind.SOURCE_MUTATION_REQUESTED,
                ClaimIssueSeverity.REFUSED,
                "coordination projection may not request direct source mutation",
                "permitted_action_set",
            )
        )
    if actions & MAILBOX_IO_ACTION_SET:
        issues.append(
            ClaimValidationIssue(
                ClaimIssueKind.MAILBOX_IO_REQUESTED,
                ClaimIssueSeverity.REFUSED,
                "coordination projection may not request mailbox IO in IR6-IA03",
                "permitted_action_set",
            )
        )
    if actions & DISPATCH_ACTION_SET:
        issues.append(
            ClaimValidationIssue(
                ClaimIssueKind.DISPATCH_REQUESTED,
                ClaimIssueSeverity.REFUSED,
                "coordination projection may not request agent dispatch",
                "permitted_action_set",
            )
        )
    if actions & LIVE_CONTROL_ACTION_SET:
        issues.append(
            ClaimValidationIssue(
                ClaimIssueKind.LIVE_CONTROL_REQUESTED,
                ClaimIssueSeverity.REFUSED,
                "coordination projection may not request operations or live machine control",
                "permitted_action_set",
            )
        )
    return tuple(issues)


def _severity_for_boundary(envelope: WorkBoundaryProjectionEnvelope) -> ClaimIssueSeverity:
    if envelope.fault_ref_set:
        return ClaimIssueSeverity.FAULT
    if envelope.ambiguous_identity_ref_set:
        return ClaimIssueSeverity.INTERRUPT
    if envelope.stale_trigger_ref_set:
        return ClaimIssueSeverity.STALE
    if envelope.refusal_reason_set:
        return ClaimIssueSeverity.REFUSED
    return ClaimIssueSeverity.BLOCKED


def _severity_for_freshness(freshness_state: ClaimFreshnessState) -> ClaimIssueSeverity:
    if freshness_state == ClaimFreshnessState.FAULTED:
        return ClaimIssueSeverity.FAULT
    if freshness_state == ClaimFreshnessState.INTERRUPTED:
        return ClaimIssueSeverity.INTERRUPT
    if freshness_state == ClaimFreshnessState.STALE:
        return ClaimIssueSeverity.STALE
    if freshness_state == ClaimFreshnessState.CONTESTED:
        return ClaimIssueSeverity.BLOCKED
    return ClaimIssueSeverity.BLOCKED
