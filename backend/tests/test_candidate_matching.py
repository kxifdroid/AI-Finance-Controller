"""
Unit tests for CandidateMatchingService.
"""

from datetime import date
from pydantic import BaseModel
from app.services.candidate_matching import CandidateMatchingService


class SimpleBank(BaseModel):
    bank_txn_id: str
    amount: float
    normalized_amount: float
    transaction_date: date
    normalized_date: date
    reference: str
    normalized_ref: str
    description: str


class SimpleGW(BaseModel):
    gateway_txn_id: str
    amount: float
    normalized_amount: float
    transaction_date: date
    normalized_date: date
    payment_reference: str
    normalized_ref: str
    customer_name: str


class SimpleInv(BaseModel):
    invoice_id: str
    amount: float
    normalized_amount: float
    invoice_date: date
    normalized_date: date
    invoice_reference: str
    normalized_ref: str
    customer_name: str


def test_candidate_generation():
    service = CandidateMatchingService(date_tolerance_days=5)

    banks = [
        SimpleBank(
            bank_txn_id="B1",
            amount=10000.0,
            normalized_amount=10000.0,
            transaction_date=date(2026, 8, 20),
            normalized_date=date(2026, 8, 20),
            reference="REF-83921",
            normalized_ref="83921",
            description="NEFT CR - ACME - 83921"
        )
    ]
    gateways = [
        SimpleGW(
            gateway_txn_id="G1",
            amount=10000.0,
            normalized_amount=10000.0,
            transaction_date=date(2026, 8, 19),
            normalized_date=date(2026, 8, 19),
            payment_reference="PAY-83921",
            normalized_ref="83921",
            customer_name="Acme Tech Pvt Ltd"
        )
    ]
    invoices = [
        SimpleInv(
            invoice_id="INV1",
            amount=10000.0,
            normalized_amount=10000.0,
            invoice_date=date(2026, 8, 18),
            normalized_date=date(2026, 8, 18),
            invoice_reference="INV-83921",
            normalized_ref="83921",
            customer_name="Acme Technologies"
        )
    ]

    candidates = service.generate_candidate_triplets(banks, gateways, invoices)
    assert len(candidates) == 1
    c = candidates[0]
    assert c["bank"].bank_txn_id == "B1"
    assert c["gateway"].gateway_txn_id == "G1"
    assert c["invoice"].invoice_id == "INV1"
