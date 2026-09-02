import os
import sys
sys.path.insert(0, os.path.abspath('backend'))
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.base import Base
from app.services.ingestion import IngestionService
from app.services.reconciliation.engine import ReconciliationEngine
from app.models.reconciliation import Match

engine = create_engine("sqlite:///:memory:")
Base.metadata.create_all(bind=engine)
Session = sessionmaker(bind=engine)
db = Session()

df_b = IngestionService.parse_file("data/sample_new/bank_transactions.xlsx", "xlsx")
df_i = IngestionService.parse_file("data/sample_new/invoices.xlsx", "xlsx")
df_g = IngestionService.parse_file("data/sample_new/gateway_transactions.xlsx", "xlsx")

type_b, map_b = IngestionService.detect_dataset_type(df_b)
type_i, map_i = IngestionService.detect_dataset_type(df_i)
type_g, map_g = IngestionService.detect_dataset_type(df_g)

for c, s in map_b.items(): df_b[c] = df_b[s]
for c, s in map_i.items(): df_i[c] = df_i[s]
for c, s in map_g.items(): df_g[c] = df_g[s]

IngestionService.ingest_bank_transactions(db, df_b, dataset_id="ds1")
IngestionService.ingest_invoices(db, df_i, dataset_id="ds1")
IngestionService.ingest_gateway_transactions(db, df_g, dataset_id="ds1")
db.commit()

rec = ReconciliationEngine()
rec.reconcile(db=db, dataset_id="ds1", use_ai=False)

matches = db.query(Match).all()
print(f"Total matches: {len(matches)}")
print("\nBreakdown of non-MATCH records:")
for m in matches:
    if m.decision != "MATCH":
        print(f"MatchID: {m.match_id}, Type: {m.match_type}, Decision: {m.decision}, Reason: {m.reason_code}, Conf: {m.confidence_score}, Bank: {m.bank_txn_id}, GW: {m.gateway_txn_id}, Inv: {m.invoice_id}, Topology: {m.topology}")
        print(f"  AmtSim={m.amount_similarity}, DateSim={m.date_similarity}, RefSim={m.reference_similarity}, CustSim={m.customer_similarity}, CompScore={m.composite_score}")
        print(f"  Amounts: {m.amounts_json}")
        print(f"  Explanation: {m.explanation.encode('ascii', 'replace').decode('ascii')}")
        print("-" * 50)
