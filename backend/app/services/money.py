"""Decimal helpers. Money never goes through binary floating point."""
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

TWO = Decimal("0.01")
ZERO = Decimal("0.00")


def to_money(value) -> Decimal:
    if isinstance(value, Decimal):
        d = value
    elif isinstance(value, float):
        d = Decimal(repr(value))
    else:
        try:
            d = Decimal(str(value).strip())
        except (InvalidOperation, ValueError):
            raise ValueError(f"Invalid monetary value: {value!r}")
    if not d.is_finite():
        raise ValueError("Invalid monetary value")
    return d.quantize(TWO, rounding=ROUND_HALF_UP)


def pct(part: Decimal, whole: Decimal) -> Decimal:
    if whole == 0:
        return ZERO
    return (part / whole * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def month_start(d: date) -> date:
    return d.replace(day=1)


def add_months(d: date, n: int) -> date:
    y, m = divmod(d.month - 1 + n, 12)
    year, month = d.year + y, m + 1
    import calendar

    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def month_end(d: date) -> date:
    import calendar

    return d.replace(day=calendar.monthrange(d.year, d.month)[1])
