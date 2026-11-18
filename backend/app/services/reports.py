"""Financial reports (JSON payload, PDF via ReportLab, CSV) built only from stored records."""
import csv
import io
import uuid
from datetime import date
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.orm import Session

from app.models import FinancialReport
from app.services import analytics
from app.services.budgets import budget_status
from app.services.money import add_months, month_end, month_start
from app.services.savings import goals_with_progress

FOREST = colors.HexColor("#25382D")
GOLD = colors.HexColor("#A58B58")
PARCHMENT = colors.HexColor("#F4F0E6")


def build_report(db: Session, user_id: uuid.UUID, report_type: str, period: date, save: bool = True) -> dict:
    if report_type == "annual":
        start, end = date(period.year, 1, 1), date(period.year, 12, 31)
        months = [analytics.monthly_summary(db, user_id, date(period.year, m, 1)) for m in range(1, 13)]
        payload = {
            "type": "annual",
            "title": f"Annual Summary {period.year}",
            "summary": analytics.period_summary(db, user_id, start, end),
            "months": [{"month": date(period.year, i + 1, 1).isoformat(), **{k: m[k] for k in ("income", "expenses", "savings", "savings_rate")}}
                       for i, m in enumerate(months)],
            "category_breakdown": analytics.category_breakdown(db, user_id, start, end),
            "income_breakdown": analytics.category_breakdown(db, user_id, start, end, "income"),
            "goals": goals_with_progress(db, user_id),
        }
    else:
        start, end = month_start(period), month_end(period)
        payload = {
            "type": "monthly",
            "title": f"Monthly Report {start:%B %Y}",
            "summary": analytics.monthly_summary(db, user_id, start),
            "category_breakdown": analytics.category_breakdown(db, user_id, start, end),
            "income_breakdown": analytics.category_breakdown(db, user_id, start, end, "income"),
            "month_over_month": analytics.month_over_month(db, user_id, start),
            "budgets": budget_status(db, user_id, start),
            "goals": goals_with_progress(db, user_id),
        }
    payload["period_start"], payload["period_end"] = start.isoformat(), end.isoformat()
    if save:
        rec = FinancialReport(user_id=user_id, report_type=report_type, period_start=start, period_end=end, payload=payload)
        db.add(rec)
        db.commit()
        payload["report_id"] = str(rec.id)
    return payload


def _fmt(v, currency: str) -> str:
    sym = {"INR": "Rs.", "USD": "$", "EUR": "EUR ", "GBP": "GBP "}.get(currency, currency + " ")
    d = Decimal(str(v))
    return f"{'-' if d < 0 else ''}{sym}{abs(d):,.2f}"


def render_pdf(payload: dict, owner_name: str, currency: str) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=18 * mm, bottomMargin=18 * mm,
                            title=payload["title"], author="AI FinanceMate")
    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Title"], fontName="Times-Bold", textColor=FOREST, fontSize=24, alignment=0)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], fontName="Times-Bold", textColor=FOREST, spaceBefore=12)
    body = ParagraphStyle("b", parent=ss["BodyText"], fontName="Helvetica", fontSize=9.5, textColor=colors.HexColor("#272820"))
    small = ParagraphStyle("s", parent=body, textColor=colors.HexColor("#777568"), fontSize=8)

    def table(rows, widths=None):
        t = Table(rows, colWidths=widths, hAlign="LEFT")
        t.setStyle(TableStyle([
            ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9), ("FONT", (0, 1), (-1, -1), "Helvetica", 9),
            ("TEXTCOLOR", (0, 0), (-1, 0), FOREST), ("LINEBELOW", (0, 0), (-1, 0), 0.8, GOLD),
            ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.HexColor("#D9D0BF")), ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 4),
        ]))
        return t

    s = payload["summary"]
    story = [
        Paragraph("AI FINANCEMATE", ParagraphStyle("k", parent=small, textColor=GOLD, fontName="Helvetica-Bold")),
        Paragraph(payload["title"], h1),
        Paragraph(f"Prepared for {owner_name} &middot; {payload['period_start']} to {payload['period_end']}", small),
        Spacer(1, 10),
        table([["Income", "Expenses", "Net savings", "Savings rate"],
               [_fmt(s["income"], currency), _fmt(s["expenses"], currency), _fmt(s["savings"], currency), f"{s['savings_rate']}%"]],
              [40 * mm] * 4),
    ]
    if payload.get("months"):
        story += [Paragraph("Month by month", h2),
                  table([["Month", "Income", "Expenses", "Savings"]] +
                        [[m["month"][:7], _fmt(m["income"], currency), _fmt(m["expenses"], currency), _fmt(m["savings"], currency)] for m in payload["months"]])]
    cats = payload.get("category_breakdown") or []
    story += [Paragraph("Expense breakdown", h2)]
    story += [table([["Category", "Amount", "Share", "Count"]] + [[c["category"], _fmt(c["amount"], currency), f"{c['share']}%", str(c["count"])] for c in cats])] if cats else [Paragraph("No expenses recorded in this period.", body)]
    if payload.get("budgets"):
        story += [Paragraph("Budget performance", h2),
                  table([["Category", "Budget", "Spent", "Used", "Status"]] +
                        [[b["category"]["name"], _fmt(b["amount"], currency), _fmt(b["spent"], currency), f"{b['utilization']}%", b["status"].replace("_", " ")] for b in payload["budgets"]])]
    if payload.get("goals"):
        story += [Paragraph("Savings progress", h2),
                  table([["Goal", "Target", "Saved", "Progress"]] +
                        [[g["name"], _fmt(g["target_amount"], currency), _fmt(g["current_amount"], currency), f"{g['progress_percent']}%"] for g in payload["goals"]])]
    story += [Spacer(1, 16), Paragraph("Figures are calculated from the transactions recorded in AI FinanceMate. This report is informational and is not financial advice.", small)]

    def bg(canvas, _doc):
        canvas.saveState()
        canvas.setFillColor(PARCHMENT)
        canvas.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
        canvas.setStrokeColor(GOLD)
        canvas.setLineWidth(0.6)
        canvas.rect(10 * mm, 10 * mm, A4[0] - 20 * mm, A4[1] - 20 * mm)
        canvas.restoreState()

    doc.build(story, onFirstPage=bg, onLaterPages=bg)
    return buf.getvalue()


def render_csv(payload: dict) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    s = payload["summary"]
    w.writerow([payload["title"]])
    w.writerow(["period_start", payload["period_start"], "period_end", payload["period_end"]])
    w.writerow([])
    w.writerow(["income", "expenses", "savings", "savings_rate"])
    w.writerow([s["income"], s["expenses"], s["savings"], s["savings_rate"]])
    w.writerow([])
    if payload.get("months"):
        w.writerow(["month", "income", "expenses", "savings"])
        for m in payload["months"]:
            w.writerow([m["month"], m["income"], m["expenses"], m["savings"]])
        w.writerow([])
    w.writerow(["category", "amount", "share_percent", "count"])
    for c in payload.get("category_breakdown") or []:
        w.writerow([c["category"], c["amount"], c["share"], c["count"]])
    if payload.get("budgets"):
        w.writerow([])
        w.writerow(["budget_category", "budget", "spent", "utilization_percent", "status"])
        for b in payload["budgets"]:
            w.writerow([b["category"]["name"], b["amount"], b["spent"], b["utilization"], b["status"]])
    return buf.getvalue()


def previous_month(today: date | None = None) -> date:
    return add_months(month_start(today or date.today()), -1)
