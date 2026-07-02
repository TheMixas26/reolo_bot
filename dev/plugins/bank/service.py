from __future__ import annotations

import pickle
from pathlib import Path

from core.core_plugin.stats import log_event
from config import bank_bot
from varibles.dialogue_loader import TEXT
from database.sqlite_db import user_exists
from .db import get_balance, set_balance
from settings import BANK_TRANSFER_COMMISSION, CURRENCY_NAME_GENITIVE

CURRENCY_INFO_PATH = Path("dev/varibles/currency_info.pickle")


def edit_currency_info(message, bats: int, rubles: int) -> None:
    """Обновляет данные о валюте в файле."""
    CURRENCY_INFO_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CURRENCY_INFO_PATH.open("wb") as file:
        pickle.dump([bats, rubles], file)

    bank_bot.reply_to(message, TEXT("currency_changed"))
    log_event(
        "currency_info_updated",
        bot="bank",
        user_id=message.from_user.id,
        chat_id=message.chat.id,
        metadata={"bats": bats, "rubles": rubles},
    )


def view_currency_info() -> str:
    if not CURRENCY_INFO_PATH.exists():
        return TEXT("err", "currency_not_set")

    with CURRENCY_INFO_PATH.open("rb") as file:
        currency_info = pickle.load(file)

    exchange_rate = currency_info[0] / currency_info[1]
    return f"{exchange_rate} {CURRENCY_NAME_GENITIVE.lower()} равняются 1 рублю"


def get_money(message, amount: int) -> None:
    try:
        to_user_id = int(message.text)
        if not user_exists(to_user_id):
            bank_bot.reply_to(message, TEXT("err", "no_bank_account"))
            return

        sender_id = message.from_user.id
        sender_balance = get_balance(sender_id)
        if sender_balance < amount:
            bank_bot.reply_to(message, TEXT("err", "not_enought_money"))
            return

        commission_amount = amount * BANK_TRANSFER_COMMISSION
        credited_amount = amount - commission_amount
        set_balance(to_user_id, get_balance(to_user_id) + credited_amount)
        set_balance(sender_id, sender_balance - amount)

        bank_bot.reply_to(message, TEXT("transfer_success"))
        bank_bot.send_message(to_user_id, TEXT("notification", "transfer"))
        log_event(
            "bank_transfer_completed",
            bot="bank",
            user_id=sender_id,
            chat_id=message.chat.id,
            metadata={
                "amount": amount,
                "credited_amount": round(credited_amount, 2),
                "commission_amount": round(commission_amount, 2),
                "receiver_id": to_user_id,
            },
        )

    except ValueError:
        bank_bot.reply_to(message, TEXT("err", "not_id"))


def send_money(message) -> None:
    try:
        amount = int(message.text)
        sender_balance = get_balance(message.from_user.id)

        if sender_balance >= amount:
            bank_bot.reply_to(message, TEXT("ask_for_id"))
            bank_bot.register_next_step_handler(message, get_money, amount)
            log_event(
                "bank_transfer_initiated",
                bot="bank",
                user_id=message.from_user.id,
                chat_id=message.chat.id,
                metadata={"amount": amount},
            )
        else:
            bank_bot.reply_to(message, TEXT("err", "not_enought_money"))

    except ValueError:
        bank_bot.reply_to(message, TEXT("err", "not_int"))


def bank_get_balance(message) -> float:
    return get_balance(message.from_user.id)
