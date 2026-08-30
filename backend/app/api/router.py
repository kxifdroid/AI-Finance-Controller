"""
Central API Router aggregation.
"""

from fastapi import APIRouter
from app.api.auth import router as auth_router
from app.api.data import router as data_router
from app.api.reconciliation import router as reconciliation_router
from app.api.transactions import router as transactions_router
from app.api.exceptions import router as exceptions_router
from app.api.metrics import router as metrics_router
from app.api.chat import router as chat_router
from app.api.forecast import router as forecast_router
from app.api.upload import router as upload_router
from app.api.approvals import router as approvals_router

api_router = APIRouter(prefix="/api")

api_router.include_router(auth_router)
api_router.include_router(data_router)
api_router.include_router(reconciliation_router)
api_router.include_router(transactions_router)
api_router.include_router(exceptions_router)
api_router.include_router(metrics_router)
api_router.include_router(chat_router)
api_router.include_router(forecast_router)
api_router.include_router(upload_router)
api_router.include_router(approvals_router)
