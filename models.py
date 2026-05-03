from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

PredicateStatus = Literal["pass", "fail", "unknown"]
SubjectType = Literal["agent", "workflow", "delegation", "action"]
MutationEventType = Literal[
    "object_changed",
    "constraint_changed",
    "temporal_expired",
    "authority_changed",
    "executor_changed",
    "refusal_unavailable",
]


class Subject(BaseModel):
    subject_id: str
    subject_type: SubjectType


class InputReceipt(BaseModel):
    receipt_id: str
    issuer: str
    signal_type: str
    digest: str
    prior_signal_digest: str | None = None
    canonicalization_profile: str
    signed_payload: dict[str, Any]
    signature: dict[str, Any]


class ExecutionPath(BaseModel):
    action_id: str
    requested_action: dict[str, Any]
    admitted_action: dict[str, Any]
    executed_action: dict[str, Any]
    mutation_boundary_ts: datetime
    executor_id: str
    execution_environment: dict[str, Any] | None = None


class MutationEvent(BaseModel):
    event_id: str
    event_type: MutationEventType
    before: dict[str, Any]
    after: dict[str, Any]
    timestamp: datetime
    evidence_ref: str | None = None


class EvaluationContext(BaseModel):
    evaluated_at: datetime
    policy_ref: str | None = None
    expected_verifier_id: str


class AnalyzerInput(BaseModel):
    schema_version: Literal["0.1"]
    subject: Subject
    receipts: list[InputReceipt]
    execution_path: ExecutionPath
    mutation_events: list[MutationEvent] = Field(default_factory=list)
    evaluation_context: EvaluationContext


class PredicateOutcome(BaseModel):
    status: PredicateStatus
    evidence_refs: list[str] = Field(default_factory=list)


class ExecutorPredicateOutcome(PredicateOutcome):
    mechanical_refusal_at_mutation_time: Literal["true", "false", "unknown"]


class ChainCompleteInput(BaseModel):
    continuity_receipt_id: str
    sar_receipt_id: str
    sar_verdict: Literal["PASS", "FAIL", "INDETERMINATE"]
    sar_issued_at: datetime
