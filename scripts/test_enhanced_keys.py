import os
import sys
sys.path.insert(0, os.path.abspath('backend'))
import re
import pandas as pd
from app.services.normalization import NormalizationService

def test_enhanced_keys():
    df_b = pd.read_csv('data/sample_new/bank_transactions.csv')
    df_i = pd.read_csv('data/sample_new/invoices.csv')
    df_g = pd.read_csv('data/sample_new/gateway_transactions.csv')

    print("Total rows each:", len(df_b), len(df_i), len(df_g))

    # Test Leg 1 (Invoice <-> Gateway)
    leg1_matches = 0
    for _, inv in df_i.iterrows():
        i_id = str(inv['invoice_id']).strip()
        i_amt = float(inv['invoice_amount'])
        
        # Check matching GW
        for _, gw in df_g.iterrows():
            gw_inv = str(gw.get('invoice_id', '')).strip()
            gw_ref = str(gw.get('payment_reference', '')).strip()
            gw_amt = float(gw.get('amount', 0.0))
            
            if (i_id == gw_inv or i_id == gw_ref or NormalizationService.normalize_reference(i_id) == NormalizationService.normalize_reference(gw_ref)):
                leg1_matches += 1
                break

    print(f"Leg 1 direct reference matches found: {leg1_matches}/100")

    # Test Leg 2 (Gateway <-> Bank)
    leg2_matches = 0
    for _, gw in df_g.iterrows():
        g_id = str(gw.get('gateway_transaction_id', '')).strip()
        g_settle = str(gw.get('settlement_id', '')).strip()
        g_inv = str(gw.get('invoice_id', '')).strip()
        g_amt = float(gw.get('settlement_amount', gw.get('amount', 0.0)))

        for _, bank in df_b.iterrows():
            b_desc = str(bank.get('narration', '')).strip()
            b_ref = str(bank.get('bank_reference', '')).strip()
            b_settle = str(bank.get('settlement_id', '')).strip()
            b_amt = float(bank.get('amount', 0.0))

            # Match criteria
            if (g_id and g_id in b_desc) or (g_settle and g_settle == b_settle) or (g_settle and g_settle == b_ref) or (g_inv and g_inv in b_desc):
                leg2_matches += 1
                break

    print(f"Leg 2 direct reference/narration/settlement matches found: {leg2_matches}/100")

test_enhanced_keys()
