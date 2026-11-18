"""Bank statement extraction (CSV, XLSX, text-based PDF). Files live only in a temp dir during parsing."""
import io
import logging
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import filetype
import pandas as pd

from app.core.errors import AppError

logger = logging.getLogger("financemate.statements")

ALLOWED = {
    "csv": {"text/csv", "application/csv", "text/plain", "application/vnd.ms-excel", "application/octet-stream"},
    "xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/octet-stream", "application/zip"},
    "pdf": {"application/pdf", "application/octet-stream"},
}
MAX_ROWS = 5000

DATE_COLS = ["date", "txn date", "transaction date", "value date", "posting date", "tran date", "value dt", "txn dt"]
DESC_COLS = ["description", "narration", "particulars", "details", "remarks", "transaction details", "memo", "payee"]
AMOUNT_COLS = ["amount", "transaction amount", "amt", "amount (inr)", "amount(inr)"]
DEBIT_COLS = ["debit", "withdrawal", "withdrawal amt", "withdrawal amount", "debit amount", "dr", "withdrawals", "paid out"]
CREDIT_COLS = ["credit", "deposit", "deposit amt", "deposit amount", "credit amount", "cr", "deposits", "paid in"]
TYPE_COLS = ["type", "dr/cr", "cr/dr", "transaction type", "txn type"]

DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y", "%d %b %Y", "%d-%b-%Y", "%d %b %y", "%d-%b-%y",
                "%d.%m.%Y", "%b %d, %Y", "%d %B %Y", "%m/%d/%Y", "%Y/%m/%d"]


@dataclass
class ExtractedRow:
    transaction_date: date
    description: str
    amount: Decimal
    type: str


def validate_upload(filename: str, content_type: str | None, data: bytes, max_bytes: int) -> str:
    if not filename or "." not in filename:
        raise AppError(400, "invalid_file", "File must have a .csv, .xlsx or .pdf extension")
    ext = filename.rsplit(".", 1)[1].lower()
    if ext not in ALLOWED:
        raise AppError(400, "invalid_file", "Unsupported file type. Upload CSV, XLSX or PDF.")
    if len(data) == 0:
        raise AppError(400, "invalid_file", "The file is empty")
    if len(data) > max_bytes:
        raise AppError(413, "file_too_large", f"File exceeds the {max_bytes // (1024 * 1024)} MB limit")
    if content_type and content_type.split(";")[0].strip().lower() not in ALLOWED[ext]:
        raise AppError(400, "invalid_file", "File content type does not match its extension")
    kind = filetype.guess(data[:8192])
    if ext == "pdf" and (kind is None or kind.mime != "application/pdf"):
        raise AppError(400, "invalid_file", "File is not a valid PDF")
    if ext == "xlsx" and (kind is None or kind.extension not in ("xlsx", "zip")):
        raise AppError(400, "invalid_file", "File is not a valid XLSX workbook")
    if ext == "csv":
        if kind is not None and kind.mime not in ("text/plain",):
            raise AppError(400, "invalid_file", "File is not a valid CSV")
        try:
            data[:65536].decode("utf-8-sig")
        except UnicodeDecodeError:
            try:
                data[:65536].decode("latin-1")
            except UnicodeDecodeError:
                raise AppError(400, "invalid_file", "CSV must be text")
    return ext


def parse_date(value) -> date | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, pd.Timestamp):
        return value.date()
    s = str(value).strip()
    if not s:
        return None
    s = re.sub(r"\s+", " ", s)
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def parse_amount(value) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, float):
        if pd.isna(value):
            return None
        value = repr(value)
    s = str(value).strip()
    if not s or s.lower() in ("nan", "-", "none"):
        return None
    neg = s.startswith("(") and s.endswith(")") or s.startswith("-") or s.lower().endswith("dr")
    s = re.sub(r"(?i)(inr|rs\.?|₹|\$|€|£|cr|dr)", "", s)
    s = re.sub(r"[,\s()+-]", "", s)
    if not s:
        return None
    try:
        d = Decimal(s).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None
    return -d if neg else d


def _find(cols: list[str], options: list[str]) -> str | None:
    for o in options:
        for c in cols:
            if c == o:
                return c
    for o in options:
        for c in cols:
            if o in c:
                return c
    return None


def rows_from_dataframe(df: pd.DataFrame) -> tuple[list[ExtractedRow], list[str]]:
    warnings: list[str] = []
    df = df.dropna(how="all")
    # Locate the header row if the sheet has preamble lines (common in bank exports).
    def norm(cols):
        return [str(c).strip().lower() for c in cols]

    cols = norm(df.columns)
    if not _find(cols, DATE_COLS):
        for i in range(min(len(df), 25)):
            candidate = norm(df.iloc[i].tolist())
            if _find(candidate, DATE_COLS) and (_find(candidate, DESC_COLS) or _find(candidate, AMOUNT_COLS + DEBIT_COLS)):
                df = df.iloc[i + 1 :]
                df.columns = candidate
                cols = candidate
                break
    df.columns = cols
    c_date, c_desc = _find(cols, DATE_COLS), _find(cols, DESC_COLS)
    c_amt, c_deb, c_cred, c_type = _find(cols, AMOUNT_COLS), _find(cols, DEBIT_COLS), _find(cols, CREDIT_COLS), _find(cols, TYPE_COLS)
    if not c_date or not (c_amt or c_deb or c_cred):
        raise AppError(422, "unrecognized_format", "Could not find date and amount columns in this statement.")
    rows: list[ExtractedRow] = []
    skipped = 0
    for _, r in df.iterrows():
        d = parse_date(r.get(c_date))
        desc = str(r.get(c_desc, "") if c_desc else "").strip()
        if desc.lower() in ("nan", "none"):
            desc = ""
        amount, tx_type = None, None
        if c_deb or c_cred:
            deb = parse_amount(r.get(c_deb)) if c_deb else None
            cred = parse_amount(r.get(c_cred)) if c_cred else None
            if deb and deb != 0:
                amount, tx_type = abs(deb), "expense"
            elif cred and cred != 0:
                amount, tx_type = abs(cred), "income"
        if amount is None and c_amt:
            a = parse_amount(r.get(c_amt))
            if a is not None and a != 0:
                t = str(r.get(c_type, "")).strip().lower() if c_type else ""
                if t in ("cr", "credit", "c", "income", "deposit"):
                    tx_type = "income"
                elif t in ("dr", "debit", "d", "expense", "withdrawal"):
                    tx_type = "expense"
                else:
                    tx_type = "income" if a > 0 else "expense"
                amount = abs(a)
        if d is None or amount is None or amount == 0:
            skipped += 1
            continue
        rows.append(ExtractedRow(d, (desc or "Statement entry")[:255], amount, tx_type))
        if len(rows) >= MAX_ROWS:
            warnings.append(f"Only the first {MAX_ROWS} rows were processed.")
            break
    if skipped:
        warnings.append(f"{skipped} row(s) without a valid date or amount were skipped (headers, balances or totals).")
    return rows, warnings


def _csv_frame(data: bytes) -> pd.DataFrame:
    """Read CSV with the csv module so preamble lines (bank name, account no.) don't break column detection."""
    try:
        raw = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raw = data.decode("latin-1")
    import csv

    try:
        dialect = csv.Sniffer().sniff(raw[:4096], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    records = [r for r in csv.reader(io.StringIO(raw), dialect) if any(c.strip() for c in r)]
    if not records:
        raise AppError(422, "no_transactions", "The CSV file has no rows.")
    header_idx = 0
    for i, rec in enumerate(records[:25]):
        cols = [c.strip().lower() for c in rec]
        if _find(cols, DATE_COLS) and (_find(cols, DESC_COLS) or _find(cols, AMOUNT_COLS + DEBIT_COLS)):
            header_idx = i
            break
    header = records[header_idx]
    width = len(header)
    body = [(r + [""] * width)[:width] for r in records[header_idx + 1 :]]
    return pd.DataFrame(body, columns=header)


def _pdf_rows(path: str) -> tuple[list[ExtractedRow], list[str]]:
    import fitz  # PyMuPDF
    import pdfplumber

    with fitz.open(path) as doc:
        if doc.is_encrypted:
            raise AppError(422, "pdf_encrypted", "This PDF is password protected. Export an unprotected statement and retry.")
        text = "".join(page.get_text() for page in doc)
    if len(text.strip()) < 20:
        raise AppError(
            422,
            "pdf_scanned",
            "This PDF has no extractable text (it looks scanned). OCR is not supported; please upload a CSV/XLSX export or a text-based PDF.",
        )
    # 1) table extraction with pdfplumber
    frames = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages[:50]:
            for table in page.extract_tables() or []:
                if table and len(table) > 1:
                    frames.append(pd.DataFrame(table[1:], columns=[str(c or "") for c in table[0]]))
    for frame in frames:
        try:
            rows, warnings = rows_from_dataframe(frame)
            if rows:
                if len(frames) > 1:
                    for extra in frames[1:]:
                        try:
                            extra.columns = frame.columns if len(extra.columns) == len(frame.columns) else extra.columns
                            more, _ = rows_from_dataframe(extra)
                            rows.extend(more)
                        except AppError:
                            pass
                return rows, warnings
        except AppError:
            continue
    # 2) line-based fallback: "<date> <description> <amount> [Cr|Dr]"
    pat = re.compile(
        r"^(?P<date>\d{1,2}[/\-. ](?:\d{1,2}|[A-Za-z]{3})[/\-. ]\d{2,4}|\d{4}-\d{2}-\d{2})\s+(?P<desc>.+?)\s+"
        r"(?P<amt>-?[\d,]+\.\d{2})\s*(?P<crdr>Cr|Dr|CR|DR)?(?:\s+[\d,]+\.\d{2})?\s*$"
    )
    rows: list[ExtractedRow] = []
    for line in text.splitlines():
        m = pat.match(line.strip())
        if not m:
            continue
        d, amt = parse_date(m.group("date")), parse_amount(m.group("amt"))
        if not d or not amt:
            continue
        crdr = (m.group("crdr") or "").lower()
        tx_type = "income" if crdr == "cr" else "expense" if crdr == "dr" else ("expense" if amt < 0 else "expense")
        rows.append(ExtractedRow(d, m.group("desc").strip()[:255], abs(amt), tx_type))
    warnings = []
    if rows:
        warnings.append("Parsed from PDF text lines; please review income/expense direction carefully.")
    return rows, warnings


def extract(ext: str, data: bytes) -> tuple[list[ExtractedRow], list[str]]:
    """Write to a private temp file, parse, and always delete it."""
    fd, path = tempfile.mkstemp(suffix=f".{ext}")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        if ext == "csv":
            rows, warnings = rows_from_dataframe(_csv_frame(data))
        elif ext == "xlsx":
            df = pd.read_excel(path, dtype=object, engine="openpyxl")
            rows, warnings = rows_from_dataframe(df)
        else:
            rows, warnings = _pdf_rows(path)
    except AppError:
        raise
    except Exception as exc:
        logger.warning("statement parse failed: %s", type(exc).__name__)
        raise AppError(422, "parse_failed", "The statement could not be read. Check the file format and try again.")
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
    if not rows:
        raise AppError(422, "no_transactions", "No transactions were found in this file.")
    return rows, warnings
