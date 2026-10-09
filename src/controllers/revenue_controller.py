import calendar
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from controllers.base_controller import BaseController
from controllers.transaction_controller import start_of_day
from errors import InvalidParameter
from repositories import (
    AccountRepository,
    BusinessDayRepository,
    PositionRepository,
    ProductRepository,
    ReferenceRateRepository,
    TransactionRepository,
)
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

        # Estimada (RN-REC-01): só calcula, não grava nada. Taxas e cotas da data de movimento.
        days = (to_date - from_date).days + 1
        business_date = BusinessDayRepository.get_current(self.context).business_date
        products = ProductRepository.list(self.context, None, None)
        held = {product.id: (quantity, cost) for product, quantity, cost in PositionRepository.sum_by_product(self.context)}
        estimated = {
            "fund_administration_fee": self.fund_administration_fee(products, held, business_date, days),
            "own_issue_spread": self.own_issue_spread(products, held, business_date, days),
            "float": self.float_estimate(business_date, days),
        }

        return {
            "from": from_date.isoformat(),
            "to": to_date.isoformat(),
            "days": days,
            "realized": {"fee_amount": fee_amount},
            "estimated": estimated,
            "total_amount": fee_amount + sum(estimate["amount"] for estimate in estimated.values()),
        }

    def fund_administration_fee(self, products: list, held: dict, business_date: date, days: int) -> dict:
        """RN-REC-05: patrimônio do fundo ao preço do dia × taxa × dias / 365."""
        fund = next(product for product in products if product.administration_fee_bps)
        quantity, _ = held.get(fund.id, (Decimal(0), 0))
        unit_price = ProductRepository.get_price_on(self.context, fund.id, business_date).unit_price
        # Centavos para baixo, como o valor atual da posição (RN-POS-01).
        base_amount = int(quantity * unit_price * 100)
        return {
            "base_amount": base_amount,
            "annual_rate_bps": fund.administration_fee_bps,
            "amount": estimate(base_amount, fund.administration_fee_bps, days),
        }

    def own_issue_spread(self, products: list, held: dict, business_date: date, days: int) -> dict:
        """RN-REC-06: custo aplicado em CDB e LCI × CDI × (1 − percentual pago) × dias / 365.

        Cada título paga um percentual do CDI, então a conta é por produto, somada no fim.
        """
        cdi_bps = ReferenceRateRepository.get_on(self.context, "CDI", business_date).annual_rate_bps
        base_amount = 0
        spread = Decimal(0)
        for product in products:
            if product.price_source_code is None:
                _, cost = held.get(product.id, (Decimal(0), 0))
                base_amount += cost
                spread += Decimal(cost) * cdi_bps * (10000 - product.cdi_percentage_bps) / 10000
        return {"base_amount": base_amount, "amount": int(spread * days / (10000 * 365))}

    def float_estimate(self, business_date: date, days: int) -> dict:
        """RN-REC-07: saldo parado nas contas de cliente × Selic × dias / 365 (sem a conta do banco)."""
        selic_bps = ReferenceRateRepository.get_on(self.context, "SELIC", business_date).annual_rate_bps
        base_amount = AccountRepository.sum_customer_balances(self.context, ["ACTIVE", "BLOCKED"])
        return {"base_amount": base_amount, "annual_rate_bps": selic_bps, "amount": estimate(base_amount, selic_bps, days)}


def estimate(base_amount: int, annual_rate_bps: int, days: int) -> int:
    """Base × taxa anual × dias / 365, em centavos para baixo. Aproximação linear (RN-REC-05)."""
    return int(Decimal(base_amount) * annual_rate_bps * days / (10000 * 365))
