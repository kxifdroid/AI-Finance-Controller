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

    async def answer_query(self, db: Session, user_message: str) -> Dict[str, Any]:
        """
        Processes a user question by selecting and executing relevant database tools,
        then formulating an accurate, grounded answer.
        """
        msg_lower = user_message.lower()
        tools_used = []
        referenced_exceptions = []
        referenced_transactions = []
        context_data = {}

        # 1. Deterministic Intent & Tool Routing
        if any(w in msg_lower for w in ["summary", "overview", "match rate", "how many", "status", "reconciled", "progress"]):
            summary = self.tool_get_reconciliation_summary(db)
            tools_used.append({"tool_name": "get_reconciliation_summary", "arguments": {}, "result_summary": f"Fetched summary for {summary.get('total_records', 0)} records."})
            context_data["reconciliation_summary"] = summary

        if any(w in msg_lower for w in ["largest", "biggest", "highest amount", "top discrepancy", "discrepancy"]):
            largest = self.tool_get_largest_discrepancies(db, limit=5)
            tools_used.append({"tool_name": "get_largest_discrepancies", "arguments": {"limit": 5}, "result_summary": f"Found {len(largest)} largest discrepancy records."})
            context_data["largest_discrepancies"] = largest
            for item in largest:
                referenced_exceptions.append(item["exception_id"])

        if any(w in msg_lower for w in ["unsettled", "cash", "pending", "exposure", "disputed"]):
            unsettled = self.tool_get_unsettled_amount(db)
            tools_used.append({"tool_name": "get_unsettled_amount", "arguments": {}, "result_summary": f"Total unsettled open amount: ₹{unsettled.get('total_open_exception_amount', 0):,.2f}"})
            context_data["unsettled_metrics"] = unsettled

        if any(w in msg_lower for w in ["high risk", "urgent", "attention", "critical", "failed"]):
            high_risk = self.tool_get_high_risk_transactions(db)
            tools_used.append({"tool_name": "get_high_risk_transactions", "arguments": {}, "result_summary": f"Found {len(high_risk)} high risk transactions."})
            context_data["high_risk_transactions"] = high_risk
            for item in high_risk:
                referenced_transactions.append(item["match_id"])

        if any(w in msg_lower for w in ["exception", "unresolved", "error", "missing", "duplicate"]):
            exceptions = self.tool_get_exceptions(db, limit=10)
            tools_used.append({"tool_name": "get_exceptions", "arguments": {"limit": 10}, "result_summary": f"Retrieved {len(exceptions)} open exception records."})
            context_data["exceptions_sample"] = exceptions
            for item in exceptions:
                referenced_exceptions.append(item["exception_id"])

        # If no specific keyword triggered tools, load general summary & exceptions
        if not tools_used:
            summary = self.tool_get_reconciliation_summary(db)
            tools_used.append({"tool_name": "get_reconciliation_summary", "arguments": {}, "result_summary": "Default reconciliation overview."})
            context_data["reconciliation_summary"] = summary

        # 2. Synthesize Grounded Natural Language Response
        # We synthesize an audit-ready response grounded completely in context_data
        parts = []

        if "reconciliation_summary" in context_data:
            s = context_data["reconciliation_summary"]
            if s.get("status") == "no_runs_found":
                parts.append("No reconciliation run has been executed yet. Please click 'Run Reconciliation' to process transactions.")
            else:
                parts.append(
                    f"**Reconciliation Summary (Run {s['run_id']})**:\n"
                    f"- Total Records Processed: **{s['total_records']}**\n"
                    f"- Matched: **{s['matched_count']}** ({s['match_rate_pct']}% match rate, ₹{s['total_matched_volume']:,.2f})\n"
                    f"- Human Review Needed: **{s['review_count']}** (₹{s['total_review_volume']:,.2f})\n"
                    f"- Exceptions: **{s['exception_count']}** (₹{s['total_exception_volume']:,.2f})\n"
                    f"- Duplicates: **{s['duplicate_count']}** | Missing Records: **{s['missing_count']}**\n"
                    f"- Pipeline Throughput: **{s['throughput_rps']} records/sec** ({s['processing_time_ms']:.0f} ms)"
                )

        if "largest_discrepancies" in context_data:
            largest = context_data["largest_discrepancies"]
            if largest:
                top = largest[0]
                parts.append(
                    f"\n**Largest Discrepancy Identified**:\n"
                    f"- Exception ID: `{top['exception_id']}`\n"
                    f"- Discrepancy Amount: **₹{top['amount_discrepancy']:,.2f}** (Total involved: ₹{top['amount_involved']:,.2f})\n"
                    f"- Classification: **{top['type']}** (Severity: `{top['severity']}`)\n"
                    f"- Cause: {top['explanation']}\n"
                    f"- Recommended Action: {top['recommended_action']}"
                )

        if "unsettled_metrics" in context_data:
            u = context_data["unsettled_metrics"]
            parts.append(
                f"\n**Unsettled Cash Position**:\n"
                f"- Total Open Exception Exposure: **₹{u['total_open_exception_amount']:,.2f}**\n"
                f"- Net Discrepancy Variance: **₹{u['total_unsettled_discrepancies']:,.2f}**\n"
                f"- Un-reconciled Gateway Volume: **₹{u['missing_gateway_volume']:,.2f}**"
            )

        if "high_risk_transactions" in context_data:
            hr = context_data["high_risk_transactions"]
            if hr:
                parts.append(f"\n**Transactions Requiring Immediate Attention ({len(hr)} High Risk items)**:")
                for item in hr[:3]:
                    parts.append(f"- Match `{item['match_id']}`: {item['explanation']} -> *{item['recommended_action']}*")

        answer_text = "\n\n".join(parts)

        return {
            "answer": answer_text,
            "tools_used": tools_used,
            "referenced_exceptions": list(set(referenced_exceptions)),
            "referenced_transactions": list(set(referenced_transactions)),
        }
