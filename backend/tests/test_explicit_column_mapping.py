import pytest
import pandas as pd
from app.services.ingestion import IngestionService


def test_explicit_column_mapping_with_synonyms_and_excludes():
    # Fixture with ambiguous columns that share generic terms (ID, Amount)
    df_fixture = pd.DataFrame(columns=["Order ID", "Invoice ID", "Gross Amount", "Net Amount", "Date", "Customer"])

    # 1. Test Invoice auto-mapping
    inv_mapping = IngestionService.auto_map_columns(df_fixture, "INVOICE")
    assert inv_mapping.get("invoice_id") == "Invoice ID"
    assert inv_mapping.get("invoice_reference") == "Order ID"
    assert inv_mapping.get("amount") == "Gross Amount" or inv_mapping.get("amount") in ["Gross Amount", "Net Amount"]
    # Ensure invoice_id did NOT match 'Order ID'
    assert inv_mapping.get("invoice_id") != "Order ID"

    # 2. Test Gateway auto-mapping with Gross vs Net separation
    gw_mapping = IngestionService.auto_map_columns(df_fixture, "GATEWAY")
    assert gw_mapping.get("gross_amount") == "Gross Amount"
    assert gw_mapping.get("net_amount") == "Net Amount"
    assert gw_mapping.get("payment_reference") == "Order ID"

    # Ensure net_amount did NOT map to Gross Amount or Order ID
    assert gw_mapping.get("net_amount") != "Gross Amount"
    assert gw_mapping.get("net_amount") != "Order ID"
    assert gw_mapping.get("gross_amount") != "Net Amount"


def test_column_previews_extraction():
    df = pd.DataFrame({
        "Invoice ID": ["INV-001", "INV-002", "INV-003", "INV-004"],
        "Amount": ["1,000.00", "2,500.00", "5,000.00", "10,000.00"]
    })

    previews = IngestionService.get_column_previews(df, max_samples=3)
    assert len(previews["Invoice ID"]) == 3
    assert previews["Invoice ID"] == ["INV-001", "INV-002", "INV-003"]
    assert previews["Amount"] == ["1,000.00", "2,500.00", "5,000.00"]
