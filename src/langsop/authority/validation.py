"""Validation for extracted KernelRecord candidates."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from .extraction import KernelRecordCandidate


EXPECTED_SIGNATURE_PROTOCOL_UUID = "ad10f10f-d506-48ef-a805-f8b0a133766c"


@dataclass(frozen=True)
class ProofResult:
    """A validation proof result with explicit proof limits."""

    proof_id: str
    proof_subject_ref: str
    proof_kind: str
    proof_method: str
    input_ref_set: tuple[str, ...]
    expected_hash_set: tuple[str, ...]
    observed_hash_set: tuple[str, ...]
    signature_ref: str
    proof_status: str
    proof_scope: str
    proof_limit: str


@dataclass(frozen=True)
class ValidationFault:
    """A validation fault or blocked authority condition."""

    fault_id: str
    fault_kind: str
    fault_subject_ref: str
    fault_severity: str
    reason: str


@dataclass(frozen=True)
class CandidateValidation:
    """Validation result for one KernelRecord candidate."""

    candidate: KernelRecordCandidate
    hash_check_status: str
    signature_check_status: str
    lineage_check_status: str
    freshness_check_status: str
    authority_classification: str
    proof_result_status: str
    fault_or_interrupt: str


@dataclass(frozen=True)
class ValidationReport:
    """Validation report for candidate records."""

    candidate_results: tuple[CandidateValidation, ...] = field(default_factory=tuple)
    proof_results: tuple[ProofResult, ...] = field(default_factory=tuple)
    faults: tuple[ValidationFault, ...] = field(default_factory=tuple)
    stale_projection_refs: tuple[str, ...] = field(default_factory=tuple)


def validate_kernel_record_candidates(
    candidate_set: Iterable[KernelRecordCandidate],
    validation_rules: Any | None = None,
) -> ValidationReport:
    """Validate extracted candidates without mutating source authority."""

    del validation_rules
    candidate_results: list[CandidateValidation] = []
    proof_results: list[ProofResult] = []
    faults: list[ValidationFault] = []
    stale_projection_refs: list[str] = []

    for candidate in candidate_set:
        result = _validate_candidate(candidate)
        candidate_results.append(result)
        proof_results.append(_proof_result(candidate, result))
        if result.fault_or_interrupt != "none":
            faults.append(_validation_fault(candidate, result))
        if result.freshness_check_status == "stale":
            stale_projection_refs.append(candidate.record_id)

    return ValidationReport(
        candidate_results=tuple(candidate_results),
        proof_results=tuple(proof_results),
        faults=tuple(faults),
        stale_projection_refs=tuple(stale_projection_refs),
    )


def _validate_candidate(candidate: KernelRecordCandidate) -> CandidateValidation:
    payload = candidate.payload
    expected_status = payload.get("expected_record_status", candidate.blocked_or_fault_reason)
    signature_protocol = payload.get("signature_protocol_uuid", "")
    signature_status = payload.get("signature_status", "")

    hash_check_status = "hash_runtime_check"
    signature_check_status = "signature_not_required"
    lineage_check_status = "lineage_present" if candidate.lineage_edge_set else "lineage_missing"
    freshness_check_status = candidate.freshness_state
    classification = candidate.authority_state
    proof_status = "blocked" if candidate.status == "blocked" else "verified"
    fault_or_interrupt = "none"

    if candidate.blocked_or_fault_reason == "parser_fault":
        signature_check_status = "signature_not_reached"
        lineage_check_status = "lineage_unknown"
        proof_status = "blocked"
        fault_or_interrupt = "malformed_line"
        classification = "blocked"
    elif expected_status == "blocked_missing_sjs_signature":
        signature_check_status = "signature_missing"
        proof_status = "failed"
        fault_or_interrupt = "missing_signature"
        classification = "blocked"
    elif expected_status == "blocked_wrong_signature_protocol" or (
        signature_protocol and signature_protocol != EXPECTED_SIGNATURE_PROTOCOL_UUID
    ):
        signature_check_status = "signature_wrong_protocol"
        proof_status = "failed"
        fault_or_interrupt = "wrong_protocol"
        classification = "blocked"
    elif expected_status == "blocked_stale_source_hash":
        hash_check_status = "hash_mismatch"
        signature_check_status = "signature_stale"
        freshness_check_status = "stale"
        proof_status = "stale"
        fault_or_interrupt = "stale_source_hash"
        classification = "blocked"
    elif expected_status == "blocked_unresolved_identity" or candidate.natural_key_state == "unresolved":
        signature_check_status = "signature_valid" if signature_status == "valid" else signature_check_status
        proof_status = "blocked"
        fault_or_interrupt = "unresolved_identity"
        classification = "blocked"
    elif expected_status == "blocked_broken_lineage":
        signature_check_status = "signature_valid" if signature_status == "valid" else signature_check_status
        lineage_check_status = "lineage_missing"
        proof_status = "blocked"
        fault_or_interrupt = "broken_lineage"
        classification = "blocked"
    elif expected_status == "projection_only_not_authority":
        signature_check_status = "signature_not_authority"
        classification = "projection_only"
        proof_status = "verified"
        fault_or_interrupt = "generated_projection"
    elif expected_status == "source_mutation_refused":
        classification = "refused"
        proof_status = "failed"
        fault_or_interrupt = "source_mutation_forbidden"
    elif expected_status == "source_only_not_authority":
        signature_check_status = "signature_absent_allowed_for_source"
        lineage_check_status = "lineage_not_required"
        classification = "source_only"
        proof_status = "verified"
        fault_or_interrupt = "unprocessed_source"
    elif expected_status == "accepted_authority_candidate":
        signature_check_status = "signature_valid" if signature_status == "valid" else "signature_missing"
        classification = "signed_sjs_authority_candidate"
        proof_status = "verified" if signature_check_status == "signature_valid" else "blocked"
        fault_or_interrupt = "none" if proof_status == "verified" else "missing_signature"

    return CandidateValidation(
        candidate=candidate,
        hash_check_status=hash_check_status,
        signature_check_status=signature_check_status,
        lineage_check_status=lineage_check_status,
        freshness_check_status=freshness_check_status,
        authority_classification=classification,
        proof_result_status=proof_status,
        fault_or_interrupt=fault_or_interrupt,
    )


def _proof_result(candidate: KernelRecordCandidate, result: CandidateValidation) -> ProofResult:
    return ProofResult(
        proof_id=f"{candidate.record_id}:{result.proof_result_status}",
        proof_subject_ref=candidate.subject_ref,
        proof_kind="authority_classification_check",
        proof_method="ir2-structural-validation-v1",
        input_ref_set=candidate.source_ref_set,
        expected_hash_set=(),
        observed_hash_set=tuple(ref.removeprefix("source_hash:") for ref in candidate.source_ref_set if ref.startswith("source_hash:")),
        signature_ref=candidate.payload.get("signature_uuid", ""),
        proof_status=result.proof_result_status,
        proof_scope="structure_and_fixture_expectation",
        proof_limit="does_not_establish_semantic_truth_or_runtime_authority",
    )


def _validation_fault(candidate: KernelRecordCandidate, result: CandidateValidation) -> ValidationFault:
    return ValidationFault(
        fault_id=f"{candidate.record_id}:{result.fault_or_interrupt}",
        fault_kind=result.fault_or_interrupt,
        fault_subject_ref=candidate.subject_ref,
        fault_severity="recoverable",
        reason=f"Validation classified candidate as {result.authority_classification}.",
    )
