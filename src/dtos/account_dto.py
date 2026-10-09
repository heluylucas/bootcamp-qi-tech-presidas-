from datetime import datetime, timezone

from models import Account, AccountStatusEvent


def account_to_dict(account: Account, investments_amount: int) -> dict:
    """`balance` é só o dinheiro na conta; `investments_amount`, as posições dela ao preço do dia."""
    return {
        "account_key": account.account_key,
        "status": account.status,
        "balance": account.balance,
        "investments_amount": investments_amount,
        # O capital total do cliente nesta conta. Calculado, não gravado: o preço muda todo dia.
        "net_worth_amount": account.balance + investments_amount,
        "created_at": to_utc_text(account.created_at),
        "updated_at": to_utc_text(account.updated_at),
    }


def status_event_to_dict(event: AccountStatusEvent) -> dict:
    return {
        # O nascimento da conta não tem status de origem (RN-CON-03).
        "from_status": event.from_status,
        "to_status": event.to_status,
        "reason": event.reason,
        # Quem fez: CUSTOMER (rota do cliente) ou BANK (rota interna), RN-CON-05.
        "actor": event.actor,
        "created_at": to_utc_text(event.created_at),
    }


def to_utc_text(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
