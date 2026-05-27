"""Planning-only manager orchestration helpers for LangSOP IR8.

The exported models are pure records and validators. They do not dispatch
agents, execute commands, control processes or GPUs, mutate model runtimes,
access credentials, change networks, or authorize live machine control.
"""

from .authority import (
    ManagerAuthorityClassification,
    classify_manager_authority_from_mapping,
    classify_manager_record_authority,
    validate_manager_authority_classification,
)
from .packets import (
    build_manager_work_packet_candidate,
    packet_is_claimable,
)
from .readiness import (
    recompute_manager_readiness,
    recompute_manager_readiness_from_mapping,
)
from .records import (
    NO_DISPATCH_NOTICE,
    NO_LIVE_EFFECT_NOTICE,
    SOP_INTERRUPT_NOTICE,
    CompletionGate,
    ManagerAuthorityClass,
    ManagerCycleInput,
    ManagerFreshnessState,
    ManagerIssue,
    ManagerIssueKind,
    ManagerIssueSeverity,
    ManagerModelRoute,
    ManagerReadinessResult,
    ManagerReadinessState,
    ManagerWorkPacketState,
    ProofObligation,
    SOPFirstManagerInterruptContext,
    WorkPacketCandidate,
    completion_gate_for_cycle,
    manager_cycle_input_from_mapping,
    manager_cycle_input_from_parts,
    proof_obligations_for_cycle,
)

__all__ = (
    "NO_DISPATCH_NOTICE",
    "NO_LIVE_EFFECT_NOTICE",
    "SOP_INTERRUPT_NOTICE",
    "CompletionGate",
    "ManagerAuthorityClass",
    "ManagerAuthorityClassification",
    "ManagerCycleInput",
    "ManagerFreshnessState",
    "ManagerIssue",
    "ManagerIssueKind",
    "ManagerIssueSeverity",
    "ManagerModelRoute",
    "ManagerReadinessResult",
    "ManagerReadinessState",
    "ManagerWorkPacketState",
    "ProofObligation",
    "SOPFirstManagerInterruptContext",
    "WorkPacketCandidate",
    "build_manager_work_packet_candidate",
    "classify_manager_authority_from_mapping",
    "classify_manager_record_authority",
    "completion_gate_for_cycle",
    "manager_cycle_input_from_mapping",
    "manager_cycle_input_from_parts",
    "packet_is_claimable",
    "proof_obligations_for_cycle",
    "recompute_manager_readiness",
    "recompute_manager_readiness_from_mapping",
    "validate_manager_authority_classification",
)
