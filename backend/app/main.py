"""
AI Finance Controller - Main FastAPI Application.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables on startup
    init_db()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Enterprise AI Finance Operations Controller & Multi-source Reconciliation Engine",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "operational",
        "llm_provider": settings.LLM_PROVIDER,
        "auto_match_threshold": settings.AUTO_MATCH_THRESHOLD,
        "ai_review_threshold": settings.AI_REVIEW_THRESHOLD,
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}


# Mount API routes
from app.api.router import api_router
app.include_router(api_router)

# Mount static files for uploads
import os
from fastapi.staticfiles import StaticFiles

os.makedirs("uploads/avatars", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

