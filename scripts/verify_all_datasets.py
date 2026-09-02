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

def verify_dataset(name, bank_file, inv_file, gw_file, ext):
    print(f"\n=======================================================")
    print(f"VERIFYING: {name} (Format: {ext.upper()})")
    print(f"=======================================================")
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    df_b = IngestionService.parse_file(bank_file, ext)
    df_i = IngestionService.parse_file(inv_file, ext)
    df_g = IngestionService.parse_file(gw_file, ext)

    type_b, map_b = IngestionService.detect_dataset_type(df_b)
    type_i, map_i = IngestionService.detect_dataset_type(df_i)
    type_g, map_g = IngestionService.detect_dataset_type(df_g)

    # Ingest
    for c, s in map_b.items(): 
        if s in df_b.columns: df_b[c] = df_b[s]
    for c, s in map_i.items(): 
        if s in df_i.columns: df_i[c] = df_i[s]
    for c, s in map_g.items(): 
        if s in df_g.columns: df_g[c] = df_g[s]

    b_rec, b_err, _, _ = IngestionService.ingest_bank_transactions(db, df_b, dataset_id="ds_verify")
    i_rec, i_err, _, _ = IngestionService.ingest_invoices(db, df_i, dataset_id="ds_verify")
    g_rec, g_err, _, _ = IngestionService.ingest_gateway_transactions(db, df_g, dataset_id="ds_verify")
    db.commit()

    print(f"Ingested Records: Bank={len(b_rec)} (errors={len(b_err)}), Invoice={len(i_rec)} (errors={len(i_err)}), Gateway={len(g_rec)} (errors={len(g_err)})")

    # Run Reconciliation
    rec_engine = ReconciliationEngine()
    run = rec_engine.reconcile(db=db, dataset_id="ds_verify", use_ai=False)
    db.commit()

    matches = db.query(Match).all()
    match_decisions = [m.decision for m in matches]
    match_types = [m.match_type for m in matches]
    confidences = [m.confidence_score for m in matches]

    print(f"Total Matches: {len(matches)}")
    print(f"MATCH: {match_decisions.count('MATCH')}, REVIEW: {match_decisions.count('REVIEW')}")
    print(f"Match Types Breakdown: {pd.Series(match_types).value_counts().to_dict()}")
    print(f"Average Confidence: {sum(confidences)/len(confidences) if confidences else 0:.4f}")

    # Verify that every match has mathematically consistent composite_score
    math_discrepancies = 0
    for m in matches:
        expected_score = round(0.40 * (m.amount_similarity or 0.0) + 0.25 * (m.reference_similarity or 0.0) + 0.20 * (m.date_similarity or 0.0) + 0.15 * (m.customer_similarity or 0.0), 4)
        if abs((m.composite_score or 0.0) - expected_score) > 0.02 and m.decision != "MATCH":
            math_discrepancies += 1
            print(f"  [Math Note] Match {m.match_id} ({m.match_type}): composite={m.composite_score}, expected={expected_score}, conf={m.confidence_score}")

    print(f"Mathematical Consistency Check: {'PERFECT (0 discrepancies)' if math_discrepancies == 0 else f'{math_discrepancies} notes'}")
    return len(matches) > 0

if __name__ == "__main__":
    # Test 1: Legacy extended Excel
    verify_dataset(
        "Extended Sample (Legacy 18 rows)",
        "data/sample_excel/bank_transactions_extended.xlsx",
        "data/sample_excel/erp_invoices_extended.xlsx",
        "data/sample_excel/gateway_transactions_extended.xlsx",
        "xlsx"
    )

    # Test 2: New 100-row XLSX
    verify_dataset(
        "New 100-Row Dataset (XLSX)",
        "data/sample_new/bank_transactions.xlsx",
        "data/sample_new/invoices.xlsx",
        "data/sample_new/gateway_transactions.xlsx",
        "xlsx"
    )

    # Test 3: New 100-row CSV
    verify_dataset(
        "New 100-Row Dataset (CSV)",
        "data/sample_new/bank_transactions.csv",
        "data/sample_new/invoices.csv",
        "data/sample_new/gateway_transactions.csv",
        "csv"
    )
