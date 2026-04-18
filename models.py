from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field


PredicateStatus = Literal["pass", "fail", "unknown"]
ConfidenceBasis = Literal[
    "direct_evidence",
    "strong_inference",
    "weak_inference",
    "insufficient_information",
]


class AnalyzerInput(BaseModel):
    receipt: dict = Field(..., description="Already-verified receipt object")
    system_description: str = Field(..., description="Plain-English system description")
    execution_trace: Optional[dict] = Field(default=None)
    policy_context: Optional[dict] = Field(default=None)
    mutation_boundary: Optional[str] = Field(default=None)


class NormalizedSystem(BaseModel):
    decision_point: Optional[str] = None
    mutation_boundary: Optional[str] = None

    approved_constraints: list[str] = Field(default_factory=list)
    downstream_actions: list[str] = Field(default_factory=list)
    parameter_transforms: list[str] = Field(default_factory=list)

    attested_objects: list[str] = Field(default_factory=list)
    mutated_objects: list[str] = Field(default_factory=list)
    object_aliases: list[str] = Field(default_factory=list)

    temporal_signals: list[str] = Field(default_factory=list)
    authority_signals: list[str] = Field(default_factory=list)
    executor_signals: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class PredicateResult(BaseModel):
    status: PredicateStatus
    reason: str
    confidence: float
    confidence_basis: ConfidenceBasis


class AnalyzerOutput(BaseModel):
    receipt_verification: Literal["assumed_external"] = "assumed_external"
    classification: str
    summary: str
    predicates: dict[str, PredicateResult]
    evidence_notes: list[str] = Field(default_factory=list)
    suggested_fixtures: list[dict] = Field(default_factory=list)