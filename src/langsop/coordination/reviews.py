"""Conflict, stale-claim, and human-override review models for IR6."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class CoordinationReviewDecision(str, Enum):
    """Accepted review decision vocabulary."""

    PROCEED = "proceed"
    BLOCK = "block"
    INTERRUPT = "interrupt"
    REFRESH = "refresh"
    RELEASE = "release"
    SUPERSEDE = "supersede"
    INVALIDATE = "invalidate"
    REBAKE = "rebake"
    HUMAN_OVERRIDE = "human_override"
    REFUSE = "refuse"


class CoordinationReviewIssueKind(str, Enum):
    """Issue vocabulary for coordination review."""

    CONTESTED_CLAIM = "contested_claim"
    STALE_CLAIM = "stale_claim"
    AMBIGUOUS_IDENTITY = "ambiguous_identity"
    HIDDEN_SCOPE_EXPANSION = "hidden_scope_expansion"
    PENDING_HUMAN_OVERRIDE = "pending_human_override"
    OUT_OF_SCOPE_OVERRIDE = "out_of_scope_override"
    EXPIRED_OVERRIDE = "expired_override"
    FORBIDDEN_EFFECT_REQUESTED = "forbidden_effect_requested"


class CoordinationReviewIssueSeverity(str, Enum):
    """How a review issue should be treated."""

    BLOCKED = "blocked"
    STALE = "stale"
    FAULT = "fault"
    INTERRUPT = "interrupt"
    REFUSED = "refused"


FORBIDDEN_OVERRIDE_EFFECT_SET: frozenset[str] = frozenset(
    {
        "assignment",
        "assign_agent",
        "dispatch",
        "agent_dispatch",
        "completion_acceptance",
        "mailbox_file_write",
        "operations_control",
        "live_machine_control",
    }
)


@dataclass(frozen=True)
class CoordinationReviewIssue:
    """One review blocker, stale signal, fault, interrupt, or refusal."""

    issue_kind: CoordinationReviewIssueKind
    severity: CoordinationReviewIssueSeverity
    reason: str
    evidence_ref_set: tuple[str, ...] = ()


@dataclass(frozen=True)
class CoordinationReviewResult:
    """Review-only decision record."""

    decision: CoordinationReviewDecision
    issue_set: tuple[CoordinationReviewIssue, ...] = ()
    required_route_set: tuple[str, ...] = ()
    forbidden_effect_set: tuple[str, ...] = ()
    authority_notice_ref: str = ""

    @property
    def accepted(self) -> bool:
        return self.decision == CoordinationReviewDecision.PROCEED


@dataclass(frozen=True)
class CoordinationConflictContext:
    """Evidence context for contested, stale, or interrupted claims."""

    involved_claim_ref_set: tuple[str, ...] = ()
    contested_claim_ref_set: tuple[str, ...] = ()
    stale_claim_ref_set: tuple[str, ...] = ()
    ambiguous_identity_ref_set: tuple[str, ...] = ()
    hidden_scope_expansion_ref_set: tuple[str, ...] = ()
    pending_human_override_ref_set: tuple[str, ...] = ()
    authority_notice_ref: str = ""


@dataclass(frozen=True)
class HumanOverrideEnvelope:
    """Scoped human override request for coordination review only."""

    override_ref: str
    requested_override_scope: str
    authority_notice_ref: str
    expiration_or_recheck_condition: str
    requested_effect_set: tuple[str, ...] = ()
    forbidden_effect_set: tuple[str, ...] = ()
    expired: bool = False
    out_of_scope: bool = False


def coordination_conflict_context_from_parts(
    *,
    involved_claim_ref_set: Iterable[str] = (),
    contested_claim_ref_set: Iterable[str] = (),
    stale_claim_ref_set: Iterable[str] = (),
    ambiguous_identity_ref_set: Iterable[str] = (),
    hidden_scope_expansion_ref_set: Iterable[str] = (),
    pending_human_override_ref_set: Iterable[str] = (),
    authority_notice_ref: str = "",
) -> CoordinationConflictContext:
    """Build a conflict review context while normalizing sets."""

    return CoordinationConflictContext(
        involved_claim_ref_set=tuple(involved_claim_ref_set),
        contested_claim_ref_set=tuple(contested_claim_ref_set),
        stale_claim_ref_set=tuple(stale_claim_ref_set),
        ambiguous_identity_ref_set=tuple(ambiguous_identity_ref_set),
        hidden_scope_expansion_ref_set=tuple(hidden_scope_expansion_ref_set),
        pending_human_override_ref_set=tuple(pending_human_override_ref_set),
        authority_notice_ref=authority_notice_ref,
    )


def human_override_envelope_from_parts(
    *,
    override_ref: str,
    requested_override_scope: str,
    authority_notice_ref: str,
    expiration_or_recheck_condition: str,
    requested_effect_set: Iterable[str] = (),
    forbidden_effect_set: Iterable[str] = (),
    expired: bool = False,
    out_of_scope: bool = False,
) -> HumanOverrideEnvelope:
    """Build a scoped human override envelope."""

    return HumanOverrideEnvelope(
        override_ref=override_ref,
        requested_override_scope=requested_override_scope,
        authority_notice_ref=authority_notice_ref,
        expiration_or_recheck_condition=expiration_or_recheck_condition,
        requested_effect_set=tuple(requested_effect_set),
        forbidden_effect_set=tuple(forbidden_effect_set),
        expired=expired,
        out_of_scope=out_of_scope,
    )


def review_coordination_conflict(context: CoordinationConflictContext) -> CoordinationReviewResult:
    """Review coordination evidence without resolving conflicts silently."""

    issues: list[CoordinationReviewIssue] = []
    if context.hidden_scope_expansion_ref_set:
        issues.append(
            CoordinationReviewIssue(
                CoordinationReviewIssueKind.HIDDEN_SCOPE_EXPANSION,
                CoordinationReviewIssueSeverity.FAULT,
                "hidden scope expansion requires invalidation or rebake",
                context.hidden_scope_expansion_ref_set,
            )
        )
    if context.ambiguous_identity_ref_set:
        issues.append(
            CoordinationReviewIssue(
                CoordinationReviewIssueKind.AMBIGUOUS_IDENTITY,
                CoordinationReviewIssueSeverity.INTERRUPT,
                "ambiguous identity requires clarification",
                context.ambiguous_identity_ref_set,
            )
        )
    if context.stale_claim_ref_set:
        issues.append(
            CoordinationReviewIssue(
                CoordinationReviewIssueKind.STALE_CLAIM,
                CoordinationReviewIssueSeverity.STALE,
                "stale claim requires refresh, release, supersession, or rebake",
                context.stale_claim_ref_set,
            )
        )
    if context.contested_claim_ref_set:
        issues.append(
            CoordinationReviewIssue(
                CoordinationReviewIssueKind.CONTESTED_CLAIM,
                CoordinationReviewIssueSeverity.BLOCKED,
                "contested claims block downstream gates",
                context.contested_claim_ref_set,
            )
        )
    if context.pending_human_override_ref_set:
        issues.append(
            CoordinationReviewIssue(
                CoordinationReviewIssueKind.PENDING_HUMAN_OVERRIDE,
                CoordinationReviewIssueSeverity.BLOCKED,
                "pending human override blocks automatic progression",
                context.pending_human_override_ref_set,
            )
        )

    decision = _decision_for_issues(issues)
    return CoordinationReviewResult(
        decision,
        tuple(issues),
        required_route_set=_required_routes_for_issues(issues),
        forbidden_effect_set=tuple(sorted(FORBIDDEN_OVERRIDE_EFFECT_SET)),
        authority_notice_ref=context.authority_notice_ref,
    )


def review_human_override(envelope: HumanOverrideEnvelope) -> CoordinationReviewResult:
    """Review a human override request as scoped evidence only."""

    issues: list[CoordinationReviewIssue] = []
    requested_effect_set = set(envelope.requested_effect_set)
    forbidden_effect_set = set(envelope.forbidden_effect_set) | FORBIDDEN_OVERRIDE_EFFECT_SET

    if envelope.expired:
        issues.append(
            CoordinationReviewIssue(
                CoordinationReviewIssueKind.EXPIRED_OVERRIDE,
                CoordinationReviewIssueSeverity.REFUSED,
                "human override is expired",
                (envelope.override_ref,),
            )
        )
    if envelope.out_of_scope:
        issues.append(
            CoordinationReviewIssue(
                CoordinationReviewIssueKind.OUT_OF_SCOPE_OVERRIDE,
                CoordinationReviewIssueSeverity.REFUSED,
                "human override request is out of accepted scope",
                (envelope.override_ref,),
            )
        )
    if requested_effect_set & forbidden_effect_set:
        issues.append(
            CoordinationReviewIssue(
                CoordinationReviewIssueKind.FORBIDDEN_EFFECT_REQUESTED,
                CoordinationReviewIssueSeverity.REFUSED,
                "human override cannot authorize forbidden effects",
                tuple(sorted(requested_effect_set & forbidden_effect_set)),
            )
        )

    decision = CoordinationReviewDecision.HUMAN_OVERRIDE if not issues else CoordinationReviewDecision.REFUSE
    return CoordinationReviewResult(
        decision,
        tuple(issues),
        required_route_set=("completion_review", "scope_recheck"),
        forbidden_effect_set=tuple(sorted(forbidden_effect_set)),
        authority_notice_ref=envelope.authority_notice_ref,
    )


def _decision_for_issues(issues: Iterable[CoordinationReviewIssue]) -> CoordinationReviewDecision:
    issue_tuple = tuple(issues)
    if any(issue.severity == CoordinationReviewIssueSeverity.FAULT for issue in issue_tuple):
        return CoordinationReviewDecision.REBAKE
    if any(issue.severity == CoordinationReviewIssueSeverity.INTERRUPT for issue in issue_tuple):
        return CoordinationReviewDecision.INTERRUPT
    if any(issue.severity == CoordinationReviewIssueSeverity.STALE for issue in issue_tuple):
        return CoordinationReviewDecision.REFRESH
    if any(issue.severity == CoordinationReviewIssueSeverity.REFUSED for issue in issue_tuple):
        return CoordinationReviewDecision.REFUSE
    if any(issue.severity == CoordinationReviewIssueSeverity.BLOCKED for issue in issue_tuple):
        return CoordinationReviewDecision.BLOCK
    return CoordinationReviewDecision.PROCEED


def _required_routes_for_issues(issues: Iterable[CoordinationReviewIssue]) -> tuple[str, ...]:
    routes: set[str] = set()
    for issue in issues:
        if issue.issue_kind == CoordinationReviewIssueKind.HIDDEN_SCOPE_EXPANSION:
            routes.update({"fault_review", "packet_rebake"})
        elif issue.issue_kind == CoordinationReviewIssueKind.AMBIGUOUS_IDENTITY:
            routes.update({"identity_clarification", "human_override"})
        elif issue.issue_kind == CoordinationReviewIssueKind.STALE_CLAIM:
            routes.update({"refresh_claim", "release_claim", "supersede_claim", "rebake"})
        elif issue.issue_kind == CoordinationReviewIssueKind.CONTESTED_CLAIM:
            routes.update({"coordination_conflict_signal", "SOP_first_interrupt", "completion_review"})
        elif issue.issue_kind == CoordinationReviewIssueKind.PENDING_HUMAN_OVERRIDE:
            routes.update({"human_override_review", "completion_review"})
    return tuple(sorted(routes))
