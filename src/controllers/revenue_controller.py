import calendar
from datetime import date
from decimal import Decimal
from typing import List, Optional

from controllers.base_controller import BaseController
from errors import InvalidParameter
from models import RevenueAccrual
from repositories import (
    AccountRepository,
    BusinessDayRepository,
    PositionRepository,
    ProductRepository,
    ReferenceRateRepository,
    RevenueAccrualRepository,
    TransactionRepository,
)
from utils.dates import parse_date


# Maior período aceito no relatório, em dias, contando as duas pontas (RN-REC-09).
MAX_PERIOD_DAYS = 366


class RevenueController(BaseController):
    def __init__(self) -> None:
        super().__init__(__name__)

    def get(self, query_params: dict) -> dict:
        """Receita do banco no período, em datas de movimento (RN-REC-09). Sem datas, o mês corrente."""
        today = BusinessDayRepository.get_current(self.context).business_date
        month_start = today.replace(day=1)
        month_end = today.replace(day=calendar.monthrange(today.year, today.month)[1])

        from_date = parse_date(query_params.get("from"), "from") or month_start
        to_date = parse_date(query_params.get("to"), "to") or month_end

        if from_date > to_date:
            raise InvalidParameter("from must not be after to")

        if (to_date - from_date).days + 1 > MAX_PERIOD_DAYS:
            raise InvalidParameter(f"the period must not be longer than {MAX_PERIOD_DAYS} days")

        # Realizada (RN-REC-02): as tarifas que entraram na conta do banco nos dias de movimento do
        # período, inclusive no dia ainda aberto.
        bank = AccountRepository.get_bank(self.context)
        fee_amount = TransactionRepository.sum_credits(self.context, bank.id, "FEE", from_date, to_date)

        # Estimada (RN-REC-05 a 07): a provisão que cada fechamento gravou. Só dias fechados.
        accruals = RevenueAccrualRepository.list_between(self.context, from_date, to_date)
        estimated = self.estimated(accruals, to_date)

        return {
            "from": from_date.isoformat(),
            "to": to_date.isoformat(),
            "days": len(accruals),
            "realized": {"fee_amount": fee_amount},
            "estimated": estimated,
            "total_amount": fee_amount + sum(estimate["amount"] for estimate in estimated.values()),
        }

    def estimated(self, accruals: List[RevenueAccrual], to_date: date) -> dict:
        """As provisões do período, com a taxa de cada dia para a conta poder ser conferida."""
        fund = self.fund()
        cdi = [(rate.rate_date, rate.annual_rate_bps) for rate in ReferenceRateRepository.list_until(self.context, "CDI", to_date)]
        selic = [
            (rate.rate_date, rate.annual_rate_bps) for rate in ReferenceRateRepository.list_until(self.context, "SELIC", to_date)
        ]

        fund_daily, spread_daily, float_daily = [], [], []
        for accrual in accruals:
            day = {"date": accrual.business_date.isoformat(), "calendar_days": accrual.calendar_days}
            fund_daily.append(
                {
                    **day,
                    "base_amount": accrual.fund_equity_amount,
                    "annual_rate_bps": fund.administration_fee_bps,
                    "amount": accrual.fund_administration_fee_amount,
                }
            )
            spread_daily.append(
                {
                    **day,
                    "base_amount": accrual.own_issue_cost_amount,
                    "cdi_annual_rate_bps": last_on(cdi, accrual.business_date),
                    "amount": accrual.own_issue_spread_amount,
                }
            )
            float_daily.append(
                {
                    **day,
                    "base_amount": accrual.customer_balance_amount,
                    "annual_rate_bps": last_on(selic, accrual.business_date),
                    "amount": accrual.float_amount,
                }
            )

        return {
            "fund_administration_fee": with_total(fund_daily),
            "own_issue_spread": with_total(spread_daily),
            "float": with_total(float_daily),
        }

    def accrue(self, close_date: date, next_date: date) -> None:
        """Grava a provisão do dia que fecha (RN-REC-05 a 07). Roda dentro do fechamento, que faz o commit.

        As bases são a foto do fim do dia (o estado de agora, antes de o novo dia abrir), e o
        valor cobre os dias corridos até o próximo dia de movimento: a de sexta vale o fim de semana.
        """
        days = (next_date - close_date).days
        fund = self.fund()
        products = ProductRepository.list(self.context, None, None)
        held = {product_id: (quantity, cost) for product_id, quantity, cost in PositionRepository.sum_by_product(self.context)}
        cdi_bps = ReferenceRateRepository.get_on(self.context, "CDI", close_date).annual_rate_bps
        selic_bps = ReferenceRateRepository.get_on(self.context, "SELIC", close_date).annual_rate_bps

        # Float: o saldo parado nas contas de cliente, sem a conta do banco.
        customer_balance = AccountRepository.sum_customer_balances(self.context)

        # Fundo: o patrimônio dos clientes ao preço do dia, em centavos para baixo, como a posição (RN-POS-01).
        fund_quantity, _ = held.get(fund.id, (Decimal(0), 0))
        fund_price = ProductRepository.get_price_on(self.context, fund.id, close_date).unit_price
        fund_equity = int(fund_quantity * fund_price * 100)

        # Spread: cada título próprio paga um percentual do CDI, então a conta é por produto.
        own_issues = [product for product in products if product.price_source_code is None]
        own_issue_cost = sum(held.get(product.id, (0, 0))[1] for product in own_issues)
        spread = sum(
            Decimal(held.get(product.id, (0, 0))[1]) * cdi_bps * (10000 - product.cdi_percentage_bps)
            for product in own_issues
        )

        RevenueAccrualRepository.create(
            self.context,
            business_date=close_date,
            calendar_days=days,
            customer_balance_amount=customer_balance,
            fund_equity_amount=fund_equity,
            own_issue_cost_amount=own_issue_cost,
            float_amount=accrued(customer_balance, selic_bps, days),
            fund_administration_fee_amount=accrued(fund_equity, fund.administration_fee_bps, days),
            own_issue_spread_amount=int(spread * days / (10000 * 10000 * 365)),
        )

    def fund(self):
        """O fundo da casa: o único produto com taxa de administração (RN-REC-04)."""
        return next(product for product in ProductRepository.list(self.context, "FUND", None) if product.administration_fee_bps)


def accrued(base_amount: int, annual_rate_bps: int, days: int) -> int:
    """Base × taxa anual × dias corridos / 365, em centavos para baixo. Aproximação linear (RN-REC-05)."""
    return int(Decimal(base_amount) * annual_rate_bps * days / (10000 * 365))


def with_total(daily: list) -> dict:
    return {"amount": sum(day["amount"] for day in daily), "daily": daily}


def last_on(published: list, day: date) -> Optional[int]:
    """A última taxa publicada até o dia (RN-REC-08)."""
    value = None
    for published_day, published_value in published:
        if published_day > day:
            break
        value = published_value
    return value
