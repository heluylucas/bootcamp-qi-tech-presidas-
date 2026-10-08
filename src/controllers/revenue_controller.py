import calendar
from datetime import datetime, timedelta, timezone

from controllers.base_controller import BaseController
from controllers.transaction_controller import start_of_day
from errors import InvalidParameter
from repositories import AccountRepository, TransactionRepository
from utils.dates import parse_date


# Maior período aceito no relatório, em dias, contando as duas pontas (RN-REC-09).
MAX_PERIOD_DAYS = 366


class RevenueController(BaseController):
    def __init__(self) -> None:
        super().__init__(__name__)

    def get(self, query_params: dict) -> dict:
        """Receita do banco no período (RN-REC-09). Sem datas, o mês corrente."""
        today = datetime.now(timezone.utc).date()
        month_start = today.replace(day=1)
        month_end = today.replace(day=calendar.monthrange(today.year, today.month)[1])

        from_date = parse_date(query_params.get("from"), "from") or month_start
        to_date = parse_date(query_params.get("to"), "to") or month_end

        if from_date > to_date:
            raise InvalidParameter("from must not be after to")

        if (to_date - from_date).days + 1 > MAX_PERIOD_DAYS:
            raise InvalidParameter(f"the period must not be longer than {MAX_PERIOD_DAYS} days")

        # Realizada (RN-REC-02): as tarifas que entraram na conta do banco, pela hora real do lançamento.
        bank = AccountRepository.get_bank(self.context)
        fee_amount = TransactionRepository.sum_credits(
            self.context, bank.id, "FEE", start_of_day(from_date), start_of_day(to_date + timedelta(days=1))
        )

        # TODO(módulo 8): parte estimada (taxa do fundo, spread dos títulos próprios, float).
        return {
            "from": from_date.isoformat(),
            "to": to_date.isoformat(),
            "realized": {"fee_amount": fee_amount},
        }
