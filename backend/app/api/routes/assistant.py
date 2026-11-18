import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.agents import actions, service
from app.agents.llm import get_llm
from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.rate_limit import limiter
from app.models import AgentConversation, AgentMessage, User
from app.schemas import ChatIn, ChatMessageOut, ChatOut, ConversationOut

router = APIRouter(prefix="/assistant", tags=["assistant"])


def _msg(m: AgentMessage) -> ChatMessageOut:
    return ChatMessageOut(id=m.id, role=m.role, content=m.content, meta=m.meta, created_at=m.created_at)


@router.get("/status")
def status(user: User = Depends(get_current_user)):
    return {"available": settings.llm_configured, "model": settings.GROQ_MODEL if settings.llm_configured else None, "name": "JOCASTA"}


@router.post("/chat", response_model=ChatOut)
@limiter.limit("20/minute")
def chat(request: Request, body: ChatIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conv, reply = service.handle_message(db, user, body.message, body.conversation_id)
    return ChatOut(conversation_id=conv.id, message=_msg(reply))


@router.get("/conversations", response_model=list[ConversationOut])
def conversations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(select(AgentConversation).where(AgentConversation.user_id == user.id).order_by(AgentConversation.updated_at.desc()).limit(50)).all()


@router.get("/conversations/{conversation_id}/messages", response_model=list[ChatMessageOut])
def messages(conversation_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conv = service.get_conversation(db, user.id, conversation_id)
    pending = {str(p.id) for p in actions.pending_in_conversation(db, user.id, conv.id)}
    out = []
    for m in conv.messages:
        msg = _msg(m)
        if msg.meta and msg.meta.get("cards"):
            for card in msg.meta["cards"]:
                if card.get("type") == "confirmation" and card.get("confirmation_id") not in pending:
                    card["status"] = "resolved"
        out.append(msg)
    return out


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conv = service.get_conversation(db, user.id, conversation_id)
    db.delete(conv)
    db.commit()


@router.post("/confirmations/{confirmation_id}/confirm", response_model=ChatOut)
def confirm(confirmation_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    pc = actions.get_pending(db, user.id, confirmation_id)
    conv = service.get_conversation(db, user.id, pc.conversation_id) if pc.conversation_id else None
    try:
        pc, result = actions.confirm(db, user, confirmation_id)
        text, meta = actions.describe_result(result, user.currency), {"cards": [result], "resolved_confirmation": {"id": str(pc.id), "status": "confirmed"}}
    except Exception as exc:
        from app.core.errors import AppError

        if not isinstance(exc, AppError) or conv is None or exc.status_code in (404, 409, 410):
            raise
        text, meta = f"I couldn't complete that: {exc.message}", {"cards": [], "error": exc.code}
    if conv is None:
        conv = AgentConversation(user_id=user.id, title="Confirmed action")
        db.add(conv)
        db.commit()
    reply = service._save(db, conv, "assistant", text, meta)
    return ChatOut(conversation_id=conv.id, message=_msg(reply))


@router.post("/confirmations/{confirmation_id}/cancel", response_model=ChatOut)
def cancel(confirmation_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    pc = actions.cancel(db, user.id, confirmation_id)
    conv = service.get_conversation(db, user.id, pc.conversation_id) if pc.conversation_id else None
    if conv is None:
        conv = AgentConversation(user_id=user.id, title="Cancelled action")
        db.add(conv)
        db.commit()
    reply = service._save(db, conv, "assistant", "Cancelled. Nothing was changed.",
                          {"cards": [], "resolved_confirmation": {"id": str(pc.id), "status": "cancelled"}})
    return ChatOut(conversation_id=conv.id, message=_msg(reply))


@router.get("/suggestions")
def suggestions(user: User = Depends(get_current_user)):
    return {"suggestions": [
        "Analyze my spending this month", "Show my last five expenses", "Which categories have exceeded their budgets?",
        "Compare this month with last month", "Recommend budgets for next month", "How much more do I need to save?",
        "Add ₹500 for groceries today", "Generate my monthly financial report",
    ]}
