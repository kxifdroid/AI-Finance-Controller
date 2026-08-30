"""
Finance Q&A Agent with Tool Calling over Financial Ledger State.

Problem Solved:
Enables financial controllers to query operational status, investigate exceptions,
and audit unsettled exposure in natural language with strict numerical grounding.

Why It Exists:
Eliminates hallucinated numbers by routing user queries through structured database
tools before response synthesis.

Available Tools:
- get_reconciliation_summary()
- get_exceptions(status, severity, limit)
- get_exception_by_id(exception_id)
- get_high_risk_transactions()
- get_unsettled_amount()
- get_largest_discrepancies()
"""

import json
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.models.reconciliation import ReconciliationRun, Match
from app.models.exception import ExceptionRecord
from app.models.transaction import BankTransaction, GatewayTransaction, Invoice
from app.agents.llm_provider import get_llm_client, BaseLLMClient
from app.agents.prompts import FINANCE_QA_SYSTEM_PROMPT


PLANNER_SYSTEM_PROMPT = """You are the AI Finance Controller Tool Planner.
Analyze the user's question and select the exact database tools needed to extract live, mathematically grounded figures from our financial ledger.

AVAILABLE TOOLS:
1. "get_reconciliation_summary": Get total volume, match rate, exception/duplicate/missing counts.
2. "get_exceptions": Retrieve list of active exception records. Can pass optional arguments: "severity" ('HIGH', 'MEDIUM', 'LOW'), "limit" (integer).
3. "get_exception_by_id": Retrieve details of a single exception ID. Arguments: "exception_id" (string, e.g., 'EXC-1001').
4. "get_high_risk_transactions": Get high-risk match records needing immediate controller review.
5. "get_unsettled_amount": Aggregate un-reconciled gateway transactions and unsettled bank credit exposure.
6. "get_largest_discrepancies": Get exceptions with the largest monetary variances. Arguments: "limit" (integer).
7. "get_specific_transaction": Lookup a specific transaction ID, reference number, or search by customer name (e.g., 'Zeta Media', 'PAY-5006', 'INV-106'). Arguments: "identifier" (string).

RULES:
- Respond ONLY with valid JSON containing "thought_process" (list of strings describing your planning reasoning) and "tools_to_call" (list of dicts containing "tool_name" and optional "arguments").
- Do NOT output any Markdown blocks, comments, or conversational text.
"""

SYNTHESIS_SYSTEM_PROMPT = """You are the AI Finance Controller Senior Forensic Auditor.
Synthesize a comprehensive, professional, audit-ready natural language response completely grounded in the provided database tool results.

CRITICAL RULES:
1. ONLY cite or summarize figures, transaction IDs, status labels, and dates that are present in the provided context.
2. If the tools found no matching records, explain that honestly rather than inventing or guessing details.
3. Formatting: Highlight monetary values with currency symbols and comma separators (e.g. ₹15,000.00). Use backticks for IDs (`PAY-5006`).
4. Output Format: Return a strict JSON response conforming to the following structure:
{
  "thought_process": ["Thinking step 1", "Thinking step 2", "Synthesizing answer"],
  "answer": "Professional Markdown formatted answer...",
  "referenced_exceptions": ["EXC-ID", ...],
  "referenced_transactions": ["MATCH-ID", ...]
}
Do NOT wrap your JSON in conversational text or comments.
"""


class FinanceQAAgent:
    """
    Q&A agent with verified tool calling against the reconciliation database.
    """

    def __init__(self, llm_client: Optional[BaseLLMClient] = None):
        self.llm_client = llm_client or get_llm_client()

    # -------------------------------------------------------------
    # Database Query Tools
    # -------------------------------------------------------------
    @staticmethod
    def tool_get_reconciliation_summary(db: Session) -> Dict[str, Any]:
        """Tool: Get latest reconciliation run summary and counts."""
        latest_run = db.query(ReconciliationRun).order_by(desc(ReconciliationRun.started_at)).first()
        if not latest_run:
            return {"status": "no_runs_found", "message": "No reconciliation runs have been performed yet."}

        total = latest_run.total_records or 1
        match_rate = round((latest_run.matched_count / total) * 100, 2)
        exc_rate = round((latest_run.exception_count / total) * 100, 2)

        return {
            "run_id": latest_run.run_id,
            "status": latest_run.status,
            "total_records": latest_run.total_records,
            "matched_count": latest_run.matched_count,
            "review_count": latest_run.review_count,
            "exception_count": latest_run.exception_count,
            "duplicate_count": latest_run.duplicate_count,
            "missing_count": latest_run.missing_count,
            "match_rate_pct": match_rate,
            "exception_rate_pct": exc_rate,
            "total_matched_volume": latest_run.total_matched_volume,
            "total_exception_volume": latest_run.total_exception_volume,
            "total_review_volume": latest_run.total_review_volume,
            "processing_time_ms": latest_run.processing_time_ms,
            "throughput_rps": latest_run.throughput_rps,
        }

    @staticmethod
    def tool_get_exceptions(db: Session, status: Optional[str] = None, severity: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Tool: Fetch active exception records."""
        query = db.query(ExceptionRecord)
        if status:
            query = query.filter(ExceptionRecord.status == status.upper())
        if severity:
            query = query.filter(ExceptionRecord.severity == severity.upper())

        records = query.order_by(desc(ExceptionRecord.amount_involved)).limit(limit).all()
        return [
            {
                "exception_id": r.exception_id,
                "type": r.exception_type,
                "severity": r.severity,
                "status": r.status,
                "amount_involved": r.amount_involved,
                "amount_discrepancy": r.amount_discrepancy,
                "explanation": r.explanation,
                "recommended_action": r.recommended_action,
                "bank_txn_id": r.bank_txn_id,
                "gateway_txn_id": r.gateway_txn_id,
                "invoice_id": r.invoice_id,
            }
            for r in records
        ]

    @staticmethod
    def tool_get_exception_by_id(db: Session, exception_id: str) -> Optional[Dict[str, Any]]:
        """Tool: Fetch single exception detail."""
        r = db.query(ExceptionRecord).filter(ExceptionRecord.exception_id == exception_id.strip()).first()
        if not r:
            return None
        return {
            "exception_id": r.exception_id,
            "type": r.exception_type,
            "severity": r.severity,
            "status": r.status,
            "amount_involved": r.amount_involved,
            "amount_discrepancy": r.amount_discrepancy,
            "explanation": r.explanation,
            "recommended_action": r.recommended_action,
            "bank_txn_id": r.bank_txn_id,
            "gateway_txn_id": r.gateway_txn_id,
            "invoice_id": r.invoice_id,
            "notes": r.notes,
        }

    @staticmethod
    def tool_get_high_risk_transactions(db: Session) -> List[Dict[str, Any]]:
        """Tool: Retrieve all transactions flagged as HIGH risk."""
        records = db.query(Match).filter(Match.risk_level == "HIGH").limit(10).all()
        return [
            {
                "match_id": m.match_id,
                "decision": m.decision,
                "risk_level": m.risk_level,
                "confidence_score": m.confidence_score,
                "bank_txn_id": m.bank_txn_id,
                "gateway_txn_id": m.gateway_txn_id,
                "invoice_id": m.invoice_id,
                "explanation": m.explanation,
                "recommended_action": m.recommended_action,
            }
            for m in records
        ]

    @staticmethod
    def tool_get_unsettled_amount(db: Session) -> Dict[str, Any]:
        """Tool: Calculate unsettled, disputed, and pending cash balances."""
        open_exc_sum = db.query(func.coalesce(func.sum(ExceptionRecord.amount_involved), 0.0))\
            .filter(ExceptionRecord.status == "OPEN").scalar() or 0.0
        
        discrepancy_sum = db.query(func.coalesce(func.sum(ExceptionRecord.amount_discrepancy), 0.0))\
            .filter(ExceptionRecord.status == "OPEN").scalar() or 0.0

        missing_gw_sum = db.query(func.coalesce(func.sum(ExceptionRecord.amount_involved), 0.0))\
            .filter(ExceptionRecord.exception_type == "MISSING_GATEWAY", ExceptionRecord.status == "OPEN").scalar() or 0.0

        return {
            "total_open_exception_amount": round(open_exc_sum, 2),
            "total_unsettled_discrepancies": round(discrepancy_sum, 2),
            "missing_gateway_volume": round(missing_gw_sum, 2),
        }

    @staticmethod
    def tool_get_largest_discrepancies(db: Session, limit: int = 5) -> List[Dict[str, Any]]:
        """Tool: Retrieve exceptions with the largest amount discrepancies."""
        records = db.query(ExceptionRecord)\
            .order_by(desc(ExceptionRecord.amount_discrepancy))\
            .limit(limit).all()
        return [
            {
                "exception_id": r.exception_id,
                "type": r.exception_type,
                "severity": r.severity,
                "amount_involved": r.amount_involved,
                "amount_discrepancy": r.amount_discrepancy,
                "explanation": r.explanation,
                "recommended_action": r.recommended_action,
            }
            for r in records
        ]

    @staticmethod
    def tool_get_specific_transaction(db: Session, identifier: str) -> Dict[str, Any]:
        """Tool: Search database for a specific transaction ID, invoice reference, or counterparty name."""
        ident_clean = identifier.strip()
        
        # 1. Search in Match records (using Match ID)
        match_rec = db.query(Match).filter(Match.match_id == ident_clean).first()
        if match_rec:
            return {
                "source": "match_records",
                "match_id": match_rec.match_id,
                "decision": match_rec.decision,
                "risk_level": match_rec.risk_level,
                "confidence_score": match_rec.confidence_score,
                "bank_txn_id": match_rec.bank_txn_id,
                "gateway_txn_id": match_rec.gateway_txn_id,
                "invoice_id": match_rec.invoice_id,
                "explanation": match_rec.explanation,
                "recommended_action": match_rec.recommended_action,
            }
            
        # 2. Search in Exceptions
        exc_rec = db.query(ExceptionRecord).filter(
            (ExceptionRecord.exception_id == ident_clean) |
            (ExceptionRecord.bank_txn_id == ident_clean) |
            (ExceptionRecord.gateway_txn_id == ident_clean) |
            (ExceptionRecord.invoice_id == ident_clean)
        ).first()
        if exc_rec:
            return {
                "source": "exception_records",
                "exception_id": exc_rec.exception_id,
                "type": exc_rec.exception_type,
                "severity": exc_rec.severity,
                "status": exc_rec.status,
                "amount_involved": exc_rec.amount_involved,
                "amount_discrepancy": exc_rec.amount_discrepancy,
                "explanation": exc_rec.explanation,
                "recommended_action": exc_rec.recommended_action,
            }

        # 3. Search Invoice (by ID, reference, or customer name)
        inv = db.query(Invoice).filter(
            (Invoice.invoice_id == ident_clean) |
            (Invoice.invoice_reference == ident_clean) |
            (Invoice.customer_name.ilike(f"%{ident_clean}%"))
        ).first()
        if inv:
            return {
                "source": "erp_invoices",
                "invoice_id": inv.invoice_id,
                "invoice_reference": inv.invoice_reference,
                "customer_name": inv.customer_name,
                "amount": inv.amount,
                "invoice_date": str(inv.invoice_date),
                "status": "Found in ERP",
            }

        # 4. Search Gateway (by ID, reference, or customer name)
        gw = db.query(GatewayTransaction).filter(
            (GatewayTransaction.gateway_txn_id == ident_clean) |
            (GatewayTransaction.payment_reference == ident_clean) |
            (GatewayTransaction.customer_name.ilike(f"%{ident_clean}%"))
        ).first()
        if gw:
            return {
                "source": "payment_gateway",
                "gateway_txn_id": gw.gateway_txn_id,
                "payment_reference": gw.payment_reference,
                "customer_name": gw.customer_name,
                "amount": gw.amount,
                "net_settlement": gw.net_settlement,
                "transaction_date": str(gw.transaction_date),
                "status": "Found in Gateway",
            }

        # 5. Search Bank
        bank = db.query(BankTransaction).filter(
            (BankTransaction.bank_txn_id == ident_clean) |
            (BankTransaction.reference == ident_clean) |
            (BankTransaction.description.ilike(f"%{ident_clean}%"))
        ).first()
        if bank:
            return {
                "source": "bank_statement",
                "bank_txn_id": bank.bank_txn_id,
                "reference": bank.reference,
                "description": bank.description,
                "amount": bank.amount,
                "transaction_date": str(bank.transaction_date),
                "status": "Found in Bank Statements",
            }

        return {"status": "not_found", "message": f"No records matching identifier '{ident_clean}' found."}

    async def answer_query(self, db: Session, user_message: str) -> Dict[str, Any]:
        """
        Processes a user question by selecting and executing relevant database tools,
        then formulating an accurate, grounded answer using a two-stage Gemini agent.
        """
        thought_process: List[str] = []
        tools_used_log: List[Dict[str, Any]] = []
        referenced_exceptions: List[str] = []
        referenced_transactions: List[str] = []
        context_data: Dict[str, Any] = {}

        # Stage 1: Gemini plans which tools to call
        planning_prompt_user = f"User Query: {user_message}\\n\\n"
        try:
            planner_response = await self.llm_client.generate_structured_json(PLANNER_SYSTEM_PROMPT, planning_prompt_user)
            thought_process.extend(planner_response.get("thought_process", []))
            tools_to_call = planner_response.get("tools_to_call", [])
        except Exception as e:
            thought_process.append(f"Error in tool planning: {e}. Attempting basic keyword routing as fallback.")
            tools_to_call = [] # Fallback to empty list, then handle keyword routing below

        # Fallback to existing deterministic keyword routing if LLM planning fails or returns no tools
        if not tools_to_call:
            if any(w in user_message.lower() for w in ["summary", "overview", "match rate", "how many", "status", "reconciled", "progress"]):
                tools_to_call.append({"tool_name": "get_reconciliation_summary", "arguments": {}})
            if any(w in user_message.lower() for w in ["largest", "biggest", "highest amount", "top discrepancy", "discrepancy"]):
                tools_to_call.append({"tool_name": "get_largest_discrepancies", "arguments": {"limit": 5}})
            if any(w in user_message.lower() for w in ["unsettled", "cash", "pending", "exposure", "disputed"]):
                tools_to_call.append({"tool_name": "get_unsettled_amount", "arguments": {}})
            if any(w in user_message.lower() for w in ["high risk", "urgent", "attention", "critical", "failed"]):
                tools_to_call.append({"tool_name": "get_high_risk_transactions", "arguments": {}})
            if any(w in user_message.lower() for w in ["exception", "unresolved", "error", "missing", "duplicate"]):
                tools_to_call.append({"tool_name": "get_exceptions", "arguments": {"limit": 10}})
            if any(w in user_message.lower() for w in ["zeta media", "pay-", "inv-", "transaction", "id", "reference"]):
                # Attempt to extract identifier for specific transaction lookup
                import re
                match = re.search(r'(PAY-\d+|INV-\d+|EXC-\d+|[A-Za-z ]+)', user_message)
                if match:
                    identifier = match.group(1).strip()
                    tools_to_call.append({"tool_name": "get_specific_transaction", "arguments": {"identifier": identifier}})
                else:
                    tools_to_call.append({"tool_name": "get_reconciliation_summary", "arguments": {}}) # Default fallback

            # If still no tools, default to summary
            if not tools_to_call:
                tools_to_call.append({"tool_name": "get_reconciliation_summary", "arguments": {}})

        # Stage 2: Execute planned tools
        for tool_call in tools_to_call:
            tool_name = tool_call["tool_name"]
            arguments = tool_call.get("arguments", {})
            tool_method = getattr(self, f"tool_{tool_name}", None)

            if tool_method:
                try:
                    # Pass db session and other required arguments
                    result = tool_method(db=db, **arguments)
                    context_data[tool_name] = result
                    tools_used_log.append({
                        "tool_name": tool_name,
                        "arguments": arguments,
                        "result_summary": f"Executed {tool_name} with args {arguments}. Found {len(result)} items." if isinstance(result, list) else f"Executed {tool_name}. Status: {result.get('status', 'OK')}"
                    })

                    # Extract referenced IDs for frontend display
                    if tool_name == "get_exceptions":
                        for item in result: referenced_exceptions.append(item["exception_id"])
                    elif tool_name == "get_largest_discrepancies":
                        for item in result: referenced_exceptions.append(item["exception_id"])
                    elif tool_name == "get_high_risk_transactions":
                        for item in result: referenced_transactions.append(item["match_id"])
                    elif tool_name == "get_specific_transaction":
                        if result.get("source") == "match_records": referenced_transactions.append(result["match_id"])
                        if result.get("source") == "exception_records": referenced_exceptions.append(result["exception_id"])

                except Exception as e:
                    thought_process.append(f"Error executing tool {tool_name}: {e}")
                    tools_used_log.append({"tool_name": tool_name, "arguments": arguments, "result_summary": f"Failed with error: {e}"})
            else:
                thought_process.append(f"Warning: Tool '{tool_name}' not found or not callable.")
                tools_used_log.append({"tool_name": tool_name, "arguments": arguments, "result_summary": "Tool not found"})

        # Stage 3: Gemini synthesizes the final answer
        synthesis_prompt_user = f"User Query: {user_message}\\n\\nTool Execution Results:\\n{json.dumps(context_data, indent=2)}\\n\\nProvide a comprehensive summary based on these results."
        
        try:
            synthesis_response = await self.llm_client.generate_structured_json(SYNTHESIS_SYSTEM_PROMPT, synthesis_prompt_user)
            final_answer = synthesis_response.get("answer", "I couldn't generate a specific answer based on the provided data.")
            thought_process.extend(synthesis_response.get("thought_process", []))
            referenced_exceptions.extend(synthesis_response.get("referenced_exceptions", []))
            referenced_transactions.extend(synthesis_response.get("referenced_transactions", []))
        except Exception as e:
            thought_process.append(f"Error in answer synthesis: {e}")
            final_answer = "I encountered an error while trying to generate a response. Please try again."

        return {
            "answer": final_answer,
            "thought_process": thought_process,
            "tools_used": tools_used_log,
            "referenced_exceptions": list(set(referenced_exceptions)),
            "referenced_transactions": list(set(referenced_transactions)),
        }
