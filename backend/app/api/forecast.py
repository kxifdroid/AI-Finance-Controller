"""
Cash Flow Forecast API Routes.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.forecast import CashForecastResponse
from app.services.forecasting import ForecastingService

router = APIRouter(prefix="/forecast", tags=["Forecast"])


@router.get("", response_model=CashForecastResponse)
def get_cash_forecast(dataset_id: Optional[str] = None, db: Session = Depends(get_db)):
    """
    Returns 7-day rule-based rolling cash projection with transparent assumptions.
    """
    try:
        forecast_data = ForecastingService.generate_7day_forecast(db=db, dataset_id=dataset_id)
        return forecast_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cash forecast calculation failed: {str(e)}")
