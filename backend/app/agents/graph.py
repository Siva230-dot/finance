"""LangGraph supervisor + specialist agents for JOCASTA.

    START -> supervisor --(route)--> transaction_agent | categorization_agent | analysis_agent
                                     | budget_agent | savings_agent | jocasta
    <agent> --(tool calls & under iteration limit)--> tools --> <same agent>
    <agent> --(final answer or limit)--> finalize -> END
"""
import json
import logging
import operator
import re
from datetime import date
from typing import Annotated, Any, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph

from app.agents.tools import TOOLSETS, ToolContext, build_tools
from app.core.config import settings
from app.core.errors import AppError

logger = logging.getLogger("financemate.agents")

INTENTS = ["transaction", "categorization", "analysis", "budget", "savings", "general"]
AGENT_NODE = {
    "transaction": "transaction_agent",
    "categorization": "categorization_agent",
    "analysis": "analysis_agent",
    "budget": "budget_agent",
    "savings": "savings_agent",
    "general": "jocasta",
}


class AgentState(TypedDict, total=False):
    user_request: str
    user_context: dict  # id/name/currency from the authenticated session (never from the LLM)
    history: list[BaseMessage]
    messages: Annotated[list[BaseMessage], operator.add]
    intent: str
    intent_source: str
    iterations: int
    tool_events: Annotated[list[dict], operator.add]
    requires_confirmation: bool
    final_response: str
    error: str | None


# ---------------------------------------------------------------- intent classification
KEYWORDS: dict[str, list[str]] = {
    "savings": [r"\bsav(e|ing|ings) goal", r"\bgoal", r"\bsave (for|up)", r"\bcontribut", r"how much more .*save", r"\bput aside", r"\bsavings? (target|plan)"],
    "budget": [r"\bbudget", r"\boverspen", r"\bexceed", r"\blimit for", r"\brecommend.*(budget|spend)"],
    "categorization": [r"\bcategori[sz]", r"\brecategori", r"\bwrong category", r"\bmove .* to .* category", r"\bwhich category"],
    "analysis": [r"\banaly[sz]", r"\bcompare", r"\breport", r"\bsummary\b", r"\bbreakdown", r"\bwhere am i spending", r"\btrend",
                 r"\bwhy did my", r"\bhow much (did|have) i (spend|spent|earn)", r"\bspending (this|last)", r"\bsavings rate",
                 r"\bpotentially save", r"\bincome vs", r"\bspend(ing)? the most", r"\boverview"],
    "transaction": [r"\badd\b", r"\brecord\b", r"\blog\b", r"\bspent\b", r"\bpaid\b", r"\btransaction", r"\bexpense", r"\bincome\b",
                    r"\bdelete\b", r"\bremove\b", r"\bupdate\b", r"\bchange\b", r"\bedit\b", r"\bduplicate", r"\bshow .*(last|recent)",
                    r"\bsalary", r"\bbought", r"\bpurchase"],
}
PRIORITY = ["savings", "budget", "categorization", "analysis", "transaction"]


def keyword_intent(text: str) -> tuple[str | None, int]:
    t = text.lower()
    scores = {k: sum(1 for p in pats if re.search(p, t)) for k, pats in KEYWORDS.items()}
    best = max(scores.values())
    if best == 0:
        return None, 0
    winners = [k for k in PRIORITY if scores[k] == best]
    # Domain nouns outrank generic verbs ("add a budget" -> budget, "add ₹500" -> transaction).
    return winners[0], best


def classify_intent(text: str, llm) -> tuple[str, str]:
    intent, score = keyword_intent(text)
    if intent and (score >= 2 or llm is None):
        return intent, "keyword"
    if llm is not None:
        try:
            prompt = (
                "Classify the user's request for a personal-finance app into ONE label: "
                "transaction (add/list/edit/delete transactions), categorization (fix or explain categories), "
                "analysis (summaries, comparisons, reports, insights), budget (create/list/change budgets, overspending, budget advice), "
                "savings (savings goals and contributions), general (greetings, help, financial literacy).\n"
                'Reply with JSON only: {"intent": "<label>"}\n\nRequest: ' + text[:500]
            )
            raw = llm.invoke([HumanMessage(content=prompt)]).content
            m = re.search(r'"intent"\s*:\s*"(\w+)"', raw if isinstance(raw, str) else str(raw))
            if m and m.group(1) in INTENTS:
                # A generic "general" label never overrides a concrete domain keyword match.
                if m.group(1) == "general" and intent:
                    return intent, "keyword"
                return m.group(1), "llm"
        except Exception as exc:  # classification falls back to keywords
            logger.warning("intent classification failed: %s", type(exc).__name__)
    return intent or "general", "keyword" if intent else "default"


# ---------------------------------------------------------------- prompts
BASE_PROMPT = """You are JOCASTA, the personal finance assistant inside AI FinanceMate.
Personality: professional, friendly, calm, clear, concise and financially responsible.
Today is {today}. The user is {name}. Their currency is {currency}; format money like "{symbol}1,250".

Rules you must follow:
- Every number you state must come from a tool result in THIS turn. Conversation history is not a data source; call a tool to fetch current records.
- Never invent transactions, balances, ids or statistics. If data is missing, say so.
- Create/update/delete tools only PREPARE an action and return status "confirmation_required". When that happens, briefly describe what was prepared and ask the user to confirm (they can press Confirm on the card or reply "yes"). Never claim the change is done.
- To update or delete a specific record, first find it with a list tool. If several records match, or the instruction is ambiguous, list the candidates and ask which one. Never delete in bulk.
- If required details are missing (e.g. amount), ask for them instead of guessing. Reasonable defaults: date = today, type = expense unless clearly income.
- Do not give personalised investment advice, stock or crypto tips, or execute payments; explain you can help with budgeting and tracking instead.
- Keep answers short: 1–4 sentences or a compact list. Cards with details are shown automatically next to your reply, so don't repeat long tables.
{specialist}"""

SPECIALIST = {
    "transaction": "You are acting as the Transaction Agent: you manage transactions (create, list, update, delete, totals).",
    "categorization": "You are acting as the Expense Categorization Agent: explain and correct transaction categories. Category changes go through update_transaction and need confirmation. Mention that automatic categories carry a confidence score and can be wrong.",
    "analysis": "You are acting as the Financial Analysis Agent: use analysis tools, then explain the drivers behind the numbers (largest categories, changes vs last month, budget pressure). Offer one practical suggestion.",
    "budget": "You are acting as the Budget Planning Agent. Recommendations come only from calculate_budget_recommendation; explain the proposed amount, the historical basis, the reason, expected effect and confidence/limitations. Recommendations are saved only when the user approves them.",
    "savings": "You are acting as the Savings Goal Agent: manage goals and contributions; explain remaining amount and required monthly saving using tool figures.",
    "general": "You are JOCASTA's conversational core. Help with general questions about using the app and responsible money habits; use tools when the user asks about their own data.",
}
SYMBOLS = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥"}


def _system(intent: str, user_ctx: dict) -> SystemMessage:
    return SystemMessage(
        content=BASE_PROMPT.format(
            today=date.today().isoformat(), name=user_ctx["name"], currency=user_ctx["currency"],
            symbol=SYMBOLS.get(user_ctx["currency"], user_ctx["currency"] + " "), specialist=SPECIALIST[intent],
        )
    )


def _json(value: Any) -> str:
    return json.dumps(value, default=str)[:6000]


# ---------------------------------------------------------------- graph
def build_graph(ctx: ToolContext, llm):
    tools = build_tools(ctx)

    def supervisor(state: AgentState) -> dict:
        intent, source = classify_intent(state["user_request"], llm)
        return {"intent": intent, "intent_source": source, "iterations": 0,
                "messages": [_system(intent, state["user_context"]), *state.get("history", []), HumanMessage(content=state["user_request"])]}

    def make_agent(intent: str):
        allowed = [tools[n] for n in TOOLSETS[intent]]
        bound = llm.bind_tools(allowed) if allowed else llm

        def agent(state: AgentState) -> dict:
            response = bound.invoke(state["messages"])
            return {"messages": [response], "iterations": state.get("iterations", 0) + 1}

        agent.__name__ = AGENT_NODE[intent]
        return agent

    def run_tools(state: AgentState) -> dict:
        last = state["messages"][-1]
        allowed = set(TOOLSETS[state["intent"]])
        out_msgs, events = [], []
        confirmation = False
        for call in getattr(last, "tool_calls", []) or []:
            name, args = call["name"], call.get("args") or {}
            # Strip any identity the model might try to inject; identity comes only from ToolContext.
            for forbidden in ("user_id", "userId", "owner_id"):
                args.pop(forbidden, None)
            if name not in allowed:
                result = {"error": f"Tool '{name}' is not available to this agent."}
                status = "rejected"
            else:
                try:
                    result = tools[name].invoke(args)
                    status = "confirmation_required" if isinstance(result, dict) and result.get("status") == "confirmation_required" else "success"
                    confirmation = confirmation or status == "confirmation_required"
                except AppError as exc:
                    ctx.db.rollback()
                    result, status = {"error": exc.message}, "error"
                except Exception as exc:  # validation errors from bad arguments, etc.
                    ctx.db.rollback()
                    msg = str(exc).split("\n")[0][:300]
                    result, status = {"error": f"Invalid tool call: {msg}"}, "error"
            events.append({"tool": name, "status": status, "args": {k: v for k, v in args.items() if k not in ("notes",)}})
            out_msgs.append(ToolMessage(content=_json(result), tool_call_id=call["id"], name=name))
        ctx.events.extend(events)
        upd: dict = {"messages": out_msgs, "tool_events": events}
        if confirmation:
            upd["requires_confirmation"] = True
        return upd

    def after_agent(state: AgentState) -> str:
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and last.tool_calls and state.get("iterations", 0) <= settings.AGENT_MAX_ITERATIONS:
            return "tools"
        return "finalize"

    def finalize(state: AgentState) -> dict:
        last = state["messages"][-1]
        text = ""
        if isinstance(last, AIMessage) and not last.tool_calls:
            text = last.content if isinstance(last.content, str) else str(last.content)
        if not text.strip():
            if state.get("requires_confirmation"):
                text = "I've prepared this for you. Please review the details and confirm to proceed."
            elif any(e["status"] == "success" for e in state.get("tool_events", [])):
                text = "Here's what I found in your records."
            else:
                text = "I couldn't complete that request. Could you rephrase it or add a little more detail?"
        # Guard against the model claiming success for an action that only awaits confirmation.
        if state.get("requires_confirmation") and re.search(r"\b(done|has been (added|deleted|updated|created)|successfully)\b", text, re.I):
            text = "I've prepared this action. Please review the card and confirm to proceed — nothing has been changed yet."
        return {"final_response": text.strip()}

    g = StateGraph(AgentState)
    g.add_node("supervisor", supervisor)
    for intent, node in AGENT_NODE.items():
        g.add_node(node, make_agent(intent))
        g.add_conditional_edges(node, after_agent, {"tools": "tools", "finalize": "finalize"})
    g.add_node("tools", run_tools)
    g.add_node("finalize", finalize)
    g.add_edge(START, "supervisor")
    g.add_conditional_edges("supervisor", lambda s: AGENT_NODE[s["intent"]], {n: n for n in AGENT_NODE.values()})
    g.add_conditional_edges("tools", lambda s: AGENT_NODE[s["intent"]], {n: n for n in AGENT_NODE.values()})
    g.add_edge("finalize", END)
    return g.compile()
