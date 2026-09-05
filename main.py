import json
import csv
import random

from router import deterministic_router
from agent import process_with_agent

def run_recovery_pipeline(input_file="workflow_payments.json"):
    print("🚀 Initializing Revenue Recovery Pipeline...\n")
    
    try:
        with open(input_file, "r") as f:
            batch = json.load(f)
    except FileNotFoundError:
        print(f"Error: Could not find {input_file}. Run data_gen.py first.")
        return


    metrics = {
        "total_records": len(batch),
        "total_mrr_at_risk": 0.0,
        "mrr_actioned": 0.0,            
        "mrr_actually_recovered": 0.0,  
        "mrr_paused_promises": 0.0,
        "mrr_pending_action": 0.0,         
        "mrr_needs_followup": 0.0,
        "mrr_confirmed_unrecoverable": 0.0, 
        "ai_decisions": 0,
        "rule_decisions": 0
    }
    
    audit_trail = []
    exceptions_list = []
    seen_txn_ids = set()

    for index, txn in enumerate(batch):
        print(f"Processing {index + 1}/{len(batch)}: {txn.get('txn_id', 'Unknown')}...")
        try:
            mrr = float(txn.get("mrr_value", 0.0))
            if mrr > 0:
                metrics["total_mrr_at_risk"] += mrr
            else:
                mrr = 0.0  # --- FIX: Normalize negative numbers to 0.0 ---
        except (ValueError, TypeError):
            mrr = 0.0 # Count as 0 if it's a malformed string like "USD 299" to prevent crashes.
        router_result = deterministic_router(txn, current_date_str="2026-08-30", seen_txn_ids=seen_txn_ids)
        actual_outcome = "N/A" 
        
        if router_result["routing"] == "DETERMINISTIC":
            metrics["rule_decisions"] += 1
            action = router_result["action"]
            reasoning = router_result["reasoning"]
            
            if action in ["NOTIFY_CUSTOMER", "MANUAL_REVIEW", "QUARANTINE_DATA"]:
                metrics["mrr_pending_action"] += mrr
                exceptions_list.append({
                    "txn_id": txn.get("txn_id"),
                    "failure_code": txn.get("failure_code"),
                    "action_taken": action,
                    "bucket": "Pending Customer/Human Action",
                    "reason": reasoning
                })
            elif action in ["BLOCK_ACCOUNT", "ESCALATE_TO_COLLECTIONS"]:
                metrics["mrr_confirmed_unrecoverable"] += mrr
                exceptions_list.append({
                    "txn_id": txn.get("txn_id"),
                    "failure_code": txn.get("failure_code"),
                    "action_taken": action,
                    "bucket": "Confirmed Unrecoverable",
                    "reason": reasoning
                })
            elif action == "ESCALATE":
                metrics["mrr_needs_followup"] += mrr
                exceptions_list.append({
                    "txn_id": txn.get("txn_id"),
                    "failure_code": txn.get("failure_code"),
                    "action_taken": action,
                    "bucket": "Failed First Attempt / Needs Follow-up",
                    "reason": reasoning
                })
            elif action == "PAUSE_WORKFLOW":
                metrics["mrr_paused_promises"] += mrr
            elif action == "RETRY_IMMEDIATE":
                metrics["mrr_actioned"] += mrr
                if random.random() < 0.85:
                    actual_outcome = "RECOVERED"
                    metrics["mrr_actually_recovered"] += mrr
                else:
                    actual_outcome = "FAILED"
                    metrics["mrr_needs_followup"] += mrr
                    exceptions_list.append({
                        "txn_id": txn.get("txn_id"),
                        "failure_code": txn.get("failure_code"),
                        "action_taken": action,
                        "bucket": "Failed First Attempt / Needs Follow-up",
                        "reason": "Immediate technical retry failed on payment gateway."
                    })

            audit_trail.append({
                "txn_id": txn.get("txn_id"),
                "mrr_value": mrr,
                "handler": "RULES_ENGINE",
                "diagnosis": "Deterministic Rule Matched",
                "action": action,
                "reasoning": reasoning,
                "actual_outcome": actual_outcome
            })
        else:
            metrics["ai_decisions"] += 1
            agent_result = process_with_agent(txn)
            
            # 1. Handle API parsing/network errors
            if "error" in agent_result:
                action = "AGENT_FAILURE"
                reasoning = agent_result["error"]
                diagnosis = "Failed to parse LLM output or API error"
                confidence = 0.0
                actual_outcome = "FAILED"
                metrics["mrr_needs_followup"] += mrr
                
                exceptions_list.append({
                    "txn_id": txn.get("txn_id"),
                    "failure_code": txn.get("failure_code"),
                    "action_taken": action,
                    "confidence_score": confidence,
                    "bucket": "Failed First Attempt / Needs Follow-up",
                    "reason": f"LLM Agent execution failed: {reasoning}"
                })
            else:
                raw_action = agent_result.get("decision", "UNKNOWN")
                reasoning = agent_result.get("reasoning", "")
                diagnosis = agent_result.get("diagnosis", "")
                confidence = float(agent_result.get("confidence_score", 1.0))
              
                if confidence < 0.60 and raw_action != "ESCALATE_TO_HUMAN":
                    action = "ESCALATE_TO_HUMAN"
                    reasoning = f"[Low Confidence Override ({confidence:.2f})] Original proposal '{raw_action}' suppressed: {reasoning}"
                    actual_outcome = "ESCALATED"
                    metrics["mrr_needs_followup"] += mrr
                    exceptions_list.append({
                        "txn_id": txn.get("txn_id"),
                        "failure_code": txn.get("failure_code"),
                        "action_taken": action,
                        "confidence_score": confidence,
                        "bucket": "Failed First Attempt / Needs Follow-up",
                        "reason": reasoning
                    })
                # --- FIX: Prevent direct AI escalations from getting coin-flipped ---
                elif raw_action == "ESCALATE_TO_HUMAN":
                    action = raw_action
                    actual_outcome = "ESCALATED"
                    metrics["mrr_needs_followup"] += mrr
                    exceptions_list.append({
                        "txn_id": txn.get("txn_id"),
                        "failure_code": txn.get("failure_code"),
                        "action_taken": action,
                        "confidence_score": confidence,
                        "bucket": "Failed First Attempt / Needs Follow-up",
                        "reason": f"AI explicitly chose to escalate: {reasoning}"
                    })
                else:
                    action = raw_action
                    metrics["mrr_actioned"] += mrr 
                    
                    # 3. Probabilistic outcome simulation
                    success_prob = 0.40 if action == "SCHEDULE_DUNNING" else 0.20
                    if random.random() < success_prob:
                        actual_outcome = "RECOVERED"
                        metrics["mrr_actually_recovered"] += mrr
                    else:
                        actual_outcome = "FAILED"
                        metrics["mrr_needs_followup"] += mrr
                        exceptions_list.append({
                            "txn_id": txn.get("txn_id"),
                            "failure_code": txn.get("failure_code"),
                            "action_taken": action,
                            "bucket": "Failed First Attempt / Needs Follow-up",
                            "reason": f"AI-orchestrated action '{action}' failed first-pass conversion."
                        })
            audit_trail.append({
                "txn_id": txn.get("txn_id"),
                "mrr_value": mrr,
                "handler": "LLM_AGENT",
                "diagnosis": diagnosis,
                "action": action,
                "confidence_score": round(confidence, 2),
                "reasoning": reasoning,
                "actual_outcome": actual_outcome
            })
    with open("audit_trail.csv", "w", newline="") as f:
        fieldnames = [
            "txn_id", "mrr_value", "handler", "diagnosis", 
            "action", "confidence_score", "reasoning", "actual_outcome"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(audit_trail)
        
    # Save the Exceptions List (JSON)
    with open("exceptions_report.json", "w") as f:
        json.dump(exceptions_list, f, indent=4)

  # 5. Print the ROI Dashboard
    print("\n" + "="*55)
    print("📊 REVENUE RECOVERY PIPELINE - FINAL REPORT")
    print("="*55)
    print(f"Total Transactions:              {metrics['total_records']}")
    print(f"Total MRR at Risk:               ${metrics['total_mrr_at_risk']:,.2f}")
    print("-" * 55)
    print(f"✅ Actual MRR Recovered:          ${metrics['mrr_actually_recovered']:,.2f}")
    print(f"⏸️ MRR Paused (Promises):         ${metrics['mrr_paused_promises']:,.2f}")
    print(f"⏳ Pending Action (incl. Quarantine): ${metrics.get('mrr_pending_action', 0.0):,.2f}")
    print(f"🔄 Needs Follow-up (AI/Retries):  ${metrics['mrr_needs_followup']:,.2f}")
    print(f"❌ Confirmed Unrecoverable:       ${metrics['mrr_confirmed_unrecoverable']:,.2f}")
    print("-" * 55)
    print("SYSTEM USAGE:")
    print(f"🛡️ Handled by Rules:              {metrics['rule_decisions']} transactions (Zero API cost)")
    print(f"🧠 Handled by AI Agent:           {metrics['ai_decisions']} transactions")
    print("="*55)
    print("📂 Deliverables generated: 'audit_trail.csv' and 'exceptions_report.json'")

if __name__ == "__main__":
    run_recovery_pipeline()