import json
from datetime import datetime

def deterministic_router(transaction, current_date_str="2026-08-30", seen_txn_ids=None):
    """
    Evaluates a transaction against time-based states and hard business rules.
    Passes a seen_txn_ids set explicitly to prevent global state leakage.
    """
    if seen_txn_ids is None:
        seen_txn_ids = set()
        
    code = transaction.get("failure_code")
    txn_id = transaction.get("txn_id")

    # ==========================================
    # 0. PRE-FLIGHT DATA VALIDATION
    # ==========================================
    if not txn_id:
        return {"routing": "DETERMINISTIC", "action": "QUARANTINE_DATA", "reasoning": "Missing Transaction ID."}
        
    # Duplicate ID check using the explicit set parameter
    if txn_id in seen_txn_ids:
        return {
            "routing": "DETERMINISTIC", 
            "action": "QUARANTINE_DATA", 
            "reasoning": f"Duplicate transaction detected ({txn_id}). Quarantined to prevent MRR double-counting."
        }
    seen_txn_ids.add(txn_id)
    
    # Check 3: Malformed MRR
    try:
        mrr = float(transaction.get("mrr_value", 0))
        if mrr <= 0:
            raise ValueError("Negative or zero MRR")
    except (ValueError, TypeError):
        return {"routing": "DETERMINISTIC", "action": "QUARANTINE_DATA", "reasoning": "Malformed or negative MRR value."}

    #  Check 4: Malformed Attempt Count ---
    try:
        attempts = int(transaction.get("attempt_count", 0))
        if attempts < 0:
            raise ValueError("Negative attempt count")
        transaction["attempt_count"] = attempts # Overwrite to ensure it's a clean int for later rules
    except (ValueError, TypeError):
        return {"routing": "DETERMINISTIC", "action": "QUARANTINE_DATA", "reasoning": "Malformed attempt count. Must be a positive integer."}
    
    # ==
    
    # ==========================================
    # 1. TIME-AWARE STATE TRACKING 
    # ==========================================
    response = transaction.get("customer_response")
    due_date_str = transaction.get("promise_due_date")
    
    if response == "PROMISE_TO_PAY" and due_date_str:
        current_date = datetime.strptime(current_date_str, "%Y-%m-%d")
        due_date = datetime.strptime(due_date_str, "%Y-%m-%d")
        
        # Rule: Promise date has passed, and payment still failed.
        if current_date > due_date:
            return {
                "routing": "DETERMINISTIC",
                "action": "ESCALATE_TO_COLLECTIONS",
                "reasoning": f"Customer lapsed on promise-to-pay date ({due_date_str}). Automatic escalation triggered."
            }
        # Rule: Promise date is today or in the future.
        else:
            return {
                "routing": "DETERMINISTIC",
                "action": "PAUSE_WORKFLOW",
                "reasoning": f"Active promise-to-pay on file for {due_date_str}. Suppressing retries to respect arrangement."
            }

    # ==========================================
    # 2. STANDARD SAFETY RAILS 
    # ==========================================
    
    # Safety Rail 1: Gateway penalty prevention (Max 3 retries)
    if attempts >= 3:
        return {
            "routing": "DETERMINISTIC",
            "action": "ESCALATE",
            "reasoning": f"Max retry limit reached ({attempts} attempts). Halting to prevent gateway fees."
        }
        
    # Safety Rail 2: Terminal failures (Never retry)
    if code in ["expired_card", "suspected_fraud"]:
        return {
            "routing": "DETERMINISTIC",
            "action": "NOTIFY_CUSTOMER" if code == "expired_card" else "BLOCK_ACCOUNT",
            "reasoning": f"Terminal failure code '{code}' cannot be resolved via retry."
        }
        
    # Safety Rail 3: Pure transient errors (Immediate blind retry)
    if code == "network_timeout":
        return {
            "routing": "DETERMINISTIC",
            "action": "RETRY_IMMEDIATE",
            "reasoning": "Transient network error. Safe to retry immediately."
        }
        
    # Safety Rail 4: Missing critical data
    if not transaction.get("customer_tier"):
        return {
            "routing": "DETERMINISTIC",
            "action": "MANUAL_REVIEW",
            "reasoning": "Missing critical customer metadata required for dunning strategy."
        }

    # If it passes all safety rails, it requires AI judgment
    return {
        "routing": "LLM_AGENT",
        "action": "PENDING_AI_DECISION",
        "reasoning": f"Code '{code}' requires intelligent scheduling or historical context."
    }

if __name__ == "__main__":
    # Pointing to the new file generated in our updated Day 2 script
    with open("workflow_payments.json", "r") as f:
        batch = json.load(f)
        
    results = {"LLM_AGENT": 0, "DETERMINISTIC": 0}
    actions_taken = {}
    
    for txn in batch:
        decision = deterministic_router(txn)
        results[decision["routing"]] += 1
        
        # Track the specific actions for better terminal visibility
        action = decision["action"]
        actions_taken[action] = actions_taken.get(action, 0) + 1
        
    print("--- Day 2 Routing Results ---")
    print(f"Handled by deterministic rules: {results['DETERMINISTIC']}")
    print(f"Queued for LLM orchestration: {results['LLM_AGENT']}")
    print("\n--- Breakdown of Actions Taken ---")
    for action, count in actions_taken.items():
        print(f" * {action}: {count}")