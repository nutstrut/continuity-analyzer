from __future__ import annotations

import base64
import fcntl
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jcs
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI, HTTPException, Request

from models import AnalyzerInput, ChainCompleteInput
from predicates import (
    classify,
    evaluate_authority_continuity,
    evaluate_constraint_continuity,
    evaluate_executor_continuity,
    evaluate_object_continuity,
    evaluate_temporal_continuity,
)

CONTINUITY_EVALUATION_FEE_USD = 0.001
CHAIN_COMPLETION_FEE_USD = 0.001
FEE_ENFORCEMENT_ENABLED = False

SERVICE = "continuity-analyzer"
VERSION = "0.1"
SCHEMA_VERSION = "0.1"
VERIFIER_ID = "defaultverifier-continuity-v1"
KID = "continuity-prod-ed25519-01"

BASE_DIR = Path(__file__).resolve().parent
CONTINUITY_LEDGER = BASE_DIR / "continuity_events_master.jsonl"
CHAIN_LEDGER = BASE_DIR / "chain_events_master.jsonl"
KEY_PATH = BASE_DIR / "keys" / f"{KID}.json"

app = FastAPI(title=SERVICE, version=VERSION)


def iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canonical_bytes(data: dict[str, Any]) -> bytes:
    return jcs.canonicalize(data)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def receipt_id_for(data: dict[str, Any]) -> str:
    return "sha256:" + sha256_hex(canonical_bytes(data))


def ensure_keypair() -> dict[str, Any]:
    KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    if KEY_PATH.exists():
        return json.loads(KEY_PATH.read_text())
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()
    private_raw = priv.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
    public_raw = pub.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    keydoc = {
        "kid": KID,
        "alg": "EdDSA",
        "crv": "Ed25519",
        "created_at": iso_now(),
        "private_key_b64": base64.b64encode(private_raw).decode(),
        "public_key_b64": base64.b64encode(public_raw).decode(),
    }
    KEY_PATH.write_text(json.dumps(keydoc, separators=(",", ":")) + "\n")
    return keydoc


def sign_digest(digest_bytes: bytes) -> str:
    keydoc = ensure_keypair()
    priv = Ed25519PrivateKey.from_private_bytes(base64.b64decode(keydoc["private_key_b64"]))
    sig = priv.sign(digest_bytes)
    return sig.hex()


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            f.write(json.dumps(record, separators=(",", ":"), ensure_ascii=False) + "\n")
            f.flush()
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def latency_bucket(seconds: float) -> str:
    if seconds < 1:
        return "sub_second"
    if seconds < 60:
        return "seconds"
    if seconds < 3600:
        return "minutes"
    if seconds < 86400:
        return "hours"
    return "days"


@app.post("/continuity/evaluate")
def evaluate(payload: AnalyzerInput):
    ensure_keypair()
    if not payload.evaluation_context.expected_verifier_id or payload.evaluation_context.expected_verifier_id != VERIFIER_ID:
        raise HTTPException(status_code=400, detail="unexpected verifier_id")
    p = payload.model_dump(mode="json", by_alias=True)
    pred_obj = evaluate_object_continuity(p["execution_path"]["requested_action"], p["execution_path"]["executed_action"], p["mutation_events"])
    pred_con = evaluate_constraint_continuity(p["execution_path"]["admitted_action"], p["execution_path"]["executed_action"], p["mutation_events"])
    mut_ts = datetime.fromisoformat(p["execution_path"]["mutation_boundary_ts"].replace("Z", "+00:00"))
    pred_tmp = evaluate_temporal_continuity(p["receipts"], mut_ts, p["evaluation_context"].get("policy_ref"), p["mutation_events"])
    pred_auth = evaluate_authority_continuity(p["receipts"], mut_ts, p["mutation_events"])
    pred_exec = evaluate_executor_continuity(p["execution_path"]["admitted_action"], p["execution_path"]["executed_action"], p["mutation_events"])
    predicates = {
        "object_continuity": pred_obj.model_dump(),
        "constraint_continuity": pred_con.model_dump(),
        "temporal_continuity": pred_tmp.model_dump(),
        "authority_continuity": pred_auth.model_dump(),
        "executor_continuity": pred_exec.model_dump(),
    }
    classification = classify({"o": pred_obj, "c": pred_con, "t": pred_tmp, "a": pred_auth, "e": pred_exec})

    input_canon = canonical_bytes(p)
    input_digest = "sha256:" + sha256_hex(input_canon)

    core = {
        "receipt_type": "continuity_receipt",
        "schema_version": SCHEMA_VERSION,
        "issued_at": iso_now(),
        "subject": p["subject"],
        "classification": classification,
        "predicates": predicates,
        "rationale": (
            "executor_continuity failed: refusal_unavailable event detected; "
            "mechanical refusal was not present at mutation boundary. "
            "All other predicates passed."
            if predicates["executor_continuity"]["status"] == "fail"
            and all(
                predicates[k]["status"] == "pass"
                for k in [
                    "object_continuity",
                    "constraint_continuity",
                    "temporal_continuity",
                    "authority_continuity",
                ]
            )
            else f"classification={classification}"
        ),
        "input_digest": input_digest,
        "sar_binding": None,
        "verifier": {
            "verifier_id": VERIFIER_ID,
            "verifier_kid": KID,
            "canonicalization_profile": "JCS",
        },
        "_ext": {
            "billing": {
                "fee_schedule": {
                    "continuity_evaluation_usd": "0.001",
                    "chain_completion_usd": "0.001",
                },
                "currency": "USD",
                "enforcement_status": "declared_not_enforced",
            }
        },
    }
    # Deterministic ordering:
    # 1) receipt_id = SHA-256(JCS(core_without_receipt_id_this_signal_digest_signature))
    # 2) this_signal_digest = SHA-256(JCS(core + receipt_id), still without signature)
    # 3) signature = Ed25519(sign SHA-256 digest bytes of JCS(core + receipt_id + this_signal_digest), excluding signature)
    rid = receipt_id_for(core)
    this_signal_digest = "sha256:" + sha256_hex(canonical_bytes({**core, "receipt_id": rid}))
    digest_bytes = hashlib.sha256(canonical_bytes({**core, "receipt_id": rid, "this_signal_digest": this_signal_digest})).digest()
    signature = sign_digest(digest_bytes)

    receipt = {**core, "receipt_id": rid, "this_signal_digest": this_signal_digest, "signature": signature}

    continuity_event = {
        "receipt_id": rid,
        "event_type": "continuity_issued",
        "issued_at": core["issued_at"],
        "subject_id": p["subject"]["subject_id"],
        "subject_type": p["subject"]["subject_type"],
        "classification": classification,
        "predicates": predicates,
        "rationale": core["rationale"],
        "scenario_digest": input_digest,
        "verifier_kid": KID,
        "input_digest": input_digest,
        "this_signal_digest": this_signal_digest,
        "canonicalization_profile": "JCS",
        "sar_binding": None,
        "chain_id": f"pending:{rid}",
    }

    chain_pending = {
        "chain_id": f"pending:{rid}",
        "event_type": "chain_pending",
        "continuity_receipt_id": rid,
        "sar_receipt_id": None,
        "chain_status": "pending",
        "continuity_issued_at": core["issued_at"],
        "sar_issued_at": None,
        "time_delta_seconds": None,
        "chain_latency_bucket": None,
        "verdict_correlation": None,
        "prior_signal_digest": p["receipts"][-1]["digest"] if p["receipts"] else None,
        "continuity_classification": classification,
        "sar_verdict": None,
        "predicate_failure_vector": [k for k, v in predicates.items() if v["status"] == "fail"],
        "executor_continuity_status": predicates["executor_continuity"]["status"],
    }
    append_jsonl(CHAIN_LEDGER, chain_pending)

    continuity_event["full_receipt"] = receipt
    append_jsonl(CONTINUITY_LEDGER, continuity_event)
    return receipt


@app.get("/continuity/receipt/{receipt_id}")
def get_receipt(receipt_id: str):
    matches = [r for r in read_jsonl(CONTINUITY_LEDGER) if r.get("receipt_id") == receipt_id]
    if not matches:
        raise HTTPException(status_code=404, detail="receipt not found")
    return matches[-1].get("full_receipt", matches[-1])


@app.get("/continuity/chain/{chain_id}")
def get_chain(chain_id: str):
    matches = [r for r in read_jsonl(CHAIN_LEDGER) if r.get("chain_id") == chain_id]
    if not matches:
        raise HTTPException(status_code=404, detail="chain not found")
    latest = matches[-1]
    return latest


@app.get("/.well-known/continuity-keys.json")
def key_registry():
    key = ensure_keypair()
    return {"keys": [{"kid": key["kid"], "alg": key["alg"], "crv": key["crv"], "public_key_b64": key["public_key_b64"], "created_at": key["created_at"], "status": "active"}]}


@app.get("/continuity/metrics/summary")
def metrics_summary():
    crecs = read_jsonl(CONTINUITY_LEDGER)
    chrecs = read_jsonl(CHAIN_LEDGER)
    latest_c = {}
    for r in crecs:
        latest_c[r["receipt_id"]] = r
    latest_chain = {}
    for r in chrecs:
        key = r["chain_id"] or f"pending:{r['continuity_receipt_id']}"
        latest_chain[key] = r
    class_breakdown = {"mutation_strong": 0, "mutation_partial": 0, "mutation_unknown": 0}
    fail_freq = {"object_continuity": 0, "constraint_continuity": 0, "temporal_continuity": 0, "authority_continuity": 0, "executor_continuity": 0}
    exec_fail = 0
    for r in latest_c.values():
        c = r.get("classification")
        if c in class_breakdown:
            class_breakdown[c] += 1
        preds = r.get("predicates", {})
        for k in fail_freq:
            if preds.get(k, {}).get("status") == "fail":
                fail_freq[k] += 1
        if preds.get("executor_continuity", {}).get("status") == "fail":
            exec_fail += 1
    total = len(latest_c)
    pending = sum(1 for r in latest_chain.values() if r.get("chain_status") == "pending")
    complete = sum(1 for r in latest_chain.values() if r.get("chain_status") == "complete")
    return {
        "total_continuity_receipts": total,
        "total_chains": len(latest_chain),
        "chains_pending": pending,
        "chains_complete": complete,
        "classification_breakdown": class_breakdown,
        "predicate_failure_frequency": fail_freq,
        "executor_continuity_fail_rate": (exec_fail / total) if total else 0.0,
    }


@app.get("/continuity/manifest")
def manifest():
    return {
        "service": "continuity-analyzer",
        "version": "0.1",
        "schema_version": "0.1",
        "receipt_type": "continuity_receipt",
        "verifier_id": "defaultverifier-continuity-v1",
        "signing_key": "continuity-prod-ed25519-01",
        "signature_algorithm": "Ed25519",
        "canonicalization_profile": "JCS",
        "digest_algorithm": "SHA-256",
        "endpoints": [
            "POST /continuity/evaluate",
            "GET /continuity/receipt/{receipt_id}",
            "GET /continuity/chain/{chain_id}",
            "GET /.well-known/continuity-keys.json",
            "GET /continuity/metrics/summary",
            "GET /continuity/manifest",
            "GET /healthz",
        ],
        "predicates": ["object_continuity", "constraint_continuity", "temporal_continuity", "authority_continuity", "executor_continuity"],
        "classification_outputs": ["mutation_strong", "mutation_partial", "mutation_unknown"],
        "chain_support": True,
        "sar_binding_support": True,
    }


@app.get("/healthz")
def healthz():
    return {"status": "ok", "service": "continuity-analyzer", "version": "0.1"}


@app.post("/continuity/internal/chain-complete")
def chain_complete(payload: ChainCompleteInput, request: Request):
    if request.client is None or request.client.host not in {"127.0.0.1", "::1"}:
        raise HTTPException(status_code=403, detail="internal endpoint only")
    chains = read_jsonl(CHAIN_LEDGER)
    pending = [r for r in chains if r.get("continuity_receipt_id") == payload.continuity_receipt_id]
    if not pending:
        raise HTTPException(status_code=404, detail="continuity receipt chain pending record not found")
    last = pending[-1]
    cont_at = datetime.fromisoformat(last["continuity_issued_at"].replace("Z", "+00:00"))
    sar_at = payload.sar_issued_at
    delta = (sar_at - cont_at).total_seconds()
    cid = "sha256:" + hashlib.sha256((payload.continuity_receipt_id + payload.sar_receipt_id).encode()).hexdigest()

    complete_record = {
        "chain_id": cid,
        "event_type": "chain_complete",
        "continuity_receipt_id": payload.continuity_receipt_id,
        "sar_receipt_id": payload.sar_receipt_id,
        "chain_status": "complete",
        "continuity_issued_at": last["continuity_issued_at"],
        "sar_issued_at": payload.sar_issued_at.isoformat().replace("+00:00", "Z"),
        "time_delta_seconds": delta,
        "chain_latency_bucket": latency_bucket(delta),
        "verdict_correlation": f"{last['continuity_classification']}:{payload.sar_verdict}",
        "prior_signal_digest": last.get("prior_signal_digest"),
        "continuity_classification": last["continuity_classification"],
        "sar_verdict": payload.sar_verdict,
        "predicate_failure_vector": last.get("predicate_failure_vector", []),
        "executor_continuity_status": last.get("executor_continuity_status", "unknown"),
    }
    append_jsonl(CHAIN_LEDGER, complete_record)

    continuity = read_jsonl(CONTINUITY_LEDGER)
    cont_matches = [r for r in continuity if r.get("receipt_id") == payload.continuity_receipt_id]
    if not cont_matches:
        raise HTTPException(status_code=404, detail="continuity receipt not found")
    prev = cont_matches[-1]
    binding_event = {
        **prev,
        "event_type": "sar_binding_completed",
        "sar_binding": payload.sar_receipt_id,
        "chain_id": cid,
    }
    append_jsonl(CONTINUITY_LEDGER, binding_event)
    return {"chain_id": cid, "chain_status": "complete"}
