from __future__ import annotations

from datetime import datetime
from typing import Any

from models import ExecutorPredicateOutcome, PredicateOutcome

IDENTITY_FIELDS = ("target_id", "object_id", "resource_id", "subject_ref")


def evaluate_object_continuity(requested_action: dict[str, Any], executed_action: dict[str, Any], mutation_events: list[dict[str, Any]]) -> PredicateOutcome:
    evidence = [e.get("evidence_ref") for e in mutation_events if e.get("event_type") == "object_changed" and e.get("evidence_ref")]
    present = False
    for field in IDENTITY_FIELDS:
        req_val = requested_action.get(field)
        exe_val = executed_action.get(field)
        if req_val is not None or exe_val is not None:
            present = True
            if req_val != exe_val:
                return PredicateOutcome(status="fail", evidence_refs=evidence)
    if present:
        return PredicateOutcome(status="pass", evidence_refs=evidence)
    return PredicateOutcome(status="unknown", evidence_refs=evidence)


def evaluate_constraint_continuity(admitted_action: dict[str, Any], executed_action: dict[str, Any], mutation_events: list[dict[str, Any]]) -> PredicateOutcome:
    evidence = [e.get("evidence_ref") for e in mutation_events if e.get("event_type") == "constraint_changed" and e.get("evidence_ref")]
    admitted_constraints = admitted_action.get("constraints")
    executed_constraints = executed_action.get("constraints")
    if admitted_constraints is not None or executed_constraints is not None:
        if admitted_constraints is None or executed_constraints is None:
            return PredicateOutcome(status="fail", evidence_refs=evidence)
        return PredicateOutcome(status="pass", evidence_refs=evidence) if admitted_constraints == executed_constraints else PredicateOutcome(status="fail", evidence_refs=evidence)

    common_fields = ["amount", "max_amount", "spend_limit", "scope", "allowed_action", "capability"]
    compared_any = False
    for field in common_fields:
        a_val = admitted_action.get(field)
        e_val = executed_action.get(field)
        if a_val is None and e_val is None:
            continue
        compared_any = True
        if a_val != e_val:
            return PredicateOutcome(status="fail", evidence_refs=evidence)

    if compared_any:
        return PredicateOutcome(status="pass", evidence_refs=evidence)
    return PredicateOutcome(status="unknown", evidence_refs=evidence)


def evaluate_temporal_continuity(receipts: list[dict[str, Any]], mutation_boundary_ts: datetime, policy_ref: str | None, mutation_events: list[dict[str, Any]]) -> PredicateOutcome:
    evidence = [e.get("evidence_ref") for e in mutation_events if e.get("event_type") == "temporal_expired" and e.get("evidence_ref")]
    has_windows = False
    for receipt in receipts:
        payload = receipt.get("signed_payload", {})
        vfrom = payload.get("valid_from")
        vuntil = payload.get("valid_until")
        if vfrom is None and vuntil is None:
            continue
        has_windows = True
        try:
            from_dt = datetime.fromisoformat(vfrom.replace("Z", "+00:00")) if vfrom else None
            until_dt = datetime.fromisoformat(vuntil.replace("Z", "+00:00")) if vuntil else None
        except Exception:
            return PredicateOutcome(status="unknown", evidence_refs=evidence)
        if from_dt and mutation_boundary_ts < from_dt:
            return PredicateOutcome(status="fail", evidence_refs=evidence)
        if until_dt and mutation_boundary_ts > until_dt:
            return PredicateOutcome(status="fail", evidence_refs=evidence)
    if has_windows:
        return PredicateOutcome(status="pass", evidence_refs=evidence)
    if policy_ref and "freshness" in policy_ref.lower():
        return PredicateOutcome(status="unknown", evidence_refs=evidence)
    return PredicateOutcome(status="pass", evidence_refs=evidence)


def evaluate_authority_continuity(receipts: list[dict[str, Any]], mutation_boundary_ts: datetime, mutation_events: list[dict[str, Any]]) -> PredicateOutcome:
    evidence = [e.get("evidence_ref") for e in mutation_events if e.get("event_type") == "authority_changed" and e.get("evidence_ref")]
    by_digest = {r.get("digest"): r for r in receipts if r.get("digest")}
    roots = 0
    for r in receipts:
        prior = r.get("prior_signal_digest")
        if prior is None:
            roots += 1
        elif prior not in by_digest:
            return PredicateOutcome(status="unknown", evidence_refs=evidence)
    authority_changed = any(e.get("event_type") == "authority_changed" for e in mutation_events)
    if authority_changed:
        for r in receipts:
            payload = r.get("signed_payload", {})
            rev = payload.get("revalidated_at")
            if rev:
                try:
                    rev_dt = datetime.fromisoformat(rev.replace("Z", "+00:00"))
                    if rev_dt <= mutation_boundary_ts:
                        return PredicateOutcome(status="pass", evidence_refs=evidence)
                except Exception:
                    continue
        return PredicateOutcome(status="fail", evidence_refs=evidence)
    if roots >= 1:
        return PredicateOutcome(status="pass", evidence_refs=evidence)
    return PredicateOutcome(status="unknown", evidence_refs=evidence)


def evaluate_executor_continuity(admitted_action: dict[str, Any], executed_action: dict[str, Any], mutation_events: list[dict[str, Any]]) -> ExecutorPredicateOutcome:
    evidence = [e.get("evidence_ref") for e in mutation_events if e.get("event_type") == "refusal_unavailable" and e.get("evidence_ref")]
    if any(e.get("event_type") == "refusal_unavailable" for e in mutation_events):
        return ExecutorPredicateOutcome(status="fail", evidence_refs=evidence, mechanical_refusal_at_mutation_time="false")
    if admitted_action == executed_action:
        return ExecutorPredicateOutcome(status="pass", evidence_refs=evidence, mechanical_refusal_at_mutation_time="true")
    if admitted_action and executed_action:
        return ExecutorPredicateOutcome(status="unknown", evidence_refs=evidence, mechanical_refusal_at_mutation_time="unknown")
    return ExecutorPredicateOutcome(status="unknown", evidence_refs=evidence, mechanical_refusal_at_mutation_time="unknown")


def classify(predicates: dict[str, PredicateOutcome | ExecutorPredicateOutcome]) -> str:
    statuses = [p.status for p in predicates.values()]
    if all(s == "pass" for s in statuses):
        return "mutation_strong"
    if any(s == "fail" for s in statuses):
        return "mutation_partial"
    return "mutation_unknown"
