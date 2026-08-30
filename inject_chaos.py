import json

def inject_adversarial_data(filename="workflow_payments.json"):
    print(f"Opening {filename} to inject adversarial data...")
    
    with open(filename, "r") as f:
        batch = json.load(f)
        
    # Hack 1: Delete a transaction ID entirely
    batch[0]["txn_id"] = None
    batch[0]["failure_code"] = "insufficient_funds" # Would normally go to LLM
    
    # Hack 2: Inject a negative MRR value (simulating a refund glitch)
    batch[1]["mrr_value"] = -150.00
    batch[1]["failure_code"] = "do_not_honor" # Would normally go to LLM
    
    # Hack 3: Inject a string where a float should be
    batch[2]["mrr_value"] = "USD 299"
    batch[2]["failure_code"] = "network_timeout" # Would normally retry
    
    with open(filename, "w") as f:
        json.dump(batch, f, indent=4)
        
    print("Chaos injected! 3 records are now heavily corrupted.")
    print("Run main.py to see your Pre-Flight validation catch them.")

if __name__ == "__main__":
    inject_adversarial_data()