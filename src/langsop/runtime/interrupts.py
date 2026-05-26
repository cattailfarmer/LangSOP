"""SOP-first interrupt context models for the bounded IR4 runtime graph."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json

from .graph_state import (
    GraphIssue,
    GraphIssueKind,
    GraphIssueSeverity,
    GraphNodeId,
    GraphPhase,
    GraphState,
    GraphValidationResult,
    NON_AUTHORITY_WARNING,
)


INTERRUPT_SCHEMA_VERSION = "ir4-sop-first-interrupt-context-v1"


class InterruptKind(str, Enum):
    """Allowed SOP-first interrupt kinds from the accepted IR4 policy."""

    AMBIGUOUS_IDENTITY = "ambiguous_identity"
    AUTHORITY_CONFLICT = "authority_conflict"
    STALE_INPUT = "stale_input"
    MISSING_PROOF_ROUTE = "missing_proof_route"
    CONTESTED_COORDINATION_CLAIM = "contested_coordination_claim"
    UNSUPPORTED_SCOPE = "unsupported_scope"
    HIGH_RISK_OPERATION = "high_risk_operation"
    HUMAN_OVERRIDE_REQUIRED = "human_override_required"
    CHECKPOINT_AUTHORITY_CONFUSION = "checkpoint_authority_confusion"
    HIDDEN_WRITE_CANNOT_BE_RULED_OUT = "hidden_write_cannot_be_ruled_out"


FORBIDDEN_INTERRUPT_CONTEXT_MARKERS: frozenset[str] = frozenset(
    {
        "credential",
        "gpu_state",
        "live_machine_state",
        "network_state",
        "process_list",
        "secret",
    }
)


@dataclass(frozen=True)
class InterruptContextPacket:
    """Generated interrupt packet for SOP or human resume judgment."""

    interrupt_id: str
    interrupt_kind: InterruptKind
    originating_node_id: GraphNodeId
    graph_phase: GraphPhase
    active_work_packet_ref: str
    input_record_ref_set: tuple[str, ...]
    authority_basis_ref_set: tuple[str, ...]
    operator_trace_ref_set: tuple[str, ...]
    fault_record_ref_set: tuple[str, ...]
    stale_projection_ref_set: tuple[str, ...]
    contested_claim_ref_set: tuple[str, ...]
    required_judgment: str
    allowed_resume_route_set: tuple[str, ...]
    evidence_ref_set: tuple[str, ...] = ()
    interrupt_schema_version: str = INTERRUPT_SCHEMA_VERSION
    packet_status: str = "generated_projection_only_until_rewritten_as_reviewed_SOP_artifact"
    non_authority_warning: str = NON_AUTHORITY_WARNING


def deterministic_interrupt_id(
    *,
    interrupt_kind: InterruptKind,
    originating_node_id: GraphNodeId,
    active_work_packet_ref: str,
    evidence_ref_set: tuple[str, ...],
    interrupt_schema_version: str = INTERRUPT_SCHEMA_VERSION,
) -> str:
    """Return a stable interrupt id for fixed interrupt context."""

    payload = {
        "active_work_packet_ref": active_work_packet_ref,
        "evidence_ref_set": sorted(evidence_ref_set),
        "interrupt_kind": interrupt_kind.value,
        "interrupt_schema_version": interrupt_schema_version,
        "originating_node_id": originating_node_id.value,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_interrupt_context(
    *,
    interrupt_kind: InterruptKind | str,
    graph_state: GraphState,
    required_judgment: str,
    allowed_resume_route_set: tuple[str, ...],
    evidence_ref_set: tuple[str, ...] = (),
) -> InterruptContextPacket:
    """Build an SOP-first interrupt context packet without persisting it."""

    resolved_kind = InterruptKind(interrupt_kind)
    evidence_refs = tuple(evidence_ref_set)
    interrupt_id = deterministic_interrupt_id(
        interrupt_kind=resolved_kind,
        originating_node_id=graph_state.current_node_id,
        active_work_packet_ref=graph_state.active_work_packet_ref,
        evidence_ref_set=evidence_refs,
    )
    return InterruptContextPacket(
        interrupt_id=interrupt_id,
        interrupt_kind=resolved_kind,
        originating_node_id=graph_state.current_node_id,
        graph_phase=graph_state.graph_phase,
        active_work_packet_ref=graph_state.active_work_packet_ref,
        input_record_ref_set=graph_state.input_record_ref_set,
        authority_basis_ref_set=graph_state.accepted_boundary_pack_ref_set,
        operator_trace_ref_set=graph_state.operator_trace_ref_set,
        fault_record_ref_set=graph_state.fault_record_ref_set,
        stale_projection_ref_set=graph_state.stale_projection_ref_set,
        contested_claim_ref_set=graph_state.coordination_claim_ref_set,
        required_judgment=required_judgment,
        allowed_resume_route_set=tuple(allowed_resume_route_set),
        evidence_ref_set=evidence_refs,
    )


def validate_interrupt_context(packet: InterruptContextPacket) -> GraphValidationResult:
    """Validate interrupt packet shape and forbidden context markers."""

    issues: list[GraphIssue] = []
    if not packet.active_work_packet_ref:
        issues.append(
            GraphIssue(
                GraphIssueKind.MISSING_FIELD,
                GraphIssueSeverity.FAULT,
                "active_work_packet_ref is required in interrupt context",
                "active_work_packet_ref",
            )
        )

    if not packet.required_judgment:
        issues.append(
            GraphIssue(
                GraphIssueKind.MISSING_FIELD,
                GraphIssueSeverity.FAULT,
                "required_judgment is required in interrupt context",
                "required_judgment",
            )
        )

    if not packet.allowed_resume_route_set:
        issues.append(
            GraphIssue(
                GraphIssueKind.MISSING_PROOF_ROUTE
                if hasattr(GraphIssueKind, "MISSING_PROOF_ROUTE")
                else GraphIssueKind.MISSING_AUTHORITY,
                GraphIssueSeverity.BLOCKED,
                "allowed_resume_route_set must cite accepted resume routes",
                "allowed_resume_route_set",
            )
        )

    forbidden_hits = _forbidden_context_hits(packet.evidence_ref_set + packet.input_record_ref_set)
    for marker in forbidden_hits:
        issues.append(
            GraphIssue(
                GraphIssueKind.UNSUPPORTED_SCOPE,
                GraphIssueSeverity.FAULT,
                f"interrupt context includes forbidden live-state marker: {marker}",
                "evidence_ref_set",
            )
        )

    if packet.packet_status != "generated_projection_only_until_rewritten_as_reviewed_SOP_artifact":
        issues.append(
            GraphIssue(
                GraphIssueKind.GENERATED_AUTHORITY,
                GraphIssueSeverity.FAULT,
                "interrupt packet must not claim direct authority",
                "packet_status",
            )
        )

    return GraphValidationResult(not issues, tuple(issues))


def interrupt_kind_for_issue(issue: GraphIssue) -> InterruptKind:
    """Map graph issue kinds to accepted interrupt kinds."""

    if issue.issue_kind == GraphIssueKind.AMBIGUOUS_IDENTITY:
        return InterruptKind.AMBIGUOUS_IDENTITY
    if issue.issue_kind == GraphIssueKind.CHECKPOINT_AUTHORITY_CONFUSION:
        return InterruptKind.CHECKPOINT_AUTHORITY_CONFUSION
    if issue.issue_kind == GraphIssueKind.CONTESTED_COORDINATION:
        return InterruptKind.CONTESTED_COORDINATION_CLAIM
    if issue.issue_kind == GraphIssueKind.STALE_PROJECTION:
        return InterruptKind.STALE_INPUT
    if issue.issue_kind == GraphIssueKind.UNSUPPORTED_SCOPE:
        return InterruptKind.UNSUPPORTED_SCOPE
    if issue.issue_kind == GraphIssueKind.HIDDEN_WRITE_ATTEMPT:
        return InterruptKind.HIDDEN_WRITE_CANNOT_BE_RULED_OUT
    return InterruptKind.MISSING_PROOF_ROUTE


def _forbidden_context_hits(ref_set: tuple[str, ...]) -> tuple[str, ...]:
    hits: list[str] = []
    for ref in ref_set:
        lowered = ref.lower()
        for marker in FORBIDDEN_INTERRUPT_CONTEXT_MARKERS:
            if marker in lowered:
                hits.append(marker)
    return tuple(sorted(set(hits)))
