"""Mailbox carrier projection models for IR6 coordination.

Mailbox records here are carrier context only. This module never reads,
writes, creates, watches, or mutates mailbox files.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class MailboxFreshnessState(str, Enum):
    """Freshness state for mailbox carrier projections."""

    FRESH = "fresh"
    PENDING_REVIEW = "pending_review"
    STALE = "stale"
    UNKNOWN = "unknown"


class CarrierAuthorityStatus(str, Enum):
    """Authority status vocabulary for carrier-originated records."""

    CARRIER_CONTEXT_ONLY = "carrier_context_only"
    REFUSED_AUTHORITY_PROMOTION = "refused_authority_promotion"


class MailboxCarrierIssueKind(str, Enum):
    """Issue vocabulary for mailbox carrier projection validation."""

    MISSING_FIELD = "missing_field"
    MISSING_AUTHORITY_NOTICE = "missing_authority_notice"
    CARRIER_AUTHORITY_PROMOTION = "carrier_authority_promotion"
    MAILBOX_IO_REQUESTED = "mailbox_io_requested"
    CLAIM_TRANSITION_REQUESTED = "claim_transition_requested"
    DISPATCH_REQUESTED = "agent_dispatch_requested"
    LIVE_CONTROL_REQUESTED = "live_machine_control_requested"


class MailboxCarrierIssueSeverity(str, Enum):
    """How a future projector should treat mailbox carrier issues."""

    BLOCKED = "blocked"
    STALE = "stale"
    FAULT = "fault"
    REFUSED = "refused"


REQUIRED_MAILBOX_CARRIER_FIELD_SET: tuple[str, ...] = (
    "message_ref",
    "carrier_surface",
    "sender_ref",
    "addressed_to_ref",
    "authority_notice_ref",
    "carrier_authority_status",
    "freshness_state",
    "required_route_set",
    "forbidden_action_set",
)

CLAIM_TRANSITION_EFFECT_SET: frozenset[str] = frozenset(
    {
        "directly_activate_claim",
        "activate_claim",
        "release_claim",
        "supersede_claim",
        "accept_completion",
        "completion_acceptance",
        "claim_state_transition",
    }
)

MAILBOX_IO_EFFECT_SET: frozenset[str] = frozenset(
    {
        "mailbox_file_read",
        "mailbox_file_write",
        "mailbox_file_create",
        "read_cursor_persist",
        "watch_mailbox_directory",
        "platform_mailbox_mutation",
    }
)

DISPATCH_EFFECT_SET: frozenset[str] = frozenset({"assign_agent", "agent_dispatch", "dispatch_work"})
LIVE_CONTROL_EFFECT_SET: frozenset[str] = frozenset(
    {"operations_control", "live_machine_control", "process_control", "gpu_control", "model_runtime_control"}
)


@dataclass(frozen=True)
class MailboxCarrierIssue:
    """One blocked, stale, fault, or refusal reason for a carrier projection."""

    issue_kind: MailboxCarrierIssueKind
    severity: MailboxCarrierIssueSeverity
    reason: str
    field_name: str | None = None


@dataclass(frozen=True)
class MailboxCarrierValidationResult:
    """Pure validation result for mailbox carrier envelopes."""

    accepted: bool
    issues: tuple[MailboxCarrierIssue, ...] = ()

    @property
    def has_refusal(self) -> bool:
        return any(issue.severity == MailboxCarrierIssueSeverity.REFUSED for issue in self.issues)

    @property
    def has_fault(self) -> bool:
        return any(issue.severity == MailboxCarrierIssueSeverity.FAULT for issue in self.issues)

    @property
    def has_blocker(self) -> bool:
        return any(issue.severity == MailboxCarrierIssueSeverity.BLOCKED for issue in self.issues)


@dataclass(frozen=True)
class MailboxFreshnessProjection:
    """Mailbox freshness classification without touching the mailbox."""

    freshness_state: MailboxFreshnessState
    reason: str
    unread_notice_present: bool = False
    stale_cursor_present: bool = False


@dataclass(frozen=True)
class MailboxCarrierEnvelope:
    """Carrier-only projection envelope for one mailbox or chat notice."""

    message_ref: str
    carrier_surface: str
    sender_ref: str
    addressed_to_ref: str
    authority_notice_ref: str
    carrier_authority_status: CarrierAuthorityStatus
    freshness_state: MailboxFreshnessState
    required_route_set: tuple[str, ...]
    forbidden_action_set: tuple[str, ...]
    related_claim_ref_set: tuple[str, ...] = ()
    mailbox_last_modified_ms: int | None = None
    read_cursor_ms: int | None = None
    attempted_effect_set: tuple[str, ...] = ()
    mailbox_io_requested: bool = False
    carrier_claimed_as_authority: bool = False


def mailbox_carrier_envelope_from_parts(
    *,
    message_ref: str,
    carrier_surface: str,
    sender_ref: str,
    addressed_to_ref: str,
    authority_notice_ref: str,
    freshness_state: str | MailboxFreshnessState,
    required_route_set: Iterable[str],
    forbidden_action_set: Iterable[str],
    carrier_authority_status: str | CarrierAuthorityStatus = CarrierAuthorityStatus.CARRIER_CONTEXT_ONLY,
    related_claim_ref_set: Iterable[str] = (),
    mailbox_last_modified_ms: int | None = None,
    read_cursor_ms: int | None = None,
    attempted_effect_set: Iterable[str] = (),
    mailbox_io_requested: bool = False,
    carrier_claimed_as_authority: bool = False,
) -> MailboxCarrierEnvelope:
    """Build a mailbox carrier envelope while normalizing enums and sets."""

    return MailboxCarrierEnvelope(
        message_ref=message_ref,
        carrier_surface=carrier_surface,
        sender_ref=sender_ref,
        addressed_to_ref=addressed_to_ref,
        authority_notice_ref=authority_notice_ref,
        carrier_authority_status=CarrierAuthorityStatus(carrier_authority_status),
        freshness_state=MailboxFreshnessState(freshness_state),
        required_route_set=tuple(required_route_set),
        forbidden_action_set=tuple(forbidden_action_set),
        related_claim_ref_set=tuple(related_claim_ref_set),
        mailbox_last_modified_ms=mailbox_last_modified_ms,
        read_cursor_ms=read_cursor_ms,
        attempted_effect_set=tuple(attempted_effect_set),
        mailbox_io_requested=mailbox_io_requested,
        carrier_claimed_as_authority=carrier_claimed_as_authority,
    )


def classify_mailbox_freshness(
    *,
    mailbox_last_modified_ms: int | None,
    read_cursor_ms: int | None,
    missing_message_hash: bool = False,
) -> MailboxFreshnessProjection:
    """Classify mailbox freshness from provided values without reading files."""

    if missing_message_hash:
        return MailboxFreshnessProjection(
            MailboxFreshnessState.STALE,
            "missing message hash prevents cursor trust",
            stale_cursor_present=True,
        )
    if mailbox_last_modified_ms is None or read_cursor_ms is None:
        return MailboxFreshnessProjection(
            MailboxFreshnessState.UNKNOWN,
            "mailbox timestamp or read cursor is missing",
            stale_cursor_present=True,
        )
    if mailbox_last_modified_ms > read_cursor_ms:
        return MailboxFreshnessProjection(
            MailboxFreshnessState.PENDING_REVIEW,
            "unread mailbox notice is newer than read cursor",
            unread_notice_present=True,
        )
    return MailboxFreshnessProjection(MailboxFreshnessState.FRESH, "read cursor covers mailbox timestamp")


def validate_mailbox_carrier_envelope(
    envelope: MailboxCarrierEnvelope,
) -> MailboxCarrierValidationResult:
    """Validate carrier-only mailbox projection boundaries."""

    issues: list[MailboxCarrierIssue] = []
    for field_name in REQUIRED_MAILBOX_CARRIER_FIELD_SET:
        if not _field_has_value(envelope, field_name):
            issues.append(
                MailboxCarrierIssue(
                    MailboxCarrierIssueKind.MISSING_FIELD,
                    MailboxCarrierIssueSeverity.FAULT,
                    f"{field_name} is required",
                    field_name,
                )
            )

    if not envelope.authority_notice_ref:
        issues.append(
            MailboxCarrierIssue(
                MailboxCarrierIssueKind.MISSING_AUTHORITY_NOTICE,
                MailboxCarrierIssueSeverity.FAULT,
                "authority notice ref is required before carrier projection use",
                "authority_notice_ref",
            )
        )

    if (
        envelope.carrier_claimed_as_authority
        or envelope.carrier_authority_status != CarrierAuthorityStatus.CARRIER_CONTEXT_ONLY
    ):
        issues.append(
            MailboxCarrierIssue(
                MailboxCarrierIssueKind.CARRIER_AUTHORITY_PROMOTION,
                MailboxCarrierIssueSeverity.FAULT,
                "mailbox carrier may not be promoted to source authority",
                "carrier_authority_status",
            )
        )

    effects = set(envelope.attempted_effect_set)
    if envelope.mailbox_io_requested or effects & MAILBOX_IO_EFFECT_SET:
        issues.append(_refusal(MailboxCarrierIssueKind.MAILBOX_IO_REQUESTED, "mailbox IO is not authorized"))
    if effects & CLAIM_TRANSITION_EFFECT_SET:
        issues.append(_refusal(MailboxCarrierIssueKind.CLAIM_TRANSITION_REQUESTED, "carrier cannot transition claims"))
    if effects & DISPATCH_EFFECT_SET:
        issues.append(_refusal(MailboxCarrierIssueKind.DISPATCH_REQUESTED, "carrier cannot dispatch agents"))
    if effects & LIVE_CONTROL_EFFECT_SET:
        issues.append(_refusal(MailboxCarrierIssueKind.LIVE_CONTROL_REQUESTED, "carrier cannot control operations"))

    return MailboxCarrierValidationResult(not issues, tuple(issues))


def _refusal(issue_kind: MailboxCarrierIssueKind, reason: str) -> MailboxCarrierIssue:
    return MailboxCarrierIssue(issue_kind, MailboxCarrierIssueSeverity.REFUSED, reason, "attempted_effect_set")


def _field_has_value(envelope: object, field_name: str) -> bool:
    value = getattr(envelope, field_name)
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value)
    if isinstance(value, tuple):
        return True
    return True
