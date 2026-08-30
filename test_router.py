import pytest
from router import deterministic_router

def test_duplicate_id_quarantine():
    seen_ids = set()
    
    txn1 = {"txn_id": "txn_test_1", "mrr_value": 100.0, "attempt_count": 1, "failure_code": "network_timeout", "customer_tier": "enterprise"}
    res1 = deterministic_router(txn1, seen_txn_ids=seen_ids)
    assert res1["action"] != "QUARANTINE_DATA"

    # Second time with the exact same ID and same set triggers duplicate quarantine
    txn2 = {"txn_id": "txn_test_1", "mrr_value": 100.0, "attempt_count": 1, "failure_code": "network_timeout", "customer_tier": "enterprise"}
    res2 = deterministic_router(txn2, seen_txn_ids=seen_ids)
    assert res2["action"] == "QUARANTINE_DATA"
    assert "Duplicate transaction detected" in res2["reasoning"]

def test_negative_mrr_quarantine():
    txn = {"txn_id": "txn_test_2", "mrr_value": -50.0, "attempt_count": 1, "failure_code": "insufficient_funds", "customer_tier": "enterprise"}
    res = deterministic_router(txn)
    assert res["action"] == "QUARANTINE_DATA"
    assert "Malformed or negative MRR" in res["reasoning"]

def test_lapsed_promise_to_pay():
    txn = {
        "txn_id": "txn_test_3",
        "mrr_value": 150.0,
        "attempt_count": 1,
        "failure_code": "insufficient_funds",
        "customer_tier": "enterprise",
        "customer_response": "PROMISE_TO_PAY",
        "promise_due_date": "2026-08-25"
    }
    res = deterministic_router(txn, current_date_str="2026-08-30")
    assert res["action"] == "ESCALATE_TO_COLLECTIONS"

def test_missing_customer_tier_manual_review():
    txn = {
        "txn_id": "txn_test_4",
        "mrr_value": 200.0,
        "attempt_count": 1,
        "failure_code": "insufficient_funds",
        "customer_tier": None
    }
    res = deterministic_router(txn)
    assert res["action"] == "MANUAL_REVIEW"
    assert "Missing critical customer metadata" in res["reasoning"]

def test_max_retry_attempts_circuit_breaker():
    txn = {
        "txn_id": "txn_test_5",
        "mrr_value": 250.0,
        "attempt_count": 3,
        "failure_code": "insufficient_funds",
        "customer_tier": "enterprise"
    }
    res = deterministic_router(txn)
    assert res["action"] == "ESCALATE"
    assert "Max retry limit reached" in res["reasoning"]