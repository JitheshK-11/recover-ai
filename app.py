import streamlit as st
import pandas as pd
import json
import uuid

# Import your backend logic
from router import deterministic_router
from agent import process_with_agent

# Set up the page layout
st.set_page_config(page_title="Revenue Recovery AI", page_icon="💸", layout="wide")

st.title("💸 Revenue Recovery Agent Dashboard")
st.markdown("### Intelligent Orchestration & Deterministic Safety Rails")

def load_data():
    try:
        audit_df = pd.read_csv("audit_trail.csv")
        with open("exceptions_report.json", "r") as f:
            exceptions = json.load(f)
        return audit_df, exceptions
    except FileNotFoundError:
        return None, None

audit_df, exceptions = load_data()

if audit_df is None:
    st.error("⚠️ Data files not found. Please run `python main.py` first to generate the audit trail.")
else:
    # --- Metrics Calculation ---
    total_mrr = audit_df["mrr_value"].sum()
    
    # Calculate what was attempted vs what actually succeeded
    mrr_actually_recovered = audit_df[audit_df["actual_outcome"] == "RECOVERED"]["mrr_value"].sum() if "actual_outcome" in audit_df.columns else 0.0
    
    # --- Executive Summary (Two Rows for Complete Financial Transparency) ---
    st.header("📊 Executive Summary & Financial Breakdown")
    
    # Row 1: Core Recovery Funnel & Active States
    col1, col2, col3, col4 = st.columns(4)
    
    mrr_paused = audit_df[audit_df["action"] == "PAUSE_WORKFLOW"]["mrr_value"].sum()
    mrr_pending = audit_df[audit_df["action"].isin(["NOTIFY_CUSTOMER", "MANUAL_REVIEW"])]["mrr_value"].sum()
    
    col1.metric(label="Total MRR Processed", value=f"${total_mrr:,.2f}")
    col2.metric(label="✅ Actual MRR Recovered", value=f"${mrr_actually_recovered:,.2f}")
    col3.metric(label="⏸️ MRR Paused (Promises)", value=f"${mrr_paused:,.2f}")
    col4.metric(label="⏳ Pending Customer Action", value=f"${mrr_pending:,.2f}")

    # Row 2: Edge Cases, AI Circuit Breakers & System Health
    col5, col6, col7, col8 = st.columns(4)
    
    mrr_needs_followup = audit_df[audit_df['action'].isin(['ESCALATE', 'ESCALATE_TO_HUMAN']) | (audit_df.get('actual_outcome') == 'FAILED')]['mrr_value'].sum()
    mrr_unrecoverable = audit_df[audit_df['action'].isin(['BLOCK_ACCOUNT', 'ESCALATE_TO_COLLECTIONS'])]['mrr_value'].sum()
    mrr_quarantined = audit_df[audit_df['action'] == 'QUARANTINE_DATA']['mrr_value'].sum()
    rules_handled = len(audit_df[audit_df["handler"] == "RULES_ENGINE"])

    col5.metric(label="🔄 Needs Follow-up (AI / Retries)", value=f"${mrr_needs_followup:,.2f}", delta="Review Queue")
    col6.metric(label="❌ Confirmed Unrecoverable", value=f"${mrr_unrecoverable:,.2f}")
    col7.metric(label="🛡️ Quarantined (Data Quality)", value=f"${mrr_quarantined:,.2f}")
    col8.metric(label="⚡ API Cost Efficiency", value=f"{rules_handled} Rules Handled", delta="Zero Token Cost")

    st.divider()

    # --- LIVE JUDGE TESTING (Moved to Main Page) ---
    st.header("🎯 Live Judge Testing (Interactive)")
    st.markdown("Enter a custom transaction to test the guardrails and AI live. **Try entering text into the MRR field to see the quarantine rules catch it!**")

    # Create a 2-column layout for the testing section
    test_col1, test_col2 = st.columns([1, 1])

    with test_col1:
        with st.form("judge_tester_form"):
            test_mrr = st.text_input("MRR Value (Try text to break it!)", value="199.00")
            test_code = st.selectbox("Failure Code", ["insufficient_funds", "expired_card", "network_timeout", "suspected_fraud", "do_not_honor", "invalid_routing"])
            test_attempts = st.number_input("Attempt Count", min_value=1, max_value=10, value=1)
            
            # Sub-columns for cleaner form layout
            col_a, col_b = st.columns(2)
            with col_a:
                test_tier = st.selectbox("Customer Tier", ["enterprise", "self_serve", "None"])
            with col_b:
                test_promise = st.selectbox("Customer Response", ["None", "PROMISE_TO_PAY"])
            
            submitted = st.form_submit_button("Run Transaction 🚀")

    with test_col2:
        st.markdown("### 🔍 Live Result:")
        if submitted:
            # Format the data exactly like our JSON dataset
            test_due_date = "2026-09-05" if test_promise == "PROMISE_TO_PAY" else None
            live_txn = {
                "txn_id": f"txn_live_{str(uuid.uuid4())[:6]}",
                "mrr_value": test_mrr,
                "failure_code": test_code,
                "attempt_count": test_attempts,
                "customer_tier": None if test_tier == "None" else test_tier,
                "customer_response": None if test_promise == "None" else test_promise,
                "promise_due_date": test_due_date
            }
            
            # Show a cool loading state while processing
            with st.status("Processing via Orchestration Engine...", expanded=True):
                # 1. Pass through safety rails
                router_result = deterministic_router(live_txn)
                
                if router_result["routing"] == "DETERMINISTIC":
                    st.error(f"🛡️ **Caught by Rules Engine!**\n\n**Action:** {router_result['action']}\n\n**Reason:** {router_result['reasoning']}")
                else:
                    # 2. Pass to LLM Agent
                    st.info("🧠 **Passed to AI Agent...**")
                    agent_result = process_with_agent(live_txn)
                    
                    if "error" in agent_result:
                        st.error(f"❌ **Agent Error:** {agent_result['error']}")
                    else:
                        st.success(f"**Action:** {agent_result['decision']}\n\n**Reason:** {agent_result['reasoning']}")
        else:
            st.info("👈 Fill out the form on the left and hit 'Run Transaction' to see the engine in action.")

    st.divider()

    # --- Exceptions & Escalations ---
    st.header("🛡️ Exceptions & Escalations")
    st.markdown("Contains both **pre-LLM quarantine** (malformed data caught by pre-flight checks) and **post-router/AI escalations** (fraud blocks, max-retry caps, collections, and low-confidence AI overrides).")
    
    if exceptions:
        exceptions_df = pd.DataFrame(exceptions)
        st.dataframe(exceptions_df, width="stretch")
    else:
        st.success("No exceptions recorded in this batch.")

    st.divider()

    # --- Transparent Audit Log ---
    st.header("🧠 Transparent Audit Log")
    st.markdown("Every decision made by the system is logged with explicit, human-readable reasoning.")
    
    # Interactive filter for the judges
    handler_filter = st.radio("Filter by Processing Engine:", ["All", "RULES_ENGINE", "LLM_AGENT"], horizontal=True)
    
    filtered_df = audit_df if handler_filter == "All" else audit_df[audit_df["handler"] == handler_filter]
    
    # Render a clean, stylized dataframe
    st.dataframe(
        filtered_df,
        width="stretch",
        column_config={
            "mrr_value": st.column_config.NumberColumn("MRR Value", format="$%.2f"),
            "txn_id": "Transaction ID",
            "handler": "Engine",
            "diagnosis": "Diagnosis",
            "action": "Action Taken",
            "confidence_score": st.column_config.ProgressColumn(
                "AI Confidence",
                help="Decisions < 0.60 are automatically overridden and escalated to humans.",
                min_value=0.0,
                max_value=1.0,
                format="%.2f"
            ),
            "reasoning": "Reasoning",
            "actual_outcome": "Final Outcome"
        }
    )