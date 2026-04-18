from models import NormalizedSystem


def normalize_system(system_description: str) -> NormalizedSystem:
    """
    Very simple v0.1 normalizer.
    For now, just captures raw signals from text.
    Later we can upgrade this with LLM parsing.
    """

    text = system_description.lower()

    approved_constraints = []
    downstream_actions = []
    parameter_transforms = []

    attested_objects = []
    mutated_objects = []
    object_aliases = []

    notes = []

    # Constraint signals
    if "limit" in text or "max" in text:
        approved_constraints.append("constraint_detected")

    # Execution signals
    if "api call" in text or "execute" in text or "send" in text:
        downstream_actions.append("downstream_execution_detected")

    # Parameter transform signals
    if (
        "modify" in text
        or "modifies" in text
        or "modified" in text
        or "transform" in text
        or "transforms" in text
        or "adjust" in text
        or "adjusts" in text
        or "rewrite" in text
        or "rewrites" in text
    ):
        parameter_transforms.append("parameter_transform_detected")

    # Async / timing notes
    if "queue" in text or "retry" in text:
        notes.append("async_behavior_detected")

    # Object continuity signals
    if "object a" in text or "target a" in text or "record a" in text:
        attested_objects.append("object_a")

    if "object b" in text or "target b" in text or "record b" in text:
        mutated_objects.append("object_b")

    if "same object" in text or "same target" in text or "same record" in text:
        attested_objects.append("same_object")
        mutated_objects.append("same_object")

    if "alias" in text or "remap" in text or "mapped" in text:
        object_aliases.append("alias_or_remap_detected")

    temporal_signals = []

    if "time" in text or "timestamp" in text or "expires" in text:
        temporal_signals.append("temporal_constraint_detected")

    if "delay" in text or "later" in text or "after" in text:
        temporal_signals.append("delayed_execution_detected")

    if "retry" in text or "replay" in text:
        temporal_signals.append("retry_or_replay_detected")

    authority_signals = []

    if "policy" in text or "delegation" in text or "revocation" in text:
        authority_signals.append("authority_constraint_detected")

    if "revoked" in text or "policy changed" in text or "delegation changed" in text:
        authority_signals.append("authority_drift_detected")

    if "revalidate" in text or "re-check" in text or "recheck" in text:
        authority_signals.append("authority_revalidation_detected")

    executor_signals = []

    if "executor" in text or "worker" in text or "downstream component" in text:
        executor_signals.append("executor_component_detected")

    if "final executor enforces" in text or "mutation-capable component enforces" in text or "final component enforces" in text:
        executor_signals.append("executor_enforcement_detected")

    if "upstream gate" in text or "gateway checks" in text or "checked upstream" in text:
        executor_signals.append("upstream_gate_detected")

    if "bypass" in text or "independent executor" in text or "final executor does not enforce" in text:
        executor_signals.append("executor_bypass_detected")

    return NormalizedSystem(
        approved_constraints=approved_constraints,
        downstream_actions=downstream_actions,
        parameter_transforms=parameter_transforms,
        attested_objects=attested_objects,
        mutated_objects=mutated_objects,
        temporal_signals=temporal_signals,
        object_aliases=object_aliases,
        authority_signals=authority_signals,
        executor_signals=executor_signals,
        notes=notes,
    )