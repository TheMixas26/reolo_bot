from __future__ import annotations

import pickle
from pathlib import Path

from analytics.stats import log_event
from config import bank_bot, commission
from database.sqlite_db import get_balance, set_balance, user_exists

CURRENCY_INFO_PATH = Path("varibles/currency_info.pickle")


def edit_currency_info(message, bats: int, rubles: int) -> None:
    """Обновляет данные о валюте в файле."""
    CURRENCY_INFO_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CURRENCY_INFO_PATH.open("wb") as file:
        pickle.dump([bats, rubles], file)

    bank_bot.reply_to(message, "Данные изменены")
    log_event(
        "currency_info_updated",
        bot="bank",
        user_id=message.from_user.id,
        chat_id=message.chat.id,
        metadata={"bats": bats, "rubles": rubles},
    )


def view_currency_info() -> str:
    if not CURRENCY_INFO_PATH.exists():
        return "Курс валюты пока не настроен."

    with CURRENCY_INFO_PATH.open("rb") as file:
        currency_info = pickle.load(file)

    exchange_rate = currency_info[0] / currency_info[1]
    return f"{exchange_rate} Имперских батов равняются 1 рублю"


def get_money(message, amount: int) -> None:
    try:
        to_user_id = int(message.text)
        if not user_exists(to_user_id):
            bank_bot.reply_to(message, "У этого id не обнаружено банковского аккаунта")
            return

        sender_id = message.from_user.id
        sender_balance = get_balance(sender_id)
        if sender_balance < amount:
            bank_bot.reply_to(message, "Не достаточно средств")
            return

        commission_amount = amount * commission
        credited_amount = amount - commission_amount
        set_balance(to_user_id, get_balance(to_user_id) + credited_amount)
        set_balance(sender_id, sender_balance - amount)

        bank_bot.reply_to(message, "Перевод совершён!")
        bank_bot.send_message(to_user_id, "Вам поступил перевод! Проверьте свой баланс: /bank")
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
        bank_bot.reply_to(message, "Это не id, попробуйте с самого начала")


def send_money(message) -> None:
    try:
        amount = int(message.text)
        sender_balance = get_balance(message.from_user.id)

        if sender_balance >= amount:
            bank_bot.reply_to(message, "Хорошо, а теперь, введите id получателя")
            bank_bot.register_next_step_handler(message, get_money, amount)
            log_event(
                "bank_transfer_initiated",
                bot="bank",
                user_id=message.from_user.id,
                chat_id=message.chat.id,
                metadata={"amount": amount},
            )
        else:
            bank_bot.reply_to(message, "Не достаточно средств")

    except ValueError:
        bank_bot.reply_to(message, "Это не число, попробуйте с самого начала")


def bank_get_balance(message) -> float:
    return get_balance(message.from_user.id)
