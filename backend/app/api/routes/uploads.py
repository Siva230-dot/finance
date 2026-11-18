import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, File, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.llm import get_llm
from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.errors import AppError
from app.core.rate_limit import limiter
from app.models import UploadedFile, User
from app.schemas import ImportApproveIn, ImportResultOut, UploadPreviewOut
from app.services import statements, transactions as tx_svc
from app.services.audit import audit
from app.services.categories import categorize_many, category_by_slug, get_category

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post("/statements", response_model=UploadPreviewOut, status_code=201)
@limiter.limit("10/minute")
async def upload_statement(request: Request, file: UploadFile = File(...), use_ai: bool = True,
                           user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    data = await file.read(settings.max_upload_bytes + 1)
    ext = statements.validate_upload(file.filename or "", file.content_type, data, settings.max_upload_bytes)
    rows, warnings = statements.extract(ext, data)
    del data  # original document is never persisted

    llm = get_llm() if use_ai else None
    guesses = categorize_many([r.description for r in rows], [r.type for r in rows], llm)
    hashes = [tx_svc.dedupe_hash(r.transaction_date, r.amount, r.type, r.description) for r in rows]
    existing = tx_svc.existing_hashes(db, user.id, hashes)
    seen: set[str] = set()
    preview, dup_count = [], 0
    cat_cache: dict[str, object] = {}
    for i, (r, g, h) in enumerate(zip(rows, guesses, hashes)):
        reason = "Already recorded" if h in existing else ("Repeated in this file" if h in seen else None)
        seen.add(h)
        dup_count += 1 if reason else 0
        cat = cat_cache.get(g.slug) or category_by_slug(db, user.id, g.slug)
        cat_cache[g.slug] = cat
        preview.append({"index": i, "transaction_date": r.transaction_date.isoformat(), "description": r.description, "amount": str(r.amount),
                        "type": r.type, "category_slug": g.slug, "category_name": cat.name, "categorization_source": g.source,
                        "confidence": str(g.confidence), "is_duplicate": bool(reason), "duplicate_reason": reason})
    if llm is None and any(g.source == "default" for g in guesses):
        warnings.append("Some rows could not be categorized automatically and were set to 'Other'. Review them before importing.")
    up = UploadedFile(user_id=user.id, original_filename=(file.filename or "statement")[:255], file_type=ext, size_bytes=file.size or 0,
                      rows_extracted=len(preview), extracted_rows=preview, status="previewed")
    db.add(up)
    db.flush()
    audit(db, user.id, "upload.preview", "uploaded_file", up.id, details={"rows": len(preview), "type": ext})
    db.commit()
    return {"upload_id": up.id, "filename": up.original_filename, "file_type": ext, "rows": preview, "duplicates": dup_count, "warnings": warnings}


def _get_upload(db: Session, user_id: uuid.UUID, upload_id: uuid.UUID) -> UploadedFile:
    up = db.scalar(select(UploadedFile).where(UploadedFile.id == upload_id, UploadedFile.user_id == user_id))
    if not up:
        raise AppError(404, "not_found", "Upload not found")
    if up.status != "previewed":
        raise AppError(409, "conflict", f"This upload was already {up.status}")
    return up


@router.post("/statements/{upload_id}/approve", response_model=ImportResultOut)
def approve(upload_id: uuid.UUID, body: ImportApproveIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    up = _get_upload(db, user.id, upload_id)
    rows = {r["index"]: r for r in (up.extracted_rows or [])}
    imported = 0
    batch = uuid.uuid4()
    for idx in sorted(set(body.selected_indexes)):
        r = rows.get(idx)
        if not r:
            raise AppError(422, "validation_error", f"Row {idx} does not exist in this upload")
        override = body.category_overrides.get(idx)
        if override:
            cat, source, conf = get_category(db, user.id, override), "user", Decimal("1.000")
        else:
            cat, source, conf = category_by_slug(db, user.id, r["category_slug"]), r["categorization_source"], Decimal(r["confidence"])
        tx_svc.create_transaction(db, user.id, description=r["description"], amount=Decimal(r["amount"]), tx_type=r["type"],
                                  transaction_date=date.fromisoformat(r["transaction_date"]), category_id=cat.id, notes=f"Imported from {up.original_filename}",
                                  categorization_source=source, categorization_confidence=conf, import_batch_id=batch, commit=False)
        imported += 1
    up.status, up.rows_imported, up.extracted_rows = "imported", imported, None  # drop extracted data after import
    audit(db, user.id, "upload.import", "uploaded_file", up.id, details={"imported": imported})
    db.commit()
    return {"upload_id": up.id, "imported": imported, "skipped": up.rows_extracted - imported}


@router.post("/statements/{upload_id}/reject", status_code=204)
def reject(upload_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    up = _get_upload(db, user.id, upload_id)
    up.status, up.extracted_rows = "rejected", None
    audit(db, user.id, "upload.reject", "uploaded_file", up.id)
    db.commit()
