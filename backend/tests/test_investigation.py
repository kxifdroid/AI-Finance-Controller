"""
Automated Test Suite for AI Exception Investigation & Policy Service (Phase 6).

Problem Solved:
Tests PolicyService citation retrieval, ExceptionInvestigatorAgent deterministic & AI analysis,
deterministic guardrail override enforcement, and the approve/reject endpoints.

Tests:
1. PolicyService static policy dictionary verification & citation retrieval.
2. ExceptionInvestigatorAgent deterministic investigation for FEE_VARIANCE (MDR formula).
3. ExceptionInvestigatorAgent deterministic investigation for TIMING_DIFFERENCE & DUPLICATE.
4. Deterministic Guardrail Override: AI claims MARK_RECONCILED with unexplained variance -> Overridden to MANUAL_REVIEW.
5. Deterministic Guardrail Override: AI claims MARK_RECONCILED on DUPLICATE -> Overridden to ESCALATE.
6. API Endpoints: POST /api/exceptions/{id}/investigate, /approve, /reject.
"""

import json
import pytest
from datetime import date, datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.main import app
from app.db.base import Base
from app.db.session import get_db
from app.models.exception import ExceptionRecord
from app.models.transaction import BankTransaction, GatewayTransaction, Invoice
from app.models.reconciliation import ReconciliationRun
from app.services.policy import (
    PolicyService,
    RAZORPAY_MDR_POLICY,
    SETTLEMENT_WINDOW_POLICY,
    IDEMPOTENCY_POLICY,
    TDS_194H_POLICY,
    MATERIALITY_POLICY,
)
from app.agents.investigator import ExceptionInvestigatorAgent
from app.agents.llm_provider import BaseLLMClient


# Isolated test database
test_engine = create_engine("sqlite:///./test_investigation.db", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=test_engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=test_engine)
    test_engine.dispose()
    import os
    try:
        if os.path.exists("./test_investigation.db"):
            os.remove("./test_investigation.db")
    except Exception:
        pass


@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


client = TestClient(app)


# =============================================================================
# 1. PolicyService Tests
# =============================================================================

def test_policy_service_static_dictionaries():
    """Verifies all static policy dictionaries and numeric parameters."""
    assert RAZORPAY_MDR_POLICY["mdr_rate"] == 0.02
    assert RAZORPAY_MDR_POLICY["gst_rate_on_fee"] == 0.18
    assert RAZORPAY_MDR_POLICY["effective_deduction_rate"] == 0.0236
    assert "2.0% MDR + 18% GST" in RAZORPAY_MDR_POLICY["citation"]

    assert SETTLEMENT_WINDOW_POLICY["min_days"] == 1
    assert SETTLEMENT_WINDOW_POLICY["max_days"] == 3
    assert "T+1 to T+3" in SETTLEMENT_WINDOW_POLICY["citation"]

    assert IDEMPOTENCY_POLICY["collision_window_seconds"] == 90
    assert "RFC 7231" in IDEMPOTENCY_POLICY["citation"]

    assert TDS_194H_POLICY["tds_rate"] == 0.05
    assert TDS_194H_POLICY["annual_exemption_threshold"] == 15000.0
    assert "Section 194H" in TDS_194H_POLICY["citation"]

    assert MATERIALITY_POLICY["auto_clear_ceiling"] == 5000.0
    assert "₹5,000" in MATERIALITY_POLICY["citation"]


def test_policy_service_citation_retrieval():
    """Tests dynamic policy citation matching across various exception types."""
    # Fee variance
    fee_pols = PolicyService.get_applicable_policies("FEE_VARIANCE", {"amount": 10000.0, "discrepancy": 236.0})
    assert any("Razorpay MDR" in p for p in fee_pols)
    assert any("Materiality Ceiling" in p for p in fee_pols)

    # Timing difference
    timing_pols = PolicyService.get_applicable_policies("TIMING_DIFFERENCE")
    assert any("T+1 to T+3" in p for p in timing_pols)

    # Duplicate
    dup_pols = PolicyService.get_applicable_policies("DUPLICATE_TRANSACTION")
    assert any("Idempotency Standard" in p for p in dup_pols)

    # Many-to-one
    mto_pols = PolicyService.get_applicable_policies("MANY_TO_ONE_SETTLEMENT")
    assert any("T+1 to T+3" in p for p in mto_pols)
    assert any("Razorpay MDR" in p for p in mto_pols)


# =============================================================================
# 2. ExceptionInvestigatorAgent Deterministic Tests
# =============================================================================

def test_investigator_fee_variance_deterministic_match(db_session):
    """
    Tests that a fee variance matching 2% MDR + 18% GST (Gross 10,000, Discrepancy 236)
    is autonomously evaluated with recommendation MARK_RECONCILED and deterministic_override=True.
    """
    # Create run and transactions
    run = ReconciliationRun(run_id="RUN_INV_1", total_records=2, matched_count=0, status="COMPLETED")
    db_session.add(run)

    gw = GatewayTransaction(
        gateway_txn_id="GW-INV-1",
        amount=10000.0,
        gross_amount=10000.0,
        gateway_fee=200.0,
        tax_on_fee=36.0,
        net_settlement=9764.0,
        transaction_date=date(2026, 8, 20),
        payment_reference="ORD-INV-1",
        customer_name="Acme Tech",
        normalized_amount=10000.0,
        normalized_date=date(2026, 8, 20),
        normalized_ref="ordinv1",
        normalized_customer="acme tech",
    )
    bank = BankTransaction(
        bank_txn_id="BNK-INV-1",
        amount=9764.0,
        transaction_date=date(2026, 8, 20),
        reference="ORD-INV-1",
        description="Payout",
        normalized_amount=9764.0,
        normalized_date=date(2026, 8, 20),
        normalized_ref="ordinv1",
        normalized_desc="payout",
    )
    db_session.add(gw)
    db_session.add(bank)

    exc = ExceptionRecord(
        exception_id="EXC-INV-001",
        run_id="RUN_INV_1",
        gateway_txn_id="GW-INV-1",
        bank_txn_id="BNK-INV-1",
        exception_type="FEE_VARIANCE",
        severity="LOW",
        amount_involved=10000.0,
        amount_discrepancy=236.0,
        explanation="Gateway fee variance of 2.36%",
        recommended_action="Approve variance as standard payment gateway fee.",
        status="OPEN",
    )
    db_session.add(exc)
    db_session.commit()

    agent = ExceptionInvestigatorAgent()
    res = agent.investigate(db=db_session, exception_record=exc, use_ai=False)

    assert res["exception_id"] == "EXC-INV-001"
    assert res["recommendation"] == "MARK_RECONCILED"
    assert res["confidence"] >= 0.95
    assert res["requires_human_review"] is False
    assert res["deterministic_override"] is True
    assert res["override_reason"] == "Formulaic MDR Fee Tolerance Match"
    assert any("2.0%" in e for e in res["evidence"])
    assert any("Razorpay MDR" in p for p in res["policy_references"])


def test_investigator_timing_and_duplicate_deterministic(db_session):
    """
    Tests deterministic investigation for TIMING_DIFFERENCE and DUPLICATE_TRANSACTION.
    """
    # Timing
    exc_timing = ExceptionRecord(
        exception_id="EXC-INV-TIMING",
        run_id="RUN_INV_1",
        exception_type="TIMING_DIFFERENCE",
        severity="MEDIUM",
        amount_involved=5000.0,
        amount_discrepancy=0.0,
        explanation="Settlement lag across weekend",
        recommended_action="Review timing discrepancy",
        status="OPEN",
    )
    db_session.add(exc_timing)

    # Duplicate
    exc_dup = ExceptionRecord(
        exception_id="EXC-INV-DUP",
        run_id="RUN_INV_1",
        exception_type="DUPLICATE_TRANSACTION",
        severity="HIGH",
        amount_involved=3000.0,
        amount_discrepancy=3000.0,
        explanation="Duplicate payment capture detected",
        recommended_action="Escalate to operations",
        status="OPEN",
    )
    db_session.add(exc_dup)
    db_session.commit()

    agent = ExceptionInvestigatorAgent()

    res_timing = agent.investigate(db=db_session, exception_record=exc_timing, use_ai=False)
    assert res_timing["recommendation"] == "MANUAL_REVIEW"
    assert res_timing["requires_human_review"] is True

    res_dup = agent.investigate(db=db_session, exception_record=exc_dup, use_ai=False)
    assert res_dup["recommendation"] == "ESCALATE"
    assert res_dup["requires_human_review"] is True


# =============================================================================
# 3. Deterministic Guardrail Override Tests (AI vs Math)
# =============================================================================

class MockHallucinatingLLMClient(BaseLLMClient):
    """Simulates an LLM hallucinating a MARK_RECONCILED on a severe amount mismatch."""

    async def generate_structured_json(self, system_prompt: str, user_prompt: str):
        return {
            "classification": "AMOUNT_MISMATCH",
            "confidence": 0.99,
            "recommendation": "MARK_RECONCILED",  # Hallucinated decision!
            "explanation": "AI erroneously believes the amounts match despite 5,000 discrepancy.",
            "evidence": ["Hallucinated perfect match"],
            "requires_human_review": False,
            "policy_references": ["Arbitrary Policy"],
        }


def test_deterministic_guardrail_overrides_hallucinating_ai(db_session):
    """
    CRITICAL RULE TEST:
    When the AI LLM proposes MARK_RECONCILED but unexplained monetary variance exists (₹5,000 delta),
    the deterministic guardrail MUST override the AI recommendation to MANUAL_REVIEW.
    """
    exc_mismatch = ExceptionRecord(
        exception_id="EXC-INV-OVERRIDE-1",
        run_id="RUN_INV_1",
        exception_type="AMOUNT_MISMATCH",
        severity="HIGH",
        amount_involved=15000.0,
        amount_discrepancy=5000.0,
        explanation="Severe variance of ₹5,000",
        recommended_action="Investigate discrepancy",
        status="OPEN",
    )
    db_session.add(exc_mismatch)
    db_session.commit()

    hallucinating_client = MockHallucinatingLLMClient()
    agent = ExceptionInvestigatorAgent(llm_client=hallucinating_client)

    res = agent.investigate(db=db_session, exception_record=exc_mismatch, use_ai=True)

    # Verify that deterministic guardrail enforced override
    assert res["recommendation"] == "MANUAL_REVIEW"
    assert res["requires_human_review"] is True
    assert res["deterministic_override"] is True
    assert "Deterministic Guardrail" in res["override_reason"]
    assert "unexplained" in res["override_reason"].lower() or "variance" in res["override_reason"].lower()


class MockDuplicateHallucinatingLLMClient(BaseLLMClient):
    """Simulates an LLM hallucinating MARK_RECONCILED on a duplicate transaction collision."""

    async def generate_structured_json(self, system_prompt: str, user_prompt: str):
        return {
            "classification": "DUPLICATE_TRANSACTION",
            "confidence": 0.95,
            "recommendation": "MARK_RECONCILED",
            "explanation": "AI incorrectly advises auto-clearing duplicate charge.",
            "evidence": ["Duplicate cleared"],
            "requires_human_review": False,
        }


def test_deterministic_guardrail_overrides_duplicate_auto_clear(db_session):
    """
    CRITICAL RULE TEST:
    When the AI proposes MARK_RECONCILED for a duplicate transaction,
    the deterministic guardrail MUST override it to ESCALATE.
    """
    exc_dup = ExceptionRecord(
        exception_id="EXC-INV-OVERRIDE-2",
        run_id="RUN_INV_1",
        exception_type="DUPLICATE_TRANSACTION",
        severity="HIGH",
        amount_involved=4000.0,
        amount_discrepancy=4000.0,
        explanation="Duplicate capture collision",
        recommended_action="Void duplicate",
        status="OPEN",
    )
    db_session.add(exc_dup)
    db_session.commit()

    agent = ExceptionInvestigatorAgent(llm_client=MockDuplicateHallucinatingLLMClient())
    res = agent.investigate(db=db_session, exception_record=exc_dup, use_ai=True)

    assert res["recommendation"] == "ESCALATE"
    assert res["requires_human_review"] is True
    assert res["deterministic_override"] is True
    assert "Duplicate transaction" in res["override_reason"]


# =============================================================================
# 4. API Endpoint Integration Tests (Investigate, Approve, Reject)
# =============================================================================

def test_api_investigate_approve_reject_flow(db_session):
    """
    Tests the complete API workflow:
    1. POST /api/exceptions/{id}/investigate
    2. POST /api/exceptions/{id}/approve -> RESOLVED
    3. POST /api/exceptions/{id}/reject -> IN_REVIEW with HIGH severity
    """
    exc = ExceptionRecord(
        exception_id="EXC-API-FLOW-1",
        run_id="RUN_INV_1",
        exception_type="FEE_VARIANCE",
        severity="LOW",
        amount_involved=10000.0,
        amount_discrepancy=236.0,
        explanation="MDR fee deduction of 2.36%",
        recommended_action="Approve variance",
        status="OPEN",
    )
    db_session.add(exc)
    db_session.commit()

    # 1. Investigate endpoint
    res_inv = client.post("/api/exceptions/EXC-API-FLOW-1/investigate")
    assert res_inv.status_code == 200
    inv_data = res_inv.json()
    assert inv_data["exception_id"] == "EXC-API-FLOW-1"
    assert inv_data["recommendation"] == "MARK_RECONCILED"
    assert inv_data["deterministic_override"] is True
    assert len(inv_data["policy_references"]) > 0

    # 2. Approve endpoint
    res_app = client.post("/api/exceptions/EXC-API-FLOW-1/approve", json={"notes": "Approved standard MDR deduction"})
    assert res_app.status_code == 200
    app_data = res_app.json()
    assert app_data["status"] == "RESOLVED"
    assert "Approved standard MDR deduction" in app_data["notes"]

    # 3. Reject endpoint (on another exception)
    exc2 = ExceptionRecord(
        exception_id="EXC-API-FLOW-2",
        run_id="RUN_INV_1",
        exception_type="AMOUNT_MISMATCH",
        severity="MEDIUM",
        amount_involved=8000.0,
        amount_discrepancy=1500.0,
        explanation="Unverified shortage",
        recommended_action="Investigate shortage",
        status="OPEN",
    )
    db_session.add(exc2)
    db_session.commit()

    res_rej = client.post("/api/exceptions/EXC-API-FLOW-2/reject", json={"reason": "Disputed deduction by customer"})
    assert res_rej.status_code == 200
    rej_data = res_rej.json()
    assert rej_data["status"] == "IN_REVIEW"
    assert rej_data["severity"] == "HIGH"
    assert "Disputed deduction" in rej_data["notes"]
