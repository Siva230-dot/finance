"""JOCASTA orchestration: conversation persistence, confirmation replies and graph execution."""
import logging
import re
import uuid

from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents import actions
from app.agents.graph import build_graph
from app.agents.llm import get_llm
from app.agents.tools import ToolContext
from app.core.config import settings
from app.core.errors import AppError
from app.models import AgentConversation, AgentMessage, User

logger = logging.getLogger("financemate.assistant")

YES = re.compile(r"^\s*(yes|y|yeah|yep|sure|ok(ay)?|confirm(ed)?|do it|go ahead|proceed|please do|haan|correct)\b[\s.!]*$", re.I)
NO = re.compile(r"^\s*(no|n|nope|cancel|stop|don'?t|do not|never ?mind|abort|nah)\b.*$", re.I)
HISTORY_LIMIT = 12


def get_conversation(db: Session, user_id: uuid.UUID, conversation_id: uuid.UUID) -> AgentConversation:
    conv = db.scalar(select(AgentConversation).where(AgentConversation.id == conversation_id, AgentConversation.user_id == user_id))
    if not conv:
        raise AppError(404, "not_found", "Conversation not found")
    return conv


def _save(db: Session, conv: AgentConversation, role: str, content: str, meta: dict | None = None) -> AgentMessage:
    m = AgentMessage(conversation_id=conv.id, user_id=conv.user_id, role=role, content=content, meta=meta)
    db.add(m)
    db.flush()
    from sqlalchemy import func

    conv.updated_at = func.now()
    db.commit()
    db.refresh(m)
    return m


def _history(db: Session, conv: AgentConversation, exclude_id: uuid.UUID) -> list:
    rows = db.scalars(
        select(AgentMessage).where(AgentMessage.conversation_id == conv.id, AgentMessage.id != exclude_id)
        .order_by(AgentMessage.created_at.desc()).limit(HISTORY_LIMIT)
    ).all()
    out = []
    for m in reversed(rows):
        out.append(HumanMessage(content=m.content) if m.role == "user" else AIMessage(content=m.content))
    return out


def _llm_error_message(exc: Exception) -> tuple[str, str]:
    name = type(exc).__name__
    if "RateLimit" in name:
        return "rate_limited", "I'm receiving too many requests right now (Groq rate limit). Please wait a moment and try again."
    if "Timeout" in name:
        return "timeout", "The language model took too long to respond. Please try again."
    if "Authentication" in name or "PermissionDenied" in name:
        return "llm_auth", "JOCASTA's language model credentials are not valid. Please contact the administrator."
    if "Connection" in name:
        return "llm_unavailable", "I couldn't reach the language model service. Please try again shortly."
    return "llm_error", "Something went wrong while I was thinking. Please try again."


def handle_message(db: Session, user: User, text: str, conversation_id: uuid.UUID | None) -> tuple[AgentConversation, AgentMessage]:
    if conversation_id:
        conv = get_conversation(db, user.id, conversation_id)
    else:
        conv = AgentConversation(user_id=user.id, title=text.strip()[:60] or "New conversation")
        db.add(conv)
        db.commit()
    user_msg = _save(db, conv, "user", text.strip())

    # 1) Replies to a pending confirmation are handled deterministically — no LLM involved.
    pending = actions.latest_pending(db, user.id, conv.id)
    if pending and (YES.match(text) or NO.match(text)):
        if YES.match(text):
            try:
                pc, result = actions.confirm(db, user, pending.id)
                reply = actions.describe_result(result, user.currency)
                meta = {"cards": [result], "resolved_confirmation": {"id": str(pc.id), "status": "confirmed"}, "intent": "confirmation"}
            except AppError as exc:
                reply, meta = f"I couldn't complete that: {exc.message}", {"cards": [], "error": exc.code, "intent": "confirmation"}
        else:
            actions.cancel(db, user.id, pending.id)
            reply = "No problem — I've cancelled that. Nothing was changed."
            meta = {"cards": [], "resolved_confirmation": {"id": str(pending.id), "status": "cancelled"}, "intent": "confirmation"}
        return conv, _save(db, conv, "assistant", reply, meta)

    # 2) Otherwise run the LangGraph multi-agent workflow.
    llm = get_llm()
    if llm is None:
        reply = ("JOCASTA's language model isn't configured on this server yet (GROQ_API_KEY is missing). "
                 "All other FinanceMate features keep working; ask the administrator to add the key.")
        return conv, _save(db, conv, "assistant", reply, {"cards": [], "error": "llm_not_configured"})

    ctx = ToolContext(db=db, user=user, conversation_id=conv.id)
    graph = build_graph(ctx, llm)
    state = {
        "user_request": text.strip(),
        "user_context": {"id": str(user.id), "name": user.full_name.split(" ")[0], "currency": user.currency},
        "history": _history(db, conv, user_msg.id),
        "messages": [],
        "tool_events": [],
    }
    try:
        result = graph.invoke(state, config={"recursion_limit": settings.AGENT_MAX_ITERATIONS * 2 + 6})
        reply = result.get("final_response") or "I couldn't complete that request."
        meta = {"cards": ctx.cards, "tool_events": ctx.events, "intent": result.get("intent"), "intent_source": result.get("intent_source"),
                "requires_confirmation": bool(result.get("requires_confirmation"))}
    except Exception as exc:
        db.rollback()
        code, reply = _llm_error_message(exc)
        if code == "llm_error":
            logger.exception("assistant graph failure")
        else:
            logger.warning("assistant llm failure: %s", type(exc).__name__)
        # Any confirmations prepared before the failure remain valid and visible.
        meta = {"cards": ctx.cards, "tool_events": ctx.events, "error": code}
    return conv, _save(db, conv, "assistant", reply, meta)
