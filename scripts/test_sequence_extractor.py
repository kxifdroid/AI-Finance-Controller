import re

def extract_smart_sequence_number(inv_id=None, gw_id=None, bank_id=None, ref=None) -> int:
    for val in [inv_id, gw_id, bank_id, ref]:
        if not val:
            continue
        s = str(val).strip()
        if "_" in s:
            s = s.split("_", 1)[1]
        nums = re.findall(r'\d+', s)
        if nums:
            last_num_str = nums[-1]
            try:
                num = int(last_num_str)
                # If e.g. 1001, 2001, 3001 -> last 3 digits
                if 1000 <= num <= 9999 and num % 1000 != 0:
                    return num % 1000
                elif num >= 100000:
                    return num % 10000
                return num
            except ValueError:
                pass
    return 999999

test_cases = [
    ("INV-2026-00001", "PAY-00001", "BANK-00001"),
    ("INV-2026-00002", "PAY-00002", "BANK-00002"),
    ("INV-2026-00010", "PAY-00010", "BANK-00010"),
    ("INV-2026-00099", "PAY-00099", "BANK-00099"),
    ("INV-2026-00100", "PAY-00100", "BANK-00100"),
    ("INV-3001", "GTX-2001", "BTX-1001"),
    ("INV-3018", "GTX-2018", "BTX-1018"),
    (None, "PAY-00041", "BANK-00041"),
    ("INV-2026-00005", "PAY-00025", None),
]

for inv, gw, bank in test_cases:
    seq = extract_smart_sequence_number(inv, gw, bank)
    print(f"inv={inv}, gw={gw}, bank={bank} -> Sequence: {seq:03d}")
