from models import PredicateResult


def evaluate_constraint_continuity(normalized_system) -> tuple[PredicateResult, list[str]]:
    """
    v0.1 rule-based evaluation for constraint continuity
    """

    has_constraints = len(normalized_system.approved_constraints) > 0
    has_transforms = len(normalized_system.parameter_transforms) > 0

    evidence_notes = []

    if has_constraints:
        evidence_notes.append("Constraint signal detected in the system description.")

    if has_transforms:
        evidence_notes.append("Parameter transformation signal detected downstream of the decision point.")

    if has_constraints and has_transforms:
        return (
            PredicateResult(
                status="fail",
                reason="Approved constraints may be modified or widened before execution.",
                confidence=0.9,
                confidence_basis="direct_evidence"
            ),
            evidence_notes,
        )

    if has_constraints and not has_transforms:
        evidence_notes.append("No downstream parameter transformation signal detected.")
        return (
            PredicateResult(
                status="pass",
                reason="Constraints detected with no evidence of downstream modification.",
                confidence=0.75,
                confidence_basis="strong_inference"
            ),
            evidence_notes,
        )

    evidence_notes.append("Insufficient information to determine whether constraints survive transit.")
    return (
        PredicateResult(
            status="unknown",
            reason="No clear constraint or transformation behavior detected.",
            confidence=0.5,
            confidence_basis="insufficient_information"
        ),
        evidence_notes,
    )


def evaluate_object_continuity(normalized_system) -> tuple[PredicateResult, list[str]]:
    """
    v0.1 rule-based evaluation for object continuity
    """

    attested = normalized_system.attested_objects
    mutated = normalized_system.mutated_objects
    aliases = normalized_system.object_aliases

    evidence_notes = []

    if attested:
        evidence_notes.append(f"Attested object signals detected: {attested}")

    if mutated:
        evidence_notes.append(f"Mutated object signals detected: {mutated}")

    if aliases:
        evidence_notes.append("Alias or remap signal detected in the execution path.")

    if "same_object" in attested and "same_object" in mutated and not aliases:
        return (
            PredicateResult(
                status="pass",
                reason="The same object appears to be attested and mutated with no aliasing signal.",
                confidence=0.9,
                confidence_basis="direct_evidence"
            ),
            evidence_notes,
        )

    if attested and mutated and attested != mutated:
        return (
            PredicateResult(
                status="fail",
                reason="The attested object and mutated object appear to differ.",
                confidence=0.9,
                confidence_basis="direct_evidence"
            ),
            evidence_notes,
        )

    if aliases:
        evidence_notes.append("Aliasing or remapping makes object continuity uncertain.")
        return (
            PredicateResult(
                status="unknown",
                reason="Object identity may be altered by aliasing or remapping.",
                confidence=0.6,
                confidence_basis="weak_inference"
            ),
            evidence_notes,
        )

    evidence_notes.append("Insufficient information to determine whether the same object reaches mutation.")
    return (
        PredicateResult(
            status="unknown",
            reason="No clear object continuity signals detected.",
            confidence=0.5,
            confidence_basis="insufficient_information"
        ),
        evidence_notes,
    )


def evaluate_temporal_continuity(normalized_system) -> tuple[PredicateResult, list[str]]:
    """
    v0.1 rule-based evaluation for temporal continuity

    This predicate asks:
    was the governing condition still valid at execution time?

    It is intentionally separate from executor continuity.
    Executor continuity asks whether the final mutation-capable component
    enforced the condition at all.
    Temporal continuity asks whether the condition remained fresh and valid
    by the time execution happened.
    """

    signals = normalized_system.temporal_signals
    evidence_notes = []

    if signals:
        evidence_notes.append(f"Temporal signals detected: {signals}")

    has_temporal_constraint = "temporal_constraint_detected" in signals
    has_delay = "delayed_execution_detected" in signals
    has_retry = "retry_or_replay_detected" in signals

    if has_temporal_constraint and (has_delay or has_retry):
        return (
            PredicateResult(
                status="fail",
                reason="Temporal validity may not survive to execution because delayed or replayed execution is present.",
                confidence=0.9,
                confidence_basis="direct_evidence"
            ),
            evidence_notes,
        )

    if has_temporal_constraint and not has_delay and not has_retry:
        evidence_notes.append("Temporal constraint detected with no delay or retry signal.")
        return (
            PredicateResult(
                status="pass",
                reason="Temporal validity appears preserved to execution.",
                confidence=0.75,
                confidence_basis="strong_inference"
            ),
            evidence_notes,
        )

    if has_delay or has_retry:
        evidence_notes.append("Execution timing risk detected, but no explicit freshness boundary is described.")
        return (
            PredicateResult(
                status="unknown",
                reason="Execution may be delayed or replayed, but temporal validity requirements are not clearly defined.",
                confidence=0.6,
                confidence_basis="weak_inference"
            ),
            evidence_notes,
        )

    evidence_notes.append("Insufficient information to determine whether validity remained fresh at mutation time.")
    return (
        PredicateResult(
            status="unknown",
            reason="No clear temporal continuity signals detected.",
            confidence=0.5,
            confidence_basis="insufficient_information"
        ),
        evidence_notes,
    )


def evaluate_authority_continuity(normalized_system) -> tuple[PredicateResult, list[str]]:
    """
    v0.1 rule-based evaluation for authority continuity
    """

    signals = normalized_system.authority_signals
    evidence_notes = []

    if signals:
        evidence_notes.append(f"Authority signals detected: {signals}")

    has_authority_constraint = "authority_constraint_detected" in signals
    has_drift = "authority_drift_detected" in signals
    has_revalidation = "authority_revalidation_detected" in signals

    if has_authority_constraint and has_drift and not has_revalidation:
        return (
            PredicateResult(
                status="fail",
                reason="Authority conditions appear to drift before execution without revalidation.",
                confidence=0.9,
                confidence_basis="direct_evidence"
            ),
            evidence_notes,
        )

    if has_authority_constraint and has_revalidation and not has_drift:
        evidence_notes.append("Authority constraint is present and revalidation is described.")
        return (
            PredicateResult(
                status="pass",
                reason="Authority validity appears preserved through revalidation.",
                confidence=0.75,
                confidence_basis="strong_inference"
            ),
            evidence_notes,
        )

    if has_drift and not has_revalidation:
        evidence_notes.append("Authority drift detected without clear revalidation step.")
        return (
            PredicateResult(
                status="unknown",
                reason="Authority may have changed before execution, but the control path is not fully described.",
                confidence=0.6,
                confidence_basis="weak_inference"
            ),
            evidence_notes,
        )

    evidence_notes.append("Insufficient information to determine whether authority remained valid at execution time.")
    return (
        PredicateResult(
            status="unknown",
            reason="No clear authority continuity signals detected.",
            confidence=0.5,
            confidence_basis="insufficient_information"
        ),
        evidence_notes,
    )


def evaluate_executor_continuity(normalized_system) -> tuple[PredicateResult, list[str]]:
    """
    v0.1 rule-based evaluation for executor continuity

    This predicate asks:
    did the final mutation-capable component enforce the governing condition?

    It is intentionally separate from temporal continuity.
    Temporal continuity covers stale state / drift between check and execution.
    Executor continuity covers whether the condition actually reached and bound
    the final executor rather than stopping at an upstream gate.
    """

    signals = normalized_system.executor_signals
    evidence_notes = []

    if signals:
        evidence_notes.append(f"Executor signals detected: {signals}")

    has_executor_component = "executor_component_detected" in signals
    has_enforcement = "executor_enforcement_detected" in signals
    has_upstream_gate = "upstream_gate_detected" in signals
    has_bypass = "executor_bypass_detected" in signals

    if has_executor_component and has_upstream_gate and has_bypass:
        return (
            PredicateResult(
                status="fail",
                reason="An upstream gate appears present, but the mutation-capable executor may bypass or fail to enforce the same condition.",
                confidence=0.9,
                confidence_basis="direct_evidence"
            ),
            evidence_notes,
        )

    if has_executor_component and has_enforcement and not has_bypass:
        evidence_notes.append("Final executor enforcement is explicitly described.")
        return (
            PredicateResult(
                status="pass",
                reason="The final mutation-capable component appears to enforce the same bound condition.",
                confidence=0.75,
                confidence_basis="strong_inference"
            ),
            evidence_notes,
        )

    if has_executor_component and not has_enforcement:
        evidence_notes.append("Executor component detected without explicit enforcement description.")
        return (
            PredicateResult(
                status="unknown",
                reason="A mutation-capable executor is present, but it is unclear whether it enforces the same governing condition.",
                confidence=0.6,
                confidence_basis="weak_inference"
            ),
            evidence_notes,
        )

    if has_upstream_gate and not has_executor_component:
        evidence_notes.append("Upstream validation is described, but final executor behavior is not.")
        return (
            PredicateResult(
                status="unknown",
                reason="Upstream gate behavior is visible, but executor continuity cannot be established from the described system.",
                confidence=0.6,
                confidence_basis="weak_inference"
            ),
            evidence_notes,
        )

    evidence_notes.append("Insufficient information to determine whether the final mutation-capable component enforced the same bound condition.")
    return (
        PredicateResult(
            status="unknown",
            reason="No clear executor continuity signals detected.",
            confidence=0.5,
            confidence_basis="insufficient_information"
        ),
        evidence_notes,
    )