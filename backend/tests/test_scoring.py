"""
Unit tests for ScoringService.
"""

from datetime import date
from app.services.scoring import ScoringService


def test_amount_similarity():
    scorer = ScoringService()
    # Exact match
    assert scorer.calculate_amount_similarity(10000.0, 10000.0) == 1.0
    
    # 2.5% fee discrepancy with fee tolerance flag enabled -> 1.0
    fee_sim = scorer.calculate_amount_similarity(9750.0, 10000.0, allow_fee_variance=True)
    assert fee_sim == 1.0

    # 2.5% fee discrepancy without fee flag enabled -> exponential decay
    decay_sim = scorer.calculate_amount_similarity(9750.0, 10000.0, allow_fee_variance=False)
    assert 0.70 < decay_sim < 0.85

    # 10% discrepancy (beyond 5% tolerance window) -> decays
    diff_sim = scorer.calculate_amount_similarity(9000.0, 10000.0)
    assert diff_sim < 0.50


def test_date_similarity():
    scorer = ScoringService(date_max_tolerance_days=5)
    d1 = date(2026, 8, 20)
    d2 = date(2026, 8, 20)
    d3 = date(2026, 8, 21) # 1 day lag
    d4 = date(2026, 8, 22) # 2 days lag
    d5 = date(2026, 8, 30) # 10 days lag
    
    assert scorer.calculate_date_similarity(d1, d2) == 1.0
    assert scorer.calculate_date_similarity(d1, d3) == 0.95
    assert scorer.calculate_date_similarity(d1, d4) == 0.90
    assert scorer.calculate_date_similarity(d1, d5) == 0.0


def test_reference_similarity():
    scorer = ScoringService()
    assert scorer.calculate_reference_similarity("REF-83921", "PAY-83921") == 1.0
    assert scorer.calculate_reference_similarity("INV/83921", "83921") == 1.0
    assert scorer.calculate_reference_similarity("REF-83921", "REF-99999") < 0.5


def test_customer_similarity():
    scorer = ScoringService()
    assert scorer.calculate_customer_similarity("Acme Technologies Pvt Ltd", "Acme Technologies") == 1.0
    assert scorer.calculate_customer_similarity("Nexus Retail Solutions", "Nexus Retail") >= 0.90
    assert scorer.calculate_customer_similarity("Acme", "Zenith Financial") <= 0.3


def test_composite_score():
    scorer = ScoringService()
    res = scorer.compute_match_score(
        amount_sim=1.0,
        date_sim=0.95,
        reference_sim=1.0,
        customer_sim=1.0,
    )
    assert res["score"] >= 0.98
    assert "Exact monetary amount match" in res["explanation"]
