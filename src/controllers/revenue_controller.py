import calendar
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional, Tuple

from controllers.base_controller import BaseController
from controllers.transaction_controller import start_of_day
from errors import InvalidParameter
from repositories import (
    AccountRepository,
    InvestmentOrderRepository,
    ProductRepository,
    ReferenceRateRepository,
    TransactionRepository,
)
from utils.dates import parse_date


# Maior período aceito no relatório, em dias, contando as duas pontas (RN-REC-09).
MAX_PERIOD_DAYS = 366

ESTIMATES = ("fund_administration_fee", "own_issue_spread", "float")


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

        # Estimada (RN-REC-01): só calcula, não grava nada. Só os dias que já aconteceram (até hoje).
        last_day = min(to_date, today)
        days = [from_date + timedelta(days=offset) for offset in range((last_day - from_date).days + 1)]
        estimated = self.estimate(days) if days else {name: {"amount": 0, "daily": []} for name in ESTIMATES}

        return {
            "from": from_date.isoformat(),
            "to": to_date.isoformat(),
            "days": len(days),
            "realized": {"fee_amount": fee_amount},
            "estimated": estimated,
            "total_amount": fee_amount + sum(estimate["amount"] for estimate in estimated.values()),
        }

    def estimate(self, days: List[date]) -> dict:
        """RN-REC-05 a 07, dia a dia: a base no fim de cada dia × a taxa vigente naquele dia / 365.

        As bases saem do histórico (lançamentos e ordens acumulados até o dia), não da foto de agora:
        a receita de um dia passado não muda com o que acontece depois.
        """
        end = start_of_day(days[-1] + timedelta(days=1))
        products = ProductRepository.list(self.context, None, None)
        fund = next(product for product in products if product.administration_fee_bps)
        own_issues = [product for product in products if product.price_source_code is None]

        changes = InvestmentOrderRepository.daily_position_changes(self.context, end)
        quantities = {
            product.id: running_totals(days, [(day, quantity) for pid, day, quantity, _ in changes if pid == product.id])
            for product in products
        }
        costs = {
            product.id: running_totals(days, [(day, cost) for pid, day, _, cost in changes if pid == product.id])
            for product in products
        }
        balances = running_totals(days, TransactionRepository.daily_customer_balance_changes(self.context, end))
        fund_prices = [
            (price.price_date, price.unit_price)
            for price in ProductRepository.list_prices(self.context, fund.id, None, days[-1])
        ]
        cdi = [(rate.rate_date, rate.annual_rate_bps) for rate in ReferenceRateRepository.list_until(self.context, "CDI", days[-1])]
        selic = [
            (rate.rate_date, rate.annual_rate_bps) for rate in ReferenceRateRepository.list_until(self.context, "SELIC", days[-1])
        ]

        fund_daily, spread_daily, float_daily = [], [], []
        for index, day in enumerate(days):
            # Fundo: patrimônio ao preço do dia, em centavos para baixo, como a posição (RN-POS-01).
            unit_price = last_on(fund_prices, day)
            fund_base = int(quantities[fund.id][index] * unit_price * 100) if unit_price is not None else 0
            fund_daily.append(daily_entry(day, fund_base, fund.administration_fee_bps))

            # Spread: cada título paga um percentual do CDI, então a conta é por produto.
            cdi_bps = last_on(cdi, day)
            spread_base = sum(costs[product.id][index] for product in own_issues)
            spread = sum(
                Decimal(costs[product.id][index]) * (cdi_bps or 0) * (10000 - product.cdi_percentage_bps)
                for product in own_issues
            )
            spread_daily.append(
                {
                    "date": day.isoformat(),
                    "base_amount": spread_base,
                    "cdi_annual_rate_bps": cdi_bps,
                    "amount": int(spread / (10000 * 10000 * 365)),
                }
            )

            # Float: saldo parado nas contas de cliente no fim do dia × Selic.
            float_daily.append(daily_entry(day, balances[index], last_on(selic, day)))

        return {
            name: {"amount": sum(entry["amount"] for entry in daily), "daily": daily}
            for name, daily in zip(ESTIMATES, (fund_daily, spread_daily, float_daily))
        }


def daily_entry(day: date, base_amount: int, annual_rate_bps: Optional[int]) -> dict:
    """Um dia da estimativa: base × taxa anual / 365, em centavos para baixo. Sem taxa publicada, 0."""
    amount = int(Decimal(base_amount) * annual_rate_bps / (10000 * 365)) if annual_rate_bps is not None else 0
    return {"date": day.isoformat(), "base_amount": base_amount, "annual_rate_bps": annual_rate_bps, "amount": amount}


def running_totals(days: List[date], changes: List[Tuple[date, int]]) -> list:
    """O total acumulado no fim de cada dia, somando as variações (em ordem de dia) até ele."""
    totals, total, index = [], 0, 0
    for day in days:
        while index < len(changes) and changes[index][0] <= day:
            total += changes[index][1]
            index += 1
        totals.append(total)
    return totals


def last_on(published: list, day: date):
    """O último valor publicado até o dia (RN-PRO-04 e RN-REC-08); None se nada foi publicado ainda."""
    value = None
    for published_day, published_value in published:
        if published_day > day:
            break
        value = published_value
    return value
