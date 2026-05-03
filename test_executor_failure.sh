#!/bin/bash
set -euo pipefail
curl -sS -X POST http://127.0.0.1:3002/continuity/evaluate \
  -H "Content-Type: application/json" \
  -d @- <<'JSON'
{
  "schema_version": "0.1",
  "subject": {"subject_id": "subj-1", "subject_type": "action"},
  "receipts": [{
    "receipt_id": "r1",
    "issuer": "issuer",
    "signal_type": "delegation",
    "digest": "d1",
    "prior_signal_digest": null,
    "canonicalization_profile": "JCS",
    "signed_payload": {},
    "signature": {}
  }],
  "execution_path": {
    "action_id": "act-1",
    "requested_action": {"target_id":"A"},
    "admitted_action": {"amount": 10},
    "executed_action": {"amount": 10},
    "mutation_boundary_ts": "2026-05-03T00:00:00Z",
    "executor_id": "exec-1",
    "execution_environment": null
  },
  "mutation_events": [{
    "event_id": "e1",
    "event_type": "refusal_unavailable",
    "before": {},
    "after": {},
    "timestamp": "2026-05-03T00:00:00Z",
    "evidence_ref": "ev:1"
  }],
  "evaluation_context": {
    "evaluated_at": "2026-05-03T00:00:00Z",
    "policy_ref": null,
    "expected_verifier_id": "defaultverifier-continuity-v1"
  }
}
JSON
echo
