"""Work-packet candidate helpers for IR8 manager projection."""

from __future__ import annotations

from .readiness import recompute_manager_readiness
from .records import (
    ManagerCycleInput,
    ManagerModelRoute,
    ManagerWorkPacketState,
    WorkPacketCandidate,
)


def build_manager_work_packet_candidate(
    cycle: ManagerCycleInput,
) -> WorkPacketCandidate:
    """Build a manager work-packet candidate without dispatch authority."""

    readiness = recompute_manager_readiness(cycle)
    return WorkPacketCandidate(
        packet_id=f"{cycle.work_ref}:manager_packet",
        work_ref=cycle.work_ref,
        readiness_state=readiness.readiness_state,
        packet_state=readiness.work_packet_state,
        model_route=cycle.model_route,
        proof_obligation_set=readiness.proof_obligation_set,
        completion_gate=readiness.completion_gate,
        issue_set=readiness.issues,
        source_ref_set=cycle.source_ref_set,
        authority_notice_ref=cycle.authority_notice_ref,
        dispatch_authorized=False,
        live_effect_performed=False,
        non_authority_notice=readiness.non_authority_notice,
    )


def packet_is_claimable(candidate: WorkPacketCandidate) -> bool:
    """Return true only for non-dispatch ready-for-claim candidates."""

    return (
        candidate.packet_state == ManagerWorkPacketState.READY_FOR_CLAIM
        and candidate.model_route != ManagerModelRoute.MISSING
        and candidate.ready_for_claim
    )
