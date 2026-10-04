import calendar
from datetime import date


def add_months(day: date, months: int) -> date:
    """Soma meses a uma data. Se o dia não existe no mês de chegada, usa o último dia dele.

    29/02/2028 + 24 meses = 28/02/2030, porque 2030 não tem 29 de fevereiro.
    """
    month_index = day.month - 1 + months
    year = day.year + month_index // 12
    month = month_index % 12 + 1
    last_day_of_month = calendar.monthrange(year, month)[1]
    return date(year, month, min(day.day, last_day_of_month))
