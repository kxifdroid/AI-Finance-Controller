"""
Data Ingestion and Dataset Management API Routes.
"""

import sys
import os

# Add scripts directory to path for generate_dataset import
# Navigate from backend/app/api/data.py up to project root, then into scripts
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
scripts_dir = os.path.join(project_root, "scripts")
if scripts_dir not in sys.path:
    sys.path.insert(0, scripts_dir)

from typing import Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.ingestion import IngestionService
from generate_dataset import generate_synthetic_data

router = APIRouter(prefix="/data", tags=["Data"])


@router.post("/generate")
def generate_dataset(
    count: int = 250,
    seed: int = 42,
    db: Session = Depends(get_db),
):
    """
    Generates a new synthetic dataset with realistic noise and loads it directly into the database.
    """
    try:
        gen_res = generate_synthetic_data(count=count, seed=seed)
        
        # Ingest the generated CSVs into the active database
        b_records, b_errs, b_ingested, b_skipped = IngestionService.ingest_bank_transactions(db, gen_res["bank_path"])
        g_records, g_errs, g_ingested, g_skipped = IngestionService.ingest_gateway_transactions(db, gen_res["gateway_path"])
        i_records, i_errs, i_ingested, i_skipped = IngestionService.ingest_invoices(db, gen_res["invoice_path"])

        db.commit()

        return {
            "status": "success",
            "message": f"Generated and loaded {b_ingested} Bank, {g_ingested} Gateway, and {i_ingested} Invoice records.",
            "bank_records_count": b_ingested,
            "gateway_records_count": g_ingested,
            "invoice_records_count": i_ingested,
            "rows_skipped_as_duplicate": b_skipped + g_skipped + i_skipped,
            "ground_truth_count": gen_res["ground_truth_count"],
            "errors": b_errs + g_errs + i_errs,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dataset generation failed: {str(e)}")


@router.post("/upload")
async def upload_csvs(
    bank_file: Optional[UploadFile] = File(None),
    gateway_file: Optional[UploadFile] = File(None),
    invoice_file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    """
    Uploads and validates custom CSV files for Bank, Gateway, or Invoice records.
    """
    results = {}
    errors = []

    if bank_file:
        content = await bank_file.read()
        records, errs, b_ingested, b_skipped = IngestionService.ingest_bank_transactions(db, content)
        results["bank_records_loaded"] = b_ingested
        results["bank_records_skipped"] = b_skipped
        errors.extend(errs)

    if gateway_file:
        content = await gateway_file.read()
        records, errs, g_ingested, g_skipped = IngestionService.ingest_gateway_transactions(db, content)
        results["gateway_records_loaded"] = g_ingested
        results["gateway_records_skipped"] = g_skipped
        errors.extend(errs)

    if invoice_file:
        content = await invoice_file.read()
        records, errs, i_ingested, i_skipped = IngestionService.ingest_invoices(db, content)
        results["invoice_records_loaded"] = i_ingested
        results["invoice_records_skipped"] = i_skipped
        errors.extend(errs)

    db.commit()

    return {
        "status": "success" if not errors else "partial_success",
        "results": results,
        "errors": errors,
    }
