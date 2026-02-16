from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import time


@dataclass(frozen=True)
class TransferFeatureContext:
    amount: float
    sender_old_balance: float
    receiver_old_balance: float
    step: int
    timestamp: datetime


def _resolve_step(explicit_step: int | None = None) -> int:
    if explicit_step is not None:
        if explicit_step < 0:
            raise ValueError("step must be greater than or equal to 0.")
        return explicit_step
    return int(time.time() // 3600)


def compute_transfer_feature_context(
    *,
    amount: float,
    sender_old_balance: float,
    receiver_old_balance: float,
    now: datetime | None = None,
    step: int | None = None,
) -> TransferFeatureContext:
    if amount <= 0:
        raise ValueError("Transfer amount must be greater than 0.")
    if sender_old_balance < 0 or receiver_old_balance < 0:
        raise ValueError("Balances cannot be negative.")
    if sender_old_balance < amount:
        raise ValueError("Insufficient sender balance for the requested transfer amount.")

    resolved_now = now or datetime.now(UTC)
    resolved_step = _resolve_step(step)
    return TransferFeatureContext(
        amount=float(amount),
        sender_old_balance=float(sender_old_balance),
        receiver_old_balance=float(receiver_old_balance),
        step=resolved_step,
        timestamp=resolved_now,
    )


def build_model_feature_payload(context: TransferFeatureContext) -> dict[str, float | int | bool]:
    sender_new_balance = context.sender_old_balance - context.amount
    receiver_new_balance = context.receiver_old_balance + context.amount
    hour = context.timestamp.hour
    is_night = hour < 6

    amount_ratio = (
        context.amount / context.sender_old_balance
        if context.sender_old_balance > 0
        else context.amount
    )

    return {
        "step": context.step,
        "amount": context.amount,
        "oldbalanceOrg": context.sender_old_balance,
        "newbalanceOrig": sender_new_balance,
        "oldbalanceDest": context.receiver_old_balance,
        "newbalanceDest": receiver_new_balance,
        "hour": hour,
        "is_night": is_night,
        "amount_ratio": amount_ratio,
        "sender_balance_change": context.sender_old_balance - sender_new_balance,
        "receiver_balance_change": receiver_new_balance - context.receiver_old_balance,
        "orig_balance_zero": context.sender_old_balance == 0,
        "dest_balance_zero": context.receiver_old_balance == 0,
        "type_TRANSFER": True,
    }


def mask_account_number(account_number: str) -> str:
    normalized = account_number.strip()
    if len(normalized) <= 4:
        return normalized
    return f"{'*' * (len(normalized) - 4)}{normalized[-4:]}"

