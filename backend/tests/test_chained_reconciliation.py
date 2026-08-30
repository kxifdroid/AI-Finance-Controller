import pytest
import asyncio
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.transaction import BankTransaction, GatewayTransaction, Invoice
from app.models.reconciliation import Match
from app.models.audit import AuditLog
from app.services.reconciliation import ReconciliationService, can_auto_clear
from app.config import settings


@pytest.fixture
def test_db(tmp_path):
    db_file = tmp_path / "test_chained.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_can_auto_clear_materiality_gate():
    # 1. Below ceiling (,000) and exact match -> True
    assert can_auto_clear(match_layer="layer1_exact", confidence_score=1.0, amount=4500.0) is True

    # 2. Above ceiling (,000) even with 1.0 confidence -> False (materiality gate holds)
    assert can_auto_clear(match_layer="layer1_exact", confidence_score=1.0, amount=6500.0) is False

    # 3. Fuzzy match below threshold -> False
    assert can_auto_clear(match_layer="layer2_fuzzy", confidence_score=0.85, amount=1000.0) is False

    # 4. One-to-many group -> False (never auto-clears)
    assert can_auto_clear(match_layer="layer1_exact", confidence_score=1.0, amount=1000.0, is_one_to_many=True) is False


def test_chained_two_way_reconciliation(test_db):
    service = ReconciliationService()

    # Seed Invoices
    inv1 = Invoice(
        invoice_id="INV-001",
        invoice_date=date(2026, 8, 20),
        amount=1000.0,
        invoice_reference="ORD-5001",
        normalized_amount=1000.0,
        normalized_date=date(2026, 8, 20),
        normalized_ref="5001",
        customer_name="Acme Corp",
        normalized_customer="acme"
    )
    test_db.add(inv1)

    # Seed Gateway (Gross: 1000, Net: 976.40, Fee: 20, Tax: 3.60)
    gw1 = GatewayTransaction(
        gateway_txn_id="GTW-001",
        transaction_date=date(2026, 8, 20),
        amount=1000.0,
        gateway_fee=20.0,
        tax_on_fee=3.60,
        net_settlement=976.40,
        payment_reference="ORD-5001",
        normalized_amount=1000.0,
        normalized_date=date(2026, 8, 20),
        normalized_ref="5001",
        customer_name="Acme Corp",
        normalized_customer="acme"
    )
    test_db.add(gw1)

    # Seed Bank (Deposited 976.40 net settlement on same day)
    bank1 = BankTransaction(
        bank_txn_id="BNK-001",
        transaction_date=date(2026, 8, 20),
        amount=976.40,
        reference="ORD-5001",
        normalized_amount=976.40,
        normalized_date=date(2026, 8, 20),
        normalized_ref="5001",
        description="Acme settlement",
        normalized_desc="acme settlement"
    )
    test_db.add(bank1)
    test_db.commit()

    # Run Chained Reconciliation
    run = asyncio.run(service.run_reconciliation(db=test_db, use_ai=False))

    assert run.status == "COMPLETED"
    assert run.matched_count == 1
    assert run.exception_count == 0

    # Verify Match Record
    match = test_db.query(Match).filter_by(run_id=run.run_id).first()
    assert match is not None
    assert match.decision == "MATCH"
    assert match.invoice_id == "INV-001"
    assert match.gateway_txn_id == "GTW-001"
    assert match.bank_txn_id == "BNK-001"

    # Verify Audit Log
    logs = test_db.query(AuditLog).all()
    assert len(logs) >= 1
    assert logs[0].action == "auto_matched"
    assert logs[0].rule_or_reason == "exact_amount_date_ref"


def test_chained_underpayment_with_fee_reconciliation(test_db):
    """
    Tests the Eta Logistics scenario:
    - Invoice: ₹5,000 (INV-107)
    - Gateway: ₹4,500 Gross, ₹90 Fee, ₹16.20 GST, ₹4,393.80 Net (PAY-5007)
    - Bank: ₹4,393.80 (BNK-9005)
    
    Result:
    - Leg 1 has ₹500 underpayment -> Fuzzy Review (Score ~ 0.7472, Amount Sim ~ 0.3679)
    - Leg 2 has exact fee settlement -> 100%
    - 3-Way Match MUST have decision="REVIEW", risk_level="MEDIUM", match_type="FUZZY",
      amount_similarity ~ 0.3679, and explanation stating Leg 1 variance and Leg 2 fee match.
    """
    service = ReconciliationService()

    inv = Invoice(
        invoice_id="INV-107",
        invoice_date=date(2026, 3, 6),
        amount=5000.0,
        invoice_reference="ORD-5007",
        normalized_amount=5000.0,
        normalized_date=date(2026, 3, 6),
        normalized_ref="5007",
        customer_name="Eta Logistics",
        normalized_customer="eta logistics"
    )
    test_db.add(inv)

    gw = GatewayTransaction(
        gateway_txn_id="PAY-5007",
        transaction_date=date(2026, 3, 6),
        amount=4500.0,
        gateway_fee=90.0,
        tax_on_fee=16.20,
        net_settlement=4393.80,
        payment_reference="ORD-5007",
        normalized_amount=4500.0,
        normalized_date=date(2026, 3, 6),
        normalized_ref="5007",
        customer_name="Eta Logistics",
        normalized_customer="eta logistics"
    )
    test_db.add(gw)

    bank = BankTransaction(
        bank_txn_id="BNK-9005",
        transaction_date=date(2026, 3, 6),
        amount=4393.80,
        reference="ORD-5007",
        normalized_amount=4393.80,
        normalized_date=date(2026, 3, 6),
        normalized_ref="5007",
        description="UPI CR ETA LOGISTICS ORD-5007",
        normalized_desc="upi cr eta logistics ord 5007"
    )
    test_db.add(bank)
    test_db.commit()

    run = asyncio.run(service.run_reconciliation(db=test_db, use_ai=False))

    assert run.status == "COMPLETED"
    assert run.review_count == 1

    match = test_db.query(Match).filter_by(run_id=run.run_id).first()
    assert match is not None
    assert match.decision == "REVIEW"
    assert match.risk_level == "MEDIUM"
    assert match.match_type == "FUZZY"
    assert match.amount_similarity < 0.50
    assert match.confidence_score < 0.85
    assert match.reference_similarity == 1.0
    assert match.date_similarity == 1.0
    assert match.customer_similarity == 1.0
    assert "underpayment" in match.explanation.lower()
    assert "Leg 1" in match.explanation or "leg 1" in match.explanation
    assert "Leg 2" in match.explanation or "leg 2" in match.explanation

