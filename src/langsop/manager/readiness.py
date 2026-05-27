"""Readiness recomputation for IR8 manager planning records."""

from __future__ import annotations

from .records import (
    ManagerCycleInput,
    ManagerIssue,
    ManagerIssueKind,
    ManagerIssueSeverity,
    ManagerModelRoute,
    ManagerReadinessResult,
    ManagerReadinessState,
    ManagerWorkPacketState,
    NO_DISPATCH_NOTICE,
    SOPFirstManagerInterruptContext,
    completion_gate_for_cycle,
    manager_cycle_input_from_mapping,
    proof_obligations_for_cycle,
)


LIVE_CONTROL_EFFECT_MARKER_SET: frozenset[str] = frozenset(
    {
        "live_control",
        "process",
        "gpu",
        "model",
        "job",
        "credential",
        "network",
        "destructive",
        "live_machine",
    }
)


def recompute_manager_readiness(cycle: ManagerCycleInput) -> ManagerReadinessResult:
    """Recompute readiness without dispatching work or performing effects."""

    proof_obligations = proof_obligations_for_cycle(cycle)
    completion_gate = completion_gate_for_cycle(cycle)
    issues: list[ManagerIssue] = []
    readiness_state = ManagerReadinessState.READY_FOR_CLAIM
    packet_state = ManagerWorkPacketState.READY_FOR_CLAIM

    if not cycle.source_ref_set:
        issues.append(
            ManagerIssue(
                ManagerIssueKind.MISSING_SOURCE_AUTHORITY,
                ManagerIssueSeverity.FAULT,
                "source_ref_set is required before manager readiness can be trusted",
                "source_ref_set",
            )
        )

    if not cycle.authority_notice_ref:
        issues.append(
            ManagerIssue(
                ManagerIssueKind.MISSING_AUTHORITY_NOTICE,
                ManagerIssueSeverity.FAULT,
                "authority_notice_ref is required before manager readiness can be trusted",
                "authority_notice_ref",
            )
        )

    stop = _first_stop_projection(cycle)
    if stop is not None:
        readiness_state, packet_state, issue = stop
        issues.append(issue)

    if not completion_gate.opened and readiness_state == ManagerReadinessState.READY_FOR_CLAIM:
        issues.append(
            ManagerIssue(
                ManagerIssueKind.COMPLETION_GATE_BYPASS,
                ManagerIssueSeverity.BLOCKED,
                "completion review gate must be visible before a ready packet can claim work",
                "completion_review_ref",
            )
        )
        readiness_state = ManagerReadinessState.BLOCKED
        packet_state = ManagerWorkPacketState.NOT_READY

    if any(not obligation.satisfied for obligation in proof_obligations) and (
        readiness_state == ManagerReadinessState.READY_FOR_CLAIM
    ):
        issues.append(
            ManagerIssue(
                ManagerIssueKind.PROOF_OBLIGATION_BYPASS,
                ManagerIssueSeverity.BLOCKED,
                "proof obligations must be visible before a ready packet can claim work",
                "proof_obligation_ref_set",
            )
        )
        readiness_state = ManagerReadinessState.BLOCKED
        packet_state = ManagerWorkPacketState.NOT_READY

    if _model_route_missing(cycle) and readiness_state == ManagerReadinessState.READY_FOR_CLAIM:
        issues.append(
            ManagerIssue(
                ManagerIssueKind.MODEL_ROUTE_AMBIGUITY,
                ManagerIssueSeverity.INTERRUPT,
                "manager packets require GPT-5.3-Codex-Spark-suitable or requires deeper reasoning",
                "model_route",
            )
        )
        readiness_state = ManagerReadinessState.REFUSED_UNTIL_MODEL_ROUTE_DECLARED
        packet_state = ManagerWorkPacketState.NOT_READY

    interrupt = _interrupt_context_for_cycle(cycle, issues)
    accepted = not issues and readiness_state == ManagerReadinessState.READY_FOR_CLAIM
    return ManagerReadinessResult(
        accepted=accepted,
        readiness_state=readiness_state,
        work_packet_state=packet_state,
        issues=tuple(issues),
        proof_obligation_set=proof_obligations,
        completion_gate=completion_gate,
        interrupt_context=interrupt,
        authority_notice_set=(cycle.authority_notice_ref,) if cycle.authority_notice_ref else (),
        dispatch_authorized=False,
        live_effect_performed=False,
        non_authority_notice=NO_DISPATCH_NOTICE,
    )


def recompute_manager_readiness_from_mapping(data: dict[str, object]) -> ManagerReadinessResult:
    """Recompute manager readiness directly from mapping data."""

    return recompute_manager_readiness(manager_cycle_input_from_mapping(data))


def _first_stop_projection(
    cycle: ManagerCycleInput,
) -> tuple[ManagerReadinessState, ManagerWorkPacketState, ManagerIssue] | None:
    if cycle.source_authority_state in {"accepted_but_stale", "stale"} or cycle.freshness_state.value == "stale":
        return (
            ManagerReadinessState.BLOCKED_STALE,
            ManagerWorkPacketState.NOT_READY,
            ManagerIssue(
                ManagerIssueKind.STALE_BOUNDARY_INPUT,
                ManagerIssueSeverity.STALE,
                "stale boundary input blocks ready packet projection",
                "source_authority_state",
            ),
        )

    if cycle.support_state in {"missing_required_support", "missing", "unsupported"}:
        return (
            ManagerReadinessState.BLOCKED_UNSUPPORTED,
            ManagerWorkPacketState.NOT_READY,
            ManagerIssue(
                ManagerIssueKind.UNSUPPORTED_REQUIREMENT,
                ManagerIssueSeverity.BLOCKED,
                "unsupported requirement blocks ready packet projection",
                "support_state",
            ),
        )

    if cycle.coordination_state in {"contested_by_active_claim", "contested"}:
        return (
            ManagerReadinessState.INTERRUPTED_CONTESTED,
            ManagerWorkPacketState.NOT_READY,
            ManagerIssue(
                ManagerIssueKind.CONTESTED_COORDINATION_CLAIM,
                ManagerIssueSeverity.INTERRUPT,
                "contested coordination claim requires SOP-first review",
                "coordination_state",
            ),
        )

    if cycle.carrier_context_kind or cycle.carrier_context_state == "informative_only":
        return (
            ManagerReadinessState.CONTEXT_RECORDED_NO_PROMOTION,
            ManagerWorkPacketState.UNCHANGED_WITHOUT_SOURCE_AUTHORITY,
            ManagerIssue(
                ManagerIssueKind.MISSING_SOURCE_AUTHORITY,
                ManagerIssueSeverity.BLOCKED,
                "carrier context may inform review but cannot open readiness alone",
                "carrier_context_kind",
            ),
        )

    if cycle.requested_effect_classification_state == "missing":
        return (
            ManagerReadinessState.INTERRUPTED_UNCLASSIFIED,
            ManagerWorkPacketState.NOT_READY,
            ManagerIssue(
                ManagerIssueKind.UNCLASSIFIED_AUTHORITY_SENSITIVE_RECORD,
                ManagerIssueSeverity.INTERRUPT,
                "surface action request requires classification before readiness changes",
                "requested_effect_classification_state",
            ),
        )

    if cycle.operations_dry_run_state == "success" and cycle.requested_promotion in {
        "dispatch_authority",
        "live_control",
    }:
        return (
            ManagerReadinessState.EVIDENCE_RECORDED,
            ManagerWorkPacketState.NOT_DISPATCHED,
            ManagerIssue(
                ManagerIssueKind.DRY_RUN_TO_LIVE_CONTROL_PROMOTION,
                ManagerIssueSeverity.REFUSED,
                "dry-run success is evidence, not dispatch or live-control authority",
                "requested_promotion",
            ),
        )

    if cycle.human_override_state and cycle.human_override_state != "present_fresh_scoped_revocable":
        return (
            ManagerReadinessState.BLOCKED,
            ManagerWorkPacketState.NOT_READY,
            ManagerIssue(
                ManagerIssueKind.HUMAN_OVERRIDE_REQUIRED,
                ManagerIssueSeverity.BLOCKED,
                "human override must be present, fresh, scoped, and revocable",
                "human_override_state",
            ),
        )

    if cycle.human_override_state == "present_fresh_scoped_revocable":
        return (
            ManagerReadinessState.CONTEXTUAL_OVERRIDE_RECORDED,
            ManagerWorkPacketState.BOUNDED_BY_OVERRIDE_SCOPE,
            ManagerIssue(
                ManagerIssueKind.MISSING_SOURCE_AUTHORITY,
                ManagerIssueSeverity.BLOCKED,
                "human override is contextual and bounded by its explicit scope",
                "human_override_state",
            ),
        )

    if cycle.generated_projection_state and cycle.requested_promotion == "source_authority":
        return (
            ManagerReadinessState.SOURCE_AUTHORITY_REQUIRED,
            ManagerWorkPacketState.NOT_READY_FROM_PROJECTION_ALONE,
            ManagerIssue(
                ManagerIssueKind.GENERATED_OUTPUT_AUTHORITY_PROMOTION,
                ManagerIssueSeverity.REFUSED,
                "generated projections cannot become source authority",
                "requested_promotion",
            ),
        )

    if cycle.graph_checkpoint_state and cycle.requested_promotion == "source_authority":
        return (
            ManagerReadinessState.BLOCKED_UNTIL_KERNEL_REFERENCE_CHECKED,
            ManagerWorkPacketState.NOT_READY_FROM_CHECKPOINT_ALONE,
            ManagerIssue(
                ManagerIssueKind.GRAPH_CHECKPOINT_AUTHORITY_PROMOTION,
                ManagerIssueSeverity.REFUSED,
                "graph checkpoints cannot become source authority",
                "requested_promotion",
            ),
        )

    if _requests_forbidden_live_scope(cycle):
        return (
            ManagerReadinessState.REFUSED_FORBIDDEN_SCOPE,
            ManagerWorkPacketState.NOT_READY,
            ManagerIssue(
                ManagerIssueKind.REQUESTED_FORBIDDEN_SCOPE,
                ManagerIssueSeverity.REFUSED,
                "live-control request is refused without separate accepted authority",
                "requested_effect_kind",
            ),
        )

    return None


def _interrupt_context_for_cycle(
    cycle: ManagerCycleInput,
    issues: list[ManagerIssue],
) -> SOPFirstManagerInterruptContext | None:
    interrupt_issue = next(
        (
            issue
            for issue in issues
            if issue.severity
            in {ManagerIssueSeverity.INTERRUPT, ManagerIssueSeverity.STALE, ManagerIssueSeverity.REFUSED}
        ),
        None,
    )
    if interrupt_issue is None:
        return None
    return SOPFirstManagerInterruptContext(
        interrupt_id=f"{cycle.work_ref}:{interrupt_issue.issue_kind.value}:interrupt",
        interrupt_kind=interrupt_issue.issue_kind,
        active_work_ref=cycle.work_ref,
        evidence_ref_set=tuple(sorted(set(cycle.source_ref_set + (interrupt_issue.issue_kind.value,)))),
        required_route_set=("SOP_first_review", "completion_review"),
    )


def _model_route_missing(cycle: ManagerCycleInput) -> bool:
    return cycle.model_route == ManagerModelRoute.MISSING or cycle.model_route_state in {"missing", "unknown", ""}


def _requests_forbidden_live_scope(cycle: ManagerCycleInput) -> bool:
    if cycle.live_authority_state not in {"missing", "absent", ""}:
        return False
    text = cycle.requested_effect_kind.lower()
    return any(marker in text for marker in LIVE_CONTROL_EFFECT_MARKER_SET)
