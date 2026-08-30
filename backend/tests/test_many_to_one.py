"""
Automated Test Suite for Many-to-One Batch Settlement Matching (Phase 6).

Problem Solved:
Verifies that the settlement matcher and reconciliation engine can accurately
identify and aggregate multiple payment gateway transactions batched into a single
bank payout deposit, with exact subset-sum proof and structured evidence generation.

Tests:
1. Exact 3-to-1 batch matching totaling ₹1,000.
2. 4-to-1 batch matching with fee and GST decomposition.
3. Unmatched singleton handling when subset sum does not match.
4. End-to-end reconciliation engine batch settlement workflow.
"""

import json
import asyncio
import pytest
from datetime import date, datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.transaction import BankTransaction, GatewayTransaction, Invoice
from app.models.reconciliation import Match, ReconciliationRun
from app.services.reconciliation.settlement_matcher import SettlementMatcher
from app.services.reconciliation.engine import ReconciliationEngine


@pytest.fixture
def test_db(tmp_path):
    db_file = tmp_path / "test_many_to_one.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_three_gateway_txns_matching_one_bank_deposit_1000():
    """
    Tests that 3 gateway transactions totaling ₹1,000 (300 + 400 + 300)
    match a single aggregate bank deposit of ₹1,000.
    """
    gw1 = GatewayTransaction(
        gateway_txn_id="GW-MTO-1",
        transaction_date=date(2026, 8, 20),
        amount=300.0,
        net_settlement=300.0,
        payment_reference="ORD-300A",
        normalized_amount=300.0,
        normalized_date=date(2026, 8, 20),
    )
    gw2 = GatewayTransaction(
        gateway_txn_id="GW-MTO-2",
        transaction_date=date(2026, 8, 20),
        amount=400.0,
        net_settlement=400.0,
        payment_reference="ORD-400B",
        normalized_amount=400.0,
        normalized_date=date(2026, 8, 20),
    )
    gw3 = GatewayTransaction(
        gateway_txn_id="GW-MTO-3",
        transaction_date=date(2026, 8, 21),
        amount=300.0,
        net_settlement=300.0,
        payment_reference="ORD-300C",
        normalized_amount=300.0,
        normalized_date=date(2026, 8, 21),
    )

    bank_deposit = BankTransaction(
        bank_txn_id="BNK-BATCH-1000",
        transaction_date=date(2026, 8, 22),
        amount=1000.0,
        reference="BATCH-PAYOUT-1000",
        normalized_amount=1000.0,
        normalized_date=date(2026, 8, 22),
        description="Razorpay Batch Payout 3 TXNS",
    )

    batch_matches, matched_bank_ids, matched_gw_ids = SettlementMatcher.match_settlements(
        unmatched_banks=[bank_deposit],
        unmatched_gateways=[gw1, gw2, gw3],
    )

    assert len(batch_matches) == 1
    assert "BNK-BATCH-1000" in matched_bank_ids
    assert len(matched_gw_ids) == 3
    assert {"GW-MTO-1", "GW-MTO-2", "GW-MTO-3"} == matched_gw_ids

    match = batch_matches[0]
    assert match["match_type"] == "MANY_TO_ONE"
    assert match["decision"] in ("MATCH", "REVIEW")
    assert match["total_net"] == 1000.0
    assert match["variance"] == 0.0
    assert match["confidence"] == 0.95

    # Check evidence structure
    evidence = json.loads(match["evidence_json"])
    assert evidence["match_type"] == "MANY_TO_ONE"
    assert evidence["amounts"]["bank_credit"] == 1000.0
    assert evidence["amounts"]["gateway_net_sum"] == 1000.0
    assert evidence["amounts"]["variance"] == 0.0
    assert len(evidence["extra"]["batch_composition"]) == 3


def test_four_gateway_txns_with_fee_decomposition():
    """
    Tests 4 gateway transactions with 2% MDR + 18% GST fee decomposition
    matching the exact aggregate net payout in the bank statement.
    """
    # Gross: 2000 (net 1952.8), 3000 (net 2929.2), 1500 (net 1464.6), 3500 (net 3417.4)
    # Total Gross: 10000.0, Total Fee: 200.0, Total Tax: 36.0, Total Net: 9764.0
    gw1 = GatewayTransaction(
        gateway_txn_id="GW-FEE-1",
        transaction_date=date(2026, 8, 10),
        amount=2000.0,
        gross_amount=2000.0,
        gateway_fee=40.0,
        tax_on_fee=7.20,
        net_settlement=1952.80,
        normalized_amount=2000.0,
        normalized_date=date(2026, 8, 10),
    )
    gw2 = GatewayTransaction(
        gateway_txn_id="GW-FEE-2",
        transaction_date=date(2026, 8, 10),
        amount=3000.0,
        gross_amount=3000.0,
        gateway_fee=60.0,
        tax_on_fee=10.80,
        net_settlement=2929.20,
        normalized_amount=3000.0,
        normalized_date=date(2026, 8, 10),
    )
    gw3 = GatewayTransaction(
        gateway_txn_id="GW-FEE-3",
        transaction_date=date(2026, 8, 11),
        amount=1500.0,
        gross_amount=1500.0,
        gateway_fee=30.0,
        tax_on_fee=5.40,
        net_settlement=1464.60,
        normalized_amount=1500.0,
        normalized_date=date(2026, 8, 11),
    )
    gw4 = GatewayTransaction(
        gateway_txn_id="GW-FEE-4",
        transaction_date=date(2026, 8, 11),
        amount=3500.0,
        gross_amount=3500.0,
        gateway_fee=70.0,
        tax_on_fee=12.60,
        net_settlement=3417.40,
        normalized_amount=3500.0,
        normalized_date=date(2026, 8, 11),
    )

    bank_deposit = BankTransaction(
        bank_txn_id="BNK-BATCH-9764",
        transaction_date=date(2026, 8, 12),
        amount=9764.0,
        reference="RAZORPAY-BATCH-9764",
        normalized_amount=9764.0,
        normalized_date=date(2026, 8, 12),
        description="Razorpay Net Settlement Payout",
    )

    batch_matches, matched_banks, matched_gws = SettlementMatcher.match_settlements(
        unmatched_banks=[bank_deposit],
        unmatched_gateways=[gw1, gw2, gw3, gw4],
    )

    assert len(batch_matches) == 1
    assert "BNK-BATCH-9764" in matched_banks
    assert len(matched_gws) == 4
    bm = batch_matches[0]
    assert bm["total_gross"] == 10000.0
    assert bm["total_fee"] == 200.0
    assert bm["total_tax"] == 36.0
    assert bm["total_net"] == 9764.0
    assert bm["variance"] == 0.0


def test_no_batch_match_when_amounts_do_not_sum():
    """
    Verifies that when gateway transactions do not sum to the bank deposit,
    no false batch match is created.
    """
    gw1 = GatewayTransaction(
        gateway_txn_id="GW-NO-1",
        transaction_date=date(2026, 8, 10),
        amount=250.0,
        net_settlement=250.0,
        normalized_amount=250.0,
        normalized_date=date(2026, 8, 10),
    )
    gw2 = GatewayTransaction(
        gateway_txn_id="GW-NO-2",
        transaction_date=date(2026, 8, 10),
        amount=300.0,
        net_settlement=300.0,
        normalized_amount=300.0,
        normalized_date=date(2026, 8, 10),
    )

    # Bank deposit is 1000.0 (sum is 550.0)
    bank_deposit = BankTransaction(
        bank_txn_id="BNK-NO-MATCH",
        transaction_date=date(2026, 8, 11),
        amount=1000.0,
        normalized_amount=1000.0,
        normalized_date=date(2026, 8, 11),
    )

    batch_matches, matched_banks, matched_gws = SettlementMatcher.match_settlements(
        unmatched_banks=[bank_deposit],
        unmatched_gateways=[gw1, gw2],
    )

    assert len(batch_matches) == 0
    assert len(matched_banks) == 0
    assert len(matched_gws) == 0


def test_reconciliation_engine_many_to_one_e2e(test_db):
    """
    Tests end-to-end reconciliation execution with many-to-one batch matching.
    """
    # 1. Add 3 Invoices
    test_db.add(Invoice(
        invoice_id="INV-B1",
        amount=500.0,
        invoice_date=date(2026, 8, 20),
        invoice_reference="REF-B1",
        normalized_amount=500.0,
        normalized_date=date(2026, 8, 20),
        normalized_ref="refb1",
        customer_name="Acme Corp",
        normalized_customer="acme corp",
    ))
    test_db.add(Invoice(
        invoice_id="INV-B2",
        amount=300.0,
        invoice_date=date(2026, 8, 20),
        invoice_reference="REF-B2",
        normalized_amount=300.0,
        normalized_date=date(2026, 8, 20),
        normalized_ref="refb2",
        customer_name="Beta LLC",
        normalized_customer="beta llc",
    ))
    test_db.add(Invoice(
        invoice_id="INV-B3",
        amount=200.0,
        invoice_date=date(2026, 8, 20),
        invoice_reference="REF-B3",
        normalized_amount=200.0,
        normalized_date=date(2026, 8, 20),
        normalized_ref="refb3",
        customer_name="Gamma Inc",
        normalized_customer="gamma inc",
    ))

    # 2. Add 3 Gateway Transactions (matching Invoices 1-to-1 in Leg 1)
    test_db.add(GatewayTransaction(
        gateway_txn_id="GW-B1",
        amount=500.0,
        transaction_date=date(2026, 8, 20),
        payment_reference="REF-B1",
        net_settlement=500.0,
        normalized_amount=500.0,
        normalized_date=date(2026, 8, 20),
        normalized_ref="refb1",
        customer_name="Acme Corp",
        normalized_customer="acme corp",
    ))
    test_db.add(GatewayTransaction(
        gateway_txn_id="GW-B2",
        amount=300.0,
        transaction_date=date(2026, 8, 20),
        payment_reference="REF-B2",
        net_settlement=300.0,
        normalized_amount=300.0,
        normalized_date=date(2026, 8, 20),
        normalized_ref="refb2",
        customer_name="Beta LLC",
        normalized_customer="beta llc",
    ))
    test_db.add(GatewayTransaction(
        gateway_txn_id="GW-B3",
        amount=200.0,
        transaction_date=date(2026, 8, 20),
        payment_reference="REF-B3",
        net_settlement=200.0,
        normalized_amount=200.0,
        normalized_date=date(2026, 8, 20),
        normalized_ref="refb3",
        customer_name="Gamma Inc",
        normalized_customer="gamma inc",
    ))

    # 3. Add 1 aggregate Bank deposit of ₹1,000 (with no 1-to-1 reference to any single invoice)
    test_db.add(BankTransaction(
        bank_txn_id="BNK-AGG-1000",
        amount=1000.0,
        transaction_date=date(2026, 8, 21),
        reference="NODAL-SETTLEMENT-AGG",
        normalized_amount=1000.0,
        normalized_date=date(2026, 8, 21),
        description="Razorpay Nodal Payout Daily Aggregate",
        normalized_desc="razorpay nodal payout daily aggregate",
        normalized_ref="nodalsettlementagg",
    ))

    test_db.commit()

    engine = ReconciliationEngine()
    run = asyncio.run(engine.run_reconciliation(db=test_db, use_ai=False))

    assert run.status == "COMPLETED"
    assert run.matched_count >= 1 or run.review_count >= 1

    matches = test_db.query(Match).filter_by(run_id=run.run_id).all()
    # Check that batch matches exist
    batch_matches = [m for m in matches if m.match_type == "MANY_TO_ONE"]
    assert len(batch_matches) >= 1
    for bm in batch_matches:
        assert bm.bank_txn_id == "BNK-AGG-1000"

