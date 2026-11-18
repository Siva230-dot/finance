import io

import fitz
import openpyxl

from tests.conftest import add_tx

API = "/api/v1/uploads/statements"

CSV = b"""Bank of Example - Statement
Account: XXXX1234
Date,Narration,Withdrawal Amt,Deposit Amt,Balance
01/11/2026,SALARY ACME CORP,,55000.00,60000.00
03/11/2026,UPI-SWIGGY-ORDER 99887766,450.00,,59550.00
04/11/2026,UBER TRIP,"1,200.50",,58349.50
04/11/2026,UBER TRIP,"1,200.50",,57149.00
05/11/2026,ZQXW MERCHANT,300.00,,56849.00
,Closing balance,,,56849.00
"""


def _upload(client, auth, name, data, ctype):
    return client.post(API, files={"file": (name, data, ctype)}, headers=auth)


def test_csv_preview_and_approve(client, auth):
    add_tx(client, auth, description="Uber trip", amount="1200.50", date="2026-11-04")  # existing -> duplicate
    r = _upload(client, auth, "statement.csv", CSV, "text/csv")
    assert r.status_code == 201, r.text
    p = r.json()
    rows = p["rows"]
    assert len(rows) == 5
    assert rows[0]["type"] == "income" and rows[0]["amount"] == "55000.00" and rows[0]["category_slug"] == "income"
    assert rows[1]["category_slug"] == "food" and rows[1]["transaction_date"] == "2026-11-03"
    assert rows[2]["amount"] == "1200.50" and rows[2]["is_duplicate"] and rows[2]["duplicate_reason"] == "Already recorded"
    assert rows[3]["is_duplicate"]
    assert rows[4]["category_slug"] == "other" and rows[4]["categorization_source"] == "default"
    assert p["duplicates"] == 2
    # Nothing saved before approval
    assert client.get("/api/v1/transactions", headers=auth).json()["total"] == 1
    cats = {c["slug"]: c["id"] for c in client.get("/api/v1/categories", headers=auth).json()}
    ok = client.post(f"{API}/{p['upload_id']}/approve", json={"selected_indexes": [0, 1, 4], "category_overrides": {"4": cats["shopping"]}}, headers=auth)
    assert ok.status_code == 200 and ok.json()["imported"] == 3
    txs = client.get("/api/v1/transactions", params={"search": "ZQXW"}, headers=auth).json()["items"]
    assert txs[0]["category"]["slug"] == "shopping" and txs[0]["categorization_source"] == "user"
    assert client.post(f"{API}/{p['upload_id']}/approve", json={"selected_indexes": [0]}, headers=auth).status_code == 409


def test_reject_import(client, auth):
    p = _upload(client, auth, "s.csv", CSV, "text/csv").json()
    assert client.post(f"{API}/{p['upload_id']}/reject", headers=auth).status_code == 204
    assert client.get("/api/v1/transactions", headers=auth).json()["total"] == 0


def test_upload_isolated(client, auth, other_auth):
    p = _upload(client, auth, "s.csv", CSV, "text/csv").json()
    assert client.post(f"{API}/{p['upload_id']}/approve", json={"selected_indexes": [0]}, headers=other_auth).status_code == 404


def test_xlsx(client, auth):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Txn Date", "Description", "Amount", "Dr/Cr"])
    ws.append(["2026-11-02", "Amazon order", 1999, "DR"])
    ws.append(["2026-11-03", "Refund", 200, "CR"])
    buf = io.BytesIO()
    wb.save(buf)
    r = _upload(client, auth, "s.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    assert r.status_code == 201, r.text
    rows = r.json()["rows"]
    assert rows[0]["type"] == "expense" and rows[0]["category_slug"] == "shopping"
    assert rows[1]["type"] == "income"


def _pdf(lines):
    doc = fitz.open()
    page = doc.new_page()
    y = 72
    for line in lines:
        page.insert_text((40, y), line, fontsize=9)
        y += 14
    data = doc.tobytes()
    doc.close()
    return data


def test_text_pdf(client, auth):
    data = _pdf(["Statement of account", "05/11/2026 NETFLIX SUBSCRIPTION 649.00 Dr 10000.00", "06/11/2026 SALARY CREDIT 50000.00 Cr 60000.00"])
    r = _upload(client, auth, "s.pdf", data, "application/pdf")
    assert r.status_code == 201, r.text
    rows = r.json()["rows"]
    assert len(rows) == 2 and rows[0]["category_slug"] == "subscriptions" and rows[1]["type"] == "income"


def test_scanned_pdf_rejected_clearly(client, auth):
    doc = fitz.open()
    doc.new_page()
    data = doc.tobytes()
    r = _upload(client, auth, "scan.pdf", data, "application/pdf")
    assert r.status_code == 422 and r.json()["error"]["code"] == "pdf_scanned"


def test_file_validation(client, auth):
    assert _upload(client, auth, "x.exe", b"MZ....", "application/octet-stream").json()["error"]["code"] == "invalid_file"
    assert _upload(client, auth, "x.pdf", b"not a pdf at all", "application/pdf").status_code == 400
    assert _upload(client, auth, "x.csv", CSV, "image/png").status_code == 400
    assert _upload(client, auth, "x.csv", b"", "text/csv").status_code == 400
    big = b"a,b\n" + b"1,2\n" * (3 * 1024 * 1024)
    assert _upload(client, auth, "x.csv", big, "text/csv").status_code == 413
    assert _upload(client, auth, "x.csv", b"foo,bar\n1,2\n", "text/csv").json()["error"]["code"] == "unrecognized_format"
