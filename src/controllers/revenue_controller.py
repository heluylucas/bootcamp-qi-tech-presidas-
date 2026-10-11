import calendar
from datetime import date
from decimal import Decimal
from typing import List, Optional, Tuple

from controllers.base_controller import BaseController
from errors import InvalidParameter
from models import Product, RevenueAccrual
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
from utils.money import amount_for


MAX_PERIOD_DAYS = 366


class RevenueController(BaseController):
    def __init__(self) -> None:
        super().__init__(__name__)

    def get(self, query_params: dict) -> dict:
        today = BusinessDayRepository.get_current(self.context).business_date
        month_start = today.replace(day=1)
        month_end = today.replace(day=calendar.monthrange(today.year, today.month)[1])

        from_date = parse_date(query_params.get("from"), "from") or month_start
        to_date = parse_date(query_params.get("to"), "to") or month_end

        if from_date > to_date:
            raise InvalidParameter("from must not be after to")

        if (to_date - from_date).days + 1 > MAX_PERIOD_DAYS:
            raise InvalidParameter(f"the period must not be longer than {MAX_PERIOD_DAYS} days")

        bank = AccountRepository.get_bank(self.context)
        fee_amount = TransactionRepository.sum_credits(self.context, bank.id, "FEE", from_date, to_date)

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
        fund = self.fund()
        cdi = self.rates_until("CDI", to_date)
        selic = self.rates_until("SELIC", to_date)

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
        days = (next_date - close_date).days
        fund = self.fund()
        products = ProductRepository.list(self.context, None, None)
        held = {product_id: (quantity, cost) for product_id, quantity, cost in PositionRepository.sum_by_product(self.context)}
        cdi_bps = ReferenceRateRepository.get_on(self.context, "CDI", close_date).annual_rate_bps
        selic_bps = ReferenceRateRepository.get_on(self.context, "SELIC", close_date).annual_rate_bps

        customer_balance = AccountRepository.sum_customer_balances(self.context)

        fund_quantity, _ = held.get(fund.id, (Decimal(0), 0))
        fund_price = ProductRepository.get_price_on(self.context, fund.id, close_date).unit_price
        fund_equity = amount_for(fund_quantity, fund_price)

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

    def rates_until(self, code: str, day: date) -> List[Tuple[date, int]]:
        return [(rate.rate_date, rate.annual_rate_bps) for rate in ReferenceRateRepository.list_until(self.context, code, day)]

    def fund(self) -> Product:
        return next(product for product in ProductRepository.list(self.context, "FUND", None) if product.administration_fee_bps)


def accrued(base_amount: int, annual_rate_bps: int, days: int) -> int:
    return int(Decimal(base_amount) * annual_rate_bps * days / (10000 * 365))


def with_total(daily: list) -> dict:
    return {"amount": sum(day["amount"] for day in daily), "daily": daily}


def last_on(published: list, day: date) -> Optional[int]:
    value = None
    for published_day, published_value in published:
        if published_day > day:
            break
        value = published_value
    return value
