import os
import uuid
import shutil
import json
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.ingestion import IngestionService
from app.models.dataset import Dataset, FileRecord
from app.models.transaction import BankTransaction, GatewayTransaction, Invoice
from app.services.normalization import NormalizationService
from app.api.auth import get_current_user

router = APIRouter(prefix="/upload", tags=["Upload"])

UPLOAD_DIR = "uploads/temp"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/file")
async def upload_file(
    file: UploadFile = File(...),
):
    """
    Receives an uploaded file, saves it temporarily, parses headers, 
    and returns suggested mappings based on data type detection.
    """
    # 1. Validate file extension
    ext = file.filename.split('.')[-1].lower() if '.' in file.filename else ''
    if ext not in ["csv", "xls", "xlsx", "pdf"]:
        raise HTTPException(status_code=400, detail="Unsupported file format. Please upload CSV, XLS, XLSX, or PDF.")

    # 2. Save file temporarily
    file_id = str(uuid.uuid4())
    filepath = os.path.join(UPLOAD_DIR, f"{file_id}.{ext}")
    
    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        # 3. Parse file
        df = IngestionService.parse_file(filepath, ext)
        if df.empty:
            raise ValueError("File is empty or could not be parsed.")
            
        # 4. Detect type and mapping
        data_type, suggested_mapping = IngestionService.detect_dataset_type(df)
        
        # 5. Return context to UI with 3 real sample values per column
        headers = df.columns.tolist()
        preview = df.head(3).fillna("").to_dict(orient="records")
        column_previews = IngestionService.get_column_previews(df, max_samples=3)
        from app.services.ingestion import TARGET_SCHEMAS
        target_schema = TARGET_SCHEMAS.get(data_type, {})
        
        return {
            "file_id": file_id,
            "filename": file.filename,
            "file_type": ext,
            "row_count": len(df),
            "headers": headers,
            "preview": preview,
            "column_previews": column_previews,
            "detected_type": data_type,
            "suggested_mapping": suggested_mapping,
            "target_schema": target_schema
        }
    except Exception as e:
        if os.path.exists(filepath):
            os.remove(filepath)
        raise HTTPException(status_code=500, detail=f"Failed to process file: {str(e)}")


from pydantic import BaseModel

class SingleFileMapping(BaseModel):
    file_id: str
    filename: str
    file_type: str
    data_type: str # BANK, GATEWAY, INVOICE
    # mapping: canonical_field -> source_column
    # e.g. {"invoice_id": "Invoice Number", "amount": "Total Amount"}
    mapping: Dict[str, str]

class MappingConfirmRequest(BaseModel):
    dataset_name: str
    files: List[SingleFileMapping]

@router.post("/confirm")
def confirm_mapping(
    req: MappingConfirmRequest,
    db: Session = Depends(get_db)
):
    """
    Applies the user-confirmed column mapping for multiple files, normalizes the data,
    creates a Dataset, and ingests into the respective tables with idempotency.
    """
    if not req.files:
        raise HTTPException(status_code=400, detail="No files provided to confirm.")

    # Create dataset
    dataset = Dataset(id=str(uuid.uuid4()), name=req.dataset_name, status="PROCESSED")
    db.add(dataset)
    
    total_records = 0
    all_errors = []
    files_result = []

    for f_req in req.files:
        filepath = os.path.join(UPLOAD_DIR, f"{f_req.file_id}.{f_req.file_type}")
        if not os.path.exists(filepath):
            db.rollback()
            raise HTTPException(status_code=404, detail=f"Uploaded file not found: {f_req.filename}. It may have expired.")

        try:
            df = IngestionService.parse_file(filepath, f_req.file_type)

            required = []
            if f_req.data_type == "BANK":
                required = ["bank_txn_id", "transaction_date", "amount"]
            elif f_req.data_type == "GATEWAY":
                required = ["gateway_txn_id", "transaction_date", "gross_amount"]
            elif f_req.data_type == "INVOICE":
                required = ["invoice_id", "invoice_date", "amount"]

            for req_field in required:
                # Check for either direct mapping or valid alias (e.g. gross_amount / amount)
                mapped_col = f_req.mapping.get(req_field)
                if not mapped_col and f_req.data_type == "GATEWAY" and req_field == "gross_amount":
                    mapped_col = f_req.mapping.get("amount")
                if not mapped_col or not str(mapped_col).strip():
                    raise ValueError(f"Missing required mapping for canonical field '{req_field}'.")
                if str(mapped_col) not in df.columns:
                    raise ValueError(f"Mapped source column '{mapped_col}' for canonical field '{req_field}' was not found in {f_req.filename}.")

            # Apply user mapping to create canonical columns
            for canonical_field, source_col in f_req.mapping.items():
                source_col = str(source_col)
                if source_col and source_col in df.columns:
                    df[canonical_field] = df[source_col]
                    
            # Aliasing for common variations
            if f_req.data_type == "GATEWAY":
                if "gross_amount" in df.columns and "amount" not in df.columns:
                    df["amount"] = df["gross_amount"]
                if "amount" in df.columns and "gross_amount" not in df.columns:
                    df["gross_amount"] = df["amount"]
                if "order_id" in df.columns and "payment_reference" not in df.columns:
                    df["payment_reference"] = df["order_id"]
            elif f_req.data_type == "INVOICE":
                if "order_id" in df.columns and "invoice_reference" not in df.columns:
                    df["invoice_reference"] = df["order_id"]
            elif f_req.data_type == "BANK":
                if "order_id" in df.columns and "reference" not in df.columns:
                    df["reference"] = df["order_id"]

            file_record = FileRecord(
                id=f_req.file_id,
                dataset_id=dataset.id,
                filename=f_req.filename,
                file_type=f_req.file_type,
                data_type=f_req.data_type,
                status="PROCESSED",
                record_count=len(df),
                mapping_config=json.dumps(f_req.mapping)
            )
            db.add(file_record)
            
            errors = []
            ingested_count = 0
            skipped_count = 0

            if f_req.data_type == "BANK":
                _, errs, ingested_count, skipped_count = IngestionService.ingest_bank_transactions(db, df, dataset_id=dataset.id)
                errors = errs
            elif f_req.data_type == "GATEWAY":
                _, errs, ingested_count, skipped_count = IngestionService.ingest_gateway_transactions(db, df, dataset_id=dataset.id)
                errors = errs
            elif f_req.data_type == "INVOICE":
                _, errs, ingested_count, skipped_count = IngestionService.ingest_invoices(db, df, dataset_id=dataset.id)
                errors = errs

            # Audit log skipped duplicates if any
            if skipped_count > 0:
                from app.services.audit import AuditService
                AuditService.log(
                    db=db,
                    entity_type="dataset",
                    entity_id=dataset.id,
                    action="skipped_duplicates",
                    rule_or_reason=f"Idempotent ingestion skipped {skipped_count} identical duplicate rows in {f_req.filename}",
                    actor="system",
                    after_status="deduplicated"
                )
                
            file_record.error_count = len(errors)
            all_errors.extend(errors)
            total_records += ingested_count
            
            if errors and len(errors) == len(df):
                file_record.status = "FAILED"
                raise ValueError(f"All rows failed to ingest in {f_req.filename}: {errors[0]}")
                
            files_result.append({
                "file_type": f_req.data_type,
                "status": "ingested",
                "rows_received": len(df),
                "rows_ingested": ingested_count,
                "rows_skipped_as_duplicate": skipped_count,
                "errors": len(errors)
            })
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=400, detail=f"Failed to ingest {f_req.filename}: {str(e)}")

    db.commit()

    return {
        "success": True,
        "dataset_id": dataset.id,
        "files": files_result
    }
