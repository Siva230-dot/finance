"""Groq LLM provider (server-side only). Tests replace `provider` with a scripted fake model."""
from collections.abc import Callable

from app.core.config import settings


def _groq():
    if not settings.llm_configured:
        return None
    from langchain_groq import ChatGroq

    return ChatGroq(
        model=settings.GROQ_MODEL,
        api_key=settings.GROQ_API_KEY,
        temperature=0.1,
        timeout=settings.GROQ_TIMEOUT_SECONDS,
        max_retries=settings.GROQ_MAX_RETRIES,  # SDK retries 429/5xx with exponential backoff
    )


provider: Callable[[], object | None] = _groq


def get_llm():
    return provider()
