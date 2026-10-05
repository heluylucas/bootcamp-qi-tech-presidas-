import calendar
from datetime import date, timedelta
from typing import Optional

from errors import InvalidSchema


def add_months(day: date, months: int) -> date:
    """Soma meses a uma data. Se o dia não existe no mês de chegada, usa o último dia dele.

    29/02/2028 + 24 meses = 28/02/2030, porque 2030 não tem 29 de fevereiro.
    """
    month_index = day.month - 1 + months
    year = day.year + month_index // 12
    month = month_index % 12 + 1
    last_day_of_month = calendar.monthrange(year, month)[1]
    return date(year, month, min(day.day, last_day_of_month))


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
