"""Authority display envelope models for IR5 surface projections.

These helpers validate projection metadata only. They do not mutate source
authority, write generated output, dispatch work, or control operations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable


class AuthorityTier(str, Enum):
    """Accepted authority tiers from the IR5 display contract."""

    SOURCE_AUTHORITY = "source_authority"
    ACCEPTED_EXECUTION_EVIDENCE = "accepted_execution_evidence"
    GENERATED_PROJECTION_EVIDENCE = "generated_projection_evidence"
    CARRIER_CONTEXT = "carrier_context"


class AuthorityDisplayIssueKind(str, Enum):
    """Issue vocabulary for authority display envelope validation."""

    MISSING_FIELD = "missing_field"
    MISSING_SOURCE_REF = "missing_source_ref_set"
    MISSING_AUTHORITY_NOTICE = "missing_authority_notice"
    MISSING_FRESHNESS_STATE = "missing_freshness_state"
    MISSING_REQUIRED_ROUTE = "missing_required_route_set"
    HIDDEN_FORBIDDEN_ACTION = "hidden_forbidden_action_set"
    LOWER_TIER_MISREPRESENTED = "lower_authority_tier_misrepresented"
    SOURCE_MUTATION_REQUESTED = "source_authority_mutation_requested"


class AuthorityDisplayIssueSeverity(str, Enum):
    """How a future projector should treat an authority display issue."""

    BLOCKED = "blocked"
    FAULT = "fault"
    REFUSED = "refused"


LOW_AUTHORITY_ACTION_SET: frozenset[str] = frozenset({"observe", "comment", "propose"})

AUTHORITY_SENSITIVE_ACTION_SET: frozenset[str] = frozenset(
    {
        "request_work_packet",
        "request_claim",
        "request_review",
        "request_rebake",
        "request_interrupt_resolution",
        "request_human_override",
        "request_dry_run",
        "request_completion_review",
    }
)

DIRECT_MUTATION_ACTION_SET: frozenset[str] = frozenset(
    {
        "direct_source_authority_write",
        "direct_source_write",
        "direct_accepted_pack_write",
        "direct_completion_review_acceptance",
        "direct_claim_acceptance",
        "direct_agent_dispatch",
        "direct_command_execution",
        "direct_operations_command",
        "source_mutation",
        "operations_control",
        "live_machine_control",
    }
)

FRESHNESS_STATE_SET: frozenset[str] = frozenset(
    {
        "fresh",
        "stale",
        "unknown",
        "contested",
        "interrupted",
        "blocked",
        "faulted",
        "pending_review",
    }
)

REQUIRED_AUTHORITY_DISPLAY_FIELD_SET: tuple[str, ...] = (
    "display_projection_id",
    "projected_subject_ref",
    "carrier_surface",
    "authority_tier",
    "trust_limit",
    "source_authority_ref_set",
    "derived_from_ref_set",
    "authority_notice_ref",
    "freshness_state",
    "risk_reason",
    "permitted_action_set",
    "forbidden_action_set",
    "required_route_set",
    "mutation_boundary_ref",
    "visible_before_action",
)


@dataclass(frozen=True)
class AuthorityDisplayIssue:
    """One blocked, fault, or refusal reason for a display envelope."""

    issue_kind: AuthorityDisplayIssueKind
    severity: AuthorityDisplayIssueSeverity
    reason: str
    field_name: str | None = None


@dataclass(frozen=True)
class AuthorityDisplayValidationResult:
    """Pure validation result for an authority display envelope."""

    accepted: bool
    issues: tuple[AuthorityDisplayIssue, ...] = ()

    @property
    def has_fault(self) -> bool:
        return any(issue.severity == AuthorityDisplayIssueSeverity.FAULT for issue in self.issues)

    @property
    def has_blocker(self) -> bool:
        return any(issue.severity == AuthorityDisplayIssueSeverity.BLOCKED for issue in self.issues)

    @property
    def has_refusal(self) -> bool:
        return any(issue.severity == AuthorityDisplayIssueSeverity.REFUSED for issue in self.issues)


@dataclass(frozen=True)
class AuthorityDisplayEnvelope:
    """Decision-facing authority notice metadata for one projection."""

    display_projection_id: str
    projected_subject_ref: str
    carrier_surface: str
    authority_tier: AuthorityTier
    trust_limit: str
    source_authority_ref_set: tuple[str, ...]
    derived_from_ref_set: tuple[str, ...]
    authority_notice_ref: str
    freshness_state: str
    risk_reason: str
    permitted_action_set: tuple[str, ...]
    forbidden_action_set: tuple[str, ...]
    required_route_set: tuple[str, ...]
    mutation_boundary_ref: str
    visible_before_action: bool = True
    lower_authority_tier_misrepresented: bool = False
    source_authority_mutation_requested: bool = False

    @property
    def is_source_authority(self) -> bool:
        return self.authority_tier == AuthorityTier.SOURCE_AUTHORITY

    @property
    def includes_authority_sensitive_action(self) -> bool:
        return bool(set(self.permitted_action_set) & AUTHORITY_SENSITIVE_ACTION_SET)


def authority_display_envelope_from_parts(
    *,
    display_projection_id: str,
    projected_subject_ref: str,
    carrier_surface: str,
    authority_tier: str | AuthorityTier,
    trust_limit: str,
    source_authority_ref_set: Iterable[str],
    derived_from_ref_set: Iterable[str] = (),
    authority_notice_ref: str,
    freshness_state: str,
    risk_reason: str,
    permitted_action_set: Iterable[str],
    forbidden_action_set: Iterable[str],
    required_route_set: Iterable[str],
    mutation_boundary_ref: str,
    visible_before_action: bool = True,
    lower_authority_tier_misrepresented: bool = False,
    source_authority_mutation_requested: bool = False,
) -> AuthorityDisplayEnvelope:
    """Build an authority display envelope while normalizing iterables and tier."""

    return AuthorityDisplayEnvelope(
        display_projection_id=display_projection_id,
        projected_subject_ref=projected_subject_ref,
        carrier_surface=carrier_surface,
        authority_tier=AuthorityTier(authority_tier),
        trust_limit=trust_limit,
        source_authority_ref_set=tuple(source_authority_ref_set),
        derived_from_ref_set=tuple(derived_from_ref_set),
        authority_notice_ref=authority_notice_ref,
        freshness_state=str(freshness_state),
        risk_reason=risk_reason,
        permitted_action_set=tuple(permitted_action_set),
        forbidden_action_set=tuple(forbidden_action_set),
        required_route_set=tuple(required_route_set),
        mutation_boundary_ref=mutation_boundary_ref,
        visible_before_action=visible_before_action,
        lower_authority_tier_misrepresented=lower_authority_tier_misrepresented,
        source_authority_mutation_requested=source_authority_mutation_requested,
    )


def validate_authority_display_envelope(
    envelope: AuthorityDisplayEnvelope,
) -> AuthorityDisplayValidationResult:
    """Validate an authority display envelope against the accepted IR5 contract."""

    issues: list[AuthorityDisplayIssue] = []

    for field_name in REQUIRED_AUTHORITY_DISPLAY_FIELD_SET:
        if not _field_has_value(envelope, field_name):
            issues.append(
                AuthorityDisplayIssue(
                    AuthorityDisplayIssueKind.MISSING_FIELD,
                    AuthorityDisplayIssueSeverity.FAULT,
                    f"{field_name} is required",
                    field_name,
                )
            )

    if not envelope.source_authority_ref_set:
        issues.append(
            AuthorityDisplayIssue(
                AuthorityDisplayIssueKind.MISSING_SOURCE_REF,
                AuthorityDisplayIssueSeverity.FAULT,
                "source authority refs are required before projection use",
                "source_authority_ref_set",
            )
        )

    if not envelope.authority_notice_ref:
        issues.append(
            AuthorityDisplayIssue(
                AuthorityDisplayIssueKind.MISSING_AUTHORITY_NOTICE,
                AuthorityDisplayIssueSeverity.FAULT,
                "authority notice ref is required before projection use",
                "authority_notice_ref",
            )
        )

    if envelope.freshness_state not in FRESHNESS_STATE_SET:
        issues.append(
            AuthorityDisplayIssue(
                AuthorityDisplayIssueKind.MISSING_FRESHNESS_STATE,
                AuthorityDisplayIssueSeverity.FAULT,
                "freshness state must use the accepted IR5 vocabulary",
                "freshness_state",
            )
        )

    if not envelope.required_route_set:
        issues.append(
            AuthorityDisplayIssue(
                AuthorityDisplayIssueKind.MISSING_REQUIRED_ROUTE,
                AuthorityDisplayIssueSeverity.FAULT,
                "required route set must be visible before action",
                "required_route_set",
            )
        )

    if not envelope.forbidden_action_set:
        issues.append(
            AuthorityDisplayIssue(
                AuthorityDisplayIssueKind.HIDDEN_FORBIDDEN_ACTION,
                AuthorityDisplayIssueSeverity.BLOCKED,
                "forbidden action set must be visible before action",
                "forbidden_action_set",
            )
        )

    if envelope.lower_authority_tier_misrepresented or _lower_tier_claims_source_authority(envelope):
        issues.append(
            AuthorityDisplayIssue(
                AuthorityDisplayIssueKind.LOWER_TIER_MISREPRESENTED,
                AuthorityDisplayIssueSeverity.FAULT,
                "lower-tier records may not be displayed as source authority",
                "authority_tier",
            )
        )

    if envelope.source_authority_mutation_requested or set(envelope.permitted_action_set) & DIRECT_MUTATION_ACTION_SET:
        issues.append(
            AuthorityDisplayIssue(
                AuthorityDisplayIssueKind.SOURCE_MUTATION_REQUESTED,
                AuthorityDisplayIssueSeverity.REFUSED,
                "display state may not request direct source or operations mutation",
                "permitted_action_set",
            )
        )

    return AuthorityDisplayValidationResult(not issues, tuple(issues))


def _lower_tier_claims_source_authority(envelope: AuthorityDisplayEnvelope) -> bool:
    if envelope.is_source_authority:
        return False
    lower_text = " ".join(
        (
            envelope.trust_limit,
            envelope.risk_reason,
            envelope.mutation_boundary_ref,
            *envelope.permitted_action_set,
        )
    ).lower()
    return "source_authority" in lower_text or "source authority" in lower_text


def _field_has_value(envelope: AuthorityDisplayEnvelope, field_name: str) -> bool:
    value = getattr(envelope, field_name)
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value)
    if isinstance(value, tuple):
        return True
    return True
