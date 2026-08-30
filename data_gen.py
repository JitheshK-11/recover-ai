import json
import random
from datetime import datetime, timedelta

def generate_messy_batch(num_records=75):
    failure_codes = [
        "insufficient_funds", 
        "expired_card", 
        "network_timeout", 
        "suspected_fraud", 
        "do_not_honor"
    ]
    
    batch = []
    # Anchoring to a static date to test time-based workflows reliably
    base_date = datetime(2026, 8, 30)
    
    for i in range(num_records):
        # Inject messiness: 10% chance of a missing customer tier
        tier = random.choice(["self_serve", "enterprise", None]) if random.random() > 0.1 else None
        
        # Inject messiness: 5% chance of an abnormal attempt count
        attempts = random.randint(1, 3) if random.random() > 0.05 else random.randint(5, 10)
        
        # Inject messiness: 5% chance of a duplicate transaction ID
        txn_id = f"txn_{1000 + i}" if random.random() > 0.05 else f"txn_{1000 + i - 1}"
        
        # Inject Promise-to-Pay state (20% of customers)
        if random.random() < 0.20:
            # Mix of lapsed (past) and active (future) promises
            offset = random.choice([-2, -1, 1, 2])
            promise_date = (base_date + timedelta(days=offset)).strftime("%Y-%m-%d")
            customer_response = "PROMISE_TO_PAY"
        else:
            promise_date = None
            customer_response = None

        record = {
            "txn_id": txn_id,
            "customer_id": f"cust_{random.randint(100, 999)}",
            "mrr_value": round(random.uniform(15.0, 499.0), 2),
            "failure_code": random.choice(failure_codes),
            "attempt_count": attempts,
            "customer_tier": tier,
            "billing_date": (base_date - timedelta(days=random.randint(0, 5))).strftime("%Y-%m-%d"),
            "customer_response": customer_response,
            "promise_due_date": promise_date
        }
        batch.append(record)
        
    # Saving to a new file name to reflect the workflow upgrade
    with open("workflow_payments.json", "w") as f:
        json.dump(batch, f, indent=4)
        
    print(f"Generated {num_records} stateful records in 'workflow_payments.json'")

if __name__ == "__main__":
    generate_messy_batch()