"""
Pydantic schemas for the 7-day cash forecast.
"""

from datetime import date
from typing import List
from pydantic import BaseModel, ConfigDict


class ForecastPoint(BaseModel):
    forecast_date: date
    day_offset: int
    cleared_cash: float
    expected_settlements: float
    expected_receivables: float
    upcoming_payouts: float
    recurring_expenses: float
    projected_balance: float
    confidence_level: str
    assumptions_notes: str

    model_config = ConfigDict(from_attributes=True)


class CashForecastResponse(BaseModel):
    generated_at: str
    current_cleared_cash: float
    forecast_points: List[ForecastPoint]
    methodology: str = "Rule-based cash forecast: Cleared Cash + Settling Payments (T+2) + Open Receivables - Estimated Disbursements"
    limitations: str = "Deterministic projection based on existing invoice due dates and gateway settlement schedules. Not a stochastic or market-risk predictive model."
