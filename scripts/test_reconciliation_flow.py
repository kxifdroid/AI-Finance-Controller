import os
import sys
sys.path.insert(0, os.path.abspath('backend'))
import json
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.services.ingestion import IngestionService
from app.services.reconciliation.engine import ReconciliationEngine
from app.models.reconciliation import ReconciliationRun, Match
from app.models.transaction import BankTransaction, GatewayTransaction, Invoice

def test_dataset(folder_name, ext="xlsx"):
    print(f"\n================ TESTING {folder_name} ({ext}) ================")
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    # Load files
    if folder_name == "sample_excel":
        bank_path = f"data/{folder_name}/bank_transactions_extended.{ext}"
        inv_path = f"data/{folder_name}/erp_invoices_extended.{ext}"
        gw_path = f"data/{folder_name}/gateway_transactions_extended.{ext}"
    else:
        bank_path = f"data/{folder_name}/bank_transactions.{ext}"
        inv_path = f"data/{folder_name}/invoices.{ext}"
        gw_path = f"data/{folder_name}/gateway_transactions.{ext}"

    df_b = IngestionService.parse_file(bank_path, ext)
    df_i = IngestionService.parse_file(inv_path, ext)
    df_g = IngestionService.parse_file(gw_path, ext)

    print(f"Bank rows: {len(df_b)}, Invoice rows: {len(df_i)}, Gateway rows: {len(df_g)}")

    type_b, map_b = IngestionService.detect_dataset_type(df_b)
    type_i, map_i = IngestionService.detect_dataset_type(df_i)
    type_g, map_g = IngestionService.detect_dataset_type(df_g)

    print("Bank mapping:", map_b)
    print("Invoice mapping:", map_i)
    print("Gateway mapping:", map_g)

    # Ingest using user mappings (same as /upload/confirm)
    # Apply mapping
    for canonical_field, source_col in map_b.items():
        if source_col in df_b.columns:
            df_b[canonical_field] = df_b[source_col]
    for canonical_field, source_col in map_i.items():
        if source_col in df_i.columns:
            df_i[canonical_field] = df_i[source_col]
    for canonical_field, source_col in map_g.items():
        if source_col in df_g.columns:
            df_g[canonical_field] = df_g[source_col]

    b_records, b_err, _, _ = IngestionService.ingest_bank_transactions(db, df_b, dataset_id="ds_test")
    i_records, i_err, _, _ = IngestionService.ingest_invoices(db, df_i, dataset_id="ds_test")
    g_records, g_err, _, _ = IngestionService.ingest_gateway_transactions(db, df_g, dataset_id="ds_test")
    db.commit()

    print(f"Ingested: Bank={len(b_records)} (errs={len(b_err)}), Invoice={len(i_records)} (errs={len(i_err)}), Gateway={len(g_records)} (errs={len(g_err)})")

    # Run reconciliation
    rec_engine = ReconciliationEngine()
    run = rec_engine.reconcile(db=db, dataset_id="ds_test", use_ai=False)
    db.commit()

    matches = db.query(Match).all()
    match_decisions = [m.decision for m in matches]
    match_types = [m.match_type for m in matches]
    confidences = [m.confidence_score for m in matches]

    print(f"\nResults for {folder_name}:")
    print(f"Total Matches: {len(matches)}")
    print(f"MATCH count: {match_decisions.count('MATCH')}")
    print(f"REVIEW count: {match_decisions.count('REVIEW')}")
    print(f"Match Types breakdown: {pd.Series(match_types).value_counts().to_dict()}")
    print(f"Avg Confidence: {sum(confidences)/len(confidences) if confidences else 0:.2f}")

    if matches:
        print("\nSample 3 matches:")
        for m in matches[:3]:
            print(f"  Match ID: {m.match_id}, Decision: {m.decision}, Type: {m.match_type}, Conf: {m.confidence_score}, Reason: {m.reason_code}, Bank: {m.bank_txn_id}, GW: {m.gateway_txn_id}, Inv: {m.invoice_id}")

if __name__ == "__main__":
    test_dataset("sample_excel", "xlsx")
    test_dataset("sample_new", "xlsx")
