from datetime import date, timedelta
from typing import Optional

from errors import InvalidSchema


def parse_date(text: Optional[str], field: str) -> Optional[date]:
    """O schema só confere a cara AAAA-MM-DD; "2026-02-30" só cai aqui."""
    if text is None:
        return None

    try:
        return date.fromisoformat(text)
    except ValueError:
        raise InvalidSchema(f"{field} is not a valid date")


def next_business_day(day: date) -> date:
    """Sexta vira segunda; sábado e domingo nunca abrem (RN-FEC-03). Feriados ficam de fora."""
    day += timedelta(days=1)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day
