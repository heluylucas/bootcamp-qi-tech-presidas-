from models import Account, AccountStatusEvent
from utils.dates import to_utc_text


def account_to_dict(account: Account, investments_amount: int) -> dict:
    return {
        "account_key": account.account_key,
        "status": account.status,
        "balance": account.balance,
        "investments_amount": investments_amount,
        "net_worth_amount": account.balance + investments_amount,
        "created_at": to_utc_text(account.created_at),
        "updated_at": to_utc_text(account.updated_at),
    }


def status_event_to_dict(event: AccountStatusEvent) -> dict:
    return {
        "from_status": event.from_status,
        "to_status": event.to_status,
        "reason": event.reason,
        "actor": event.actor,
        "created_at": to_utc_text(event.created_at),
    }
