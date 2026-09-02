import os
import sys
sys.path.insert(0, os.path.abspath('backend'))
import pandas as pd

df_b = pd.read_csv('data/sample_new/bank_transactions.csv')
df_i = pd.read_csv('data/sample_new/invoices.csv')
df_g = pd.read_csv('data/sample_new/gateway_transactions.csv')

print("Bank rows:", len(df_b))
print("Invoice rows:", len(df_i))
print("Gateway rows:", len(df_g))

print("\n--- Bank sample rows ---")
print(df_b.head(5)[['transaction_id', 'bank_reference', 'narration', 'amount', 'settlement_id']])

print("\n--- Invoice sample rows ---")
print(df_i.head(5)[['invoice_id', 'customer_name', 'invoice_amount']])

print("\n--- Gateway sample rows ---")
print(df_g.head(5)[['payment_id', 'gateway_transaction_id', 'invoice_id', 'amount', 'fee', 'settlement_amount', 'settlement_id']])

# Check how rows 1-100 are structured in new dataset:
# Let's inspect different segments of rows in the new dataset:
print("\n--- Segment 1-60 (Clean 1-1 matches) ---")
print("Bank 1:", df_b.iloc[0].to_dict())
print("Inv 1:", df_i.iloc[0].to_dict())
print("GW 1:", df_g.iloc[0].to_dict())

print("\n--- Segment 61-70 (USD currency / timing?) ---")
print("Bank 62:", df_b.iloc[61].to_dict())
print("Inv 62:", df_i.iloc[61].to_dict())
print("GW 62:", df_g.iloc[61].to_dict())

print("\n--- Segment 71-80 (Duplicates / Settlements) ---")
print("Bank 71:", df_b.iloc[70].to_dict())
print("Inv 71:", df_i.iloc[70].to_dict())
print("GW 71:", df_g.iloc[70].to_dict())

print("\n--- Segment 81-85 (Fee & Net settlements) ---")
print("Bank 81:", df_b.iloc[80].to_dict())
print("Inv 81:", df_i.iloc[80].to_dict())
print("GW 81:", df_g.iloc[80].to_dict())

print("\n--- Segment 86-90 (Part payments) ---")
print("Bank 86:", df_b.iloc[85].to_dict())
print("Inv 86:", df_i.iloc[85].to_dict())
print("GW 86:", df_g.iloc[85].to_dict())

print("\n--- Segment 91-95 (Duplicate settlements) ---")
print("Bank 91:", df_b.iloc[90].to_dict())
print("Inv 91:", df_i.iloc[90].to_dict())
print("GW 91:", df_g.iloc[90].to_dict())

print("\n--- Segment 96-100 (Unmatched) ---")
print("Bank 96:", df_b.iloc[95].to_dict())
print("Inv 96:", df_i.iloc[95].to_dict())
print("GW 96:", df_g.iloc[95].to_dict())
