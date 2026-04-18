def suggest_fixtures(predicate_name: str, status: str) -> list[dict]:
    if predicate_name == "constraint_continuity":
        if status in ("fail", "unknown"):
            return [
                {
                    "fixture": "parameter_widening_in_transit",
                    "descriptor_dimensions": {
                        "invariant_survival": "pre_action"
                    },
                }
            ]

    if predicate_name == "object_continuity":
        if status in ("fail", "unknown"):
            return [
                {
                    "fixture": "object_substitution",
                    "descriptor_dimensions": {
                        "invariant_survival": "pre_action"
                    },
                }
            ]

    if predicate_name == "temporal_continuity":
        if status in ("fail", "unknown"):
            return [
                {
                    "fixture": "stale_verdict_at_mutation_time",
                    "descriptor_dimensions": {
                        "invariant_survival": "pre_action_vs_post_action"
                    },
                }
            ]

    if predicate_name == "authority_continuity":
        if status in ("fail", "unknown"):
            return [
                {
                    "fixture": "async_retry_after_drift",
                    "descriptor_dimensions": {
                        "refusal_authority": "grantor_enforced"
                    },
                }
            ]

    if predicate_name == "executor_continuity":
        if status in ("fail", "unknown"):
            return [
                {
                    "fixture": "proxy_executor_mismatch",
                    "descriptor_dimensions": {
                        "refusal_authority": "infrastructure_enforced"
                    },
                }
            ]

    return []