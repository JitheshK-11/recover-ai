import os
import json
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import Literal
from google import genai
from google.genai import types

load_dotenv()  

# Initialize the official Gemini client
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

# ==========================================
# 1. STRUCTURED OUTPUT SCHEMA (THE TOOLS)
# ==========================================
class AgentDecision(BaseModel):
    diagnosis: str = Field(
        description="Diagnose the root cause based on the failure code and customer data."
    )
    decision: Literal["SCHEDULE_DUNNING", "NOTIFY_CUSTOMER", "ESCALATE_TO_HUMAN"] = Field(
        description="The bounded action chosen based on the diagnosis."
    )
    execution_step: str = Field(
        description="Simulate the execution. E.g., 'Scheduled retry for Friday' or 'Sent email template A'."
    )
    reasoning: str = Field(
        description="Explain exactly why this action was chosen over the alternatives."
    )
    confidence_score: float = Field(
        description="Confidence in this decision from 0.0 to 1.0."
    )

# ==========================================
# 2. THE AGENT ORCHESTRATOR
# ==========================================
def process_with_agent(transaction: dict) -> dict:
    """
    Takes an ambiguous transaction, feeds it to Gemini, and forces a structured response.
    """
    prompt = f"""
    You are a Revenue Recovery Agent. Analyze this failed subscription payment:
    {json.dumps(transaction, indent=2)}
    
    Your task:
    1. Diagnose the root cause.
    2. Decide on the best bounded action (SCHEDULE_DUNNING, NOTIFY_CUSTOMER, or ESCALATE_TO_HUMAN).
    3. Outline the simulated execution step.
    4. Provide clear reasoning for the audit log.
    """

    try:
        # Call Gemini 2.5 Flash, enforcing the Pydantic schema
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=AgentDecision,
                temperature=0.1, # Keep it deterministic and analytical
            ),
        )
        
        # Parse the JSON string back into a Python dictionary for our audit log
        return json.loads(response.text)
        
    except Exception as e:
        return {"error": f"Agent execution failed: {str(e)}"}

# ==========================================
# 3. TEST THE AGENT
# ==========================================
if __name__ == "__main__":
    # A sample transaction that passed our deterministic rules in router.py
    sample_txn = {
        "txn_id": "txn_1042",
        "customer_id": "cust_882",
        "mrr_value": 299.00,
        "failure_code": "insufficient_funds",
        "attempt_count": 1,
        "customer_tier": "enterprise",
        "billing_date": "2026-08-28"
    }

    print("Analyzing transaction...")
    decision_log = process_with_agent(sample_txn)
    
    print("\n--- FINAL AUDIT LOG ---")
    print(json.dumps(decision_log, indent=4))