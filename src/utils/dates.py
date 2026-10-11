import calendar
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from errors import InvalidSchema


def add_months(day: date, months: int) -> date:
    month_index = day.month - 1 + months
    year = day.year + month_index // 12
    month = month_index % 12 + 1
    last_day_of_month = calendar.monthrange(year, month)[1]
    return day.replace(year=year, month=month, day=min(day.day, last_day_of_month))


def parse_date(text: Optional[str], field: str) -> Optional[date]:
    if text is None:
        return None

    try:
        return date.fromisoformat(text)
    except ValueError:
        raise InvalidSchema(f"{field} is not a valid date")


def next_business_day(day: date) -> date:
    day += timedelta(days=1)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day


def to_utc_text(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
