from models import AnalyzerInput, AnalyzerOutput
from normalize import normalize_system
from predicates import (
    evaluate_constraint_continuity,
    evaluate_object_continuity,
    evaluate_temporal_continuity,
    evaluate_authority_continuity,
    evaluate_executor_continuity,
)
from fixtures import suggest_fixtures


def analyze_continuity(data: AnalyzerInput) -> AnalyzerOutput:
    normalized = normalize_system(data.system_description)

    constraint_result, constraint_notes = evaluate_constraint_continuity(normalized)
    object_result, object_notes = evaluate_object_continuity(normalized)
    temporal_result, temporal_notes = evaluate_temporal_continuity(normalized)
    authority_result, authority_notes = evaluate_authority_continuity(normalized)
    executor_result, executor_notes = evaluate_executor_continuity(normalized)

    predicates = {
        "constraint_continuity": constraint_result,
        "object_continuity": object_result,
        "temporal_continuity": temporal_result,
        "authority_continuity": authority_result,
        "executor_continuity": executor_result,
    }

    statuses = [result.status for result in predicates.values()]

    if "fail" in statuses:
        classification = "receipt-strong / mutation-partial"
        summary = "Receipt validity is assumed externally, but one or more continuity predicates are not preserved through the execution path."
    elif all(status == "pass" for status in statuses):
        classification = "receipt-strong / mutation-strong"
        summary = "Receipt validity is assumed externally, and all implemented continuity predicates appear preserved through the execution path."
    else:
        classification = "receipt-strong / mutation-unknown"
        summary = "Receipt validity is assumed externally, but there is not enough information to evaluate all implemented continuity predicates confidently."

    suggested_fixtures = []
    suggested_fixtures.extend(
        suggest_fixtures("constraint_continuity", constraint_result.status)
    )
    suggested_fixtures.extend(
        suggest_fixtures("object_continuity", object_result.status)
    )
    suggested_fixtures.extend(
        suggest_fixtures("temporal_continuity", temporal_result.status)
    )
    suggested_fixtures.extend(
        suggest_fixtures("authority_continuity", authority_result.status)
    )
    suggested_fixtures.extend(
        suggest_fixtures("executor_continuity", executor_result.status)
    )

    deduped_fixtures = []
    seen = set()

    for item in suggested_fixtures:
        key = (
            item.get("fixture"),
            tuple(sorted(item.get("descriptor_dimensions", {}).items())),
        )
        if key not in seen:
            seen.add(key)
            deduped_fixtures.append(item)

    suggested_fixtures = deduped_fixtures

    return AnalyzerOutput(
        classification=classification,
        summary=summary,
        predicates=predicates,
        evidence_notes=(
            normalized.notes
            + constraint_notes
            + object_notes
            + temporal_notes
            + authority_notes
            + executor_notes
        ),
        suggested_fixtures=suggested_fixtures,
    )


if __name__ == "__main__":
    samples = [
        # Constraint failure
        AnalyzerInput(
            receipt={"receipt_id": "test-fail-123"},
            system_description=(
                "The system checks a max amount before approval, "
                "then later modifies the request parameters before the API call executes."
            ),
        ),

        # Clean pass
        AnalyzerInput(
            receipt={"receipt_id": "test-pass-456"},
            system_description=(
                "The system checks a max amount before approval, "
                "then sends the approved request directly to the API call without changes."
            ),
        ),

        # Unknown
        AnalyzerInput(
            receipt={"receipt_id": "test-unknown-789"},
            system_description=(
                "The system receives a request and processes it."
            ),
        ),

        # Object substitution (FAIL)
        AnalyzerInput(
            receipt={"receipt_id": "test-object-fail"},
            system_description=(
                "The system evaluates object A, but the API call executes on object B."
            ),
        ),

        # Same object (PASS)
        AnalyzerInput(
            receipt={"receipt_id": "test-object-pass"},
            system_description=(
                "The system evaluates the same object and executes on the same object."
            ),
        ),

        # Alias/remap (UNKNOWN)
        AnalyzerInput(
            receipt={"receipt_id": "test-object-alias"},
            system_description=(
                "The system evaluates object A, then maps it through an alias before execution."
            ),
        ),

        # Temporal failure
        AnalyzerInput(
            receipt={"receipt_id": "test-temporal-fail"},
            system_description=(
                "The system has an expires timestamp, but execution happens later after a delay."
            ),
        ),

        # Temporal likely pass
        AnalyzerInput(
            receipt={"receipt_id": "test-temporal-pass"},
            system_description=(
                "The system checks a timestamp and executes immediately before it expires."
            ),
        ),

        # Temporal unknown
        AnalyzerInput(
            receipt={"receipt_id": "test-temporal-unknown"},
            system_description=(
                "The system retries execution later."
            ),
        ),

        # Authority mixed / ambiguous
        AnalyzerInput(
            receipt={"receipt_id": "test-authority-mixed"},
            system_description=(
                "The system checks policy and delegation before approval, "
                "policy changed before execution, and it revalidates before execution."
            ),
        ),

        # Authority likely pass
        AnalyzerInput(
            receipt={"receipt_id": "test-authority-pass"},
            system_description=(
                "The system checks policy and delegation before approval "
                "and revalidates authority before execution."
            ),
        ),

        # Authority fail
        AnalyzerInput(
            receipt={"receipt_id": "test-authority-fail"},
            system_description=(
                "The system checks policy and delegation before approval, "
                "but policy changed before execution and it does not revalidate."
            ),
        ),

        # Executor failure
        AnalyzerInput(
            receipt={"receipt_id": "test-executor-fail"},
            system_description=(
                "An upstream gate checks the request, but the worker is an independent executor "
                "and the final executor does not enforce the condition."
            ),
        ),

        # Executor likely pass
        AnalyzerInput(
            receipt={"receipt_id": "test-executor-pass"},
            system_description=(
                "The downstream component is the executor, and the final component enforces "
                "the same condition before mutation."
            ),
        ),

        # Executor unknown
        AnalyzerInput(
            receipt={"receipt_id": "test-executor-unknown"},
            system_description=(
                "The worker is the downstream component, but enforcement at the final executor is not described."
            ),
        ),
    ]

    for i, sample in enumerate(samples, start=1):
        result = analyze_continuity(sample)
        print(f"\n--- SAMPLE {i} ---")
        print(result.model_dump_json(indent=2))