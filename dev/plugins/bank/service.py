from __future__ import annotations

from pathlib import Path

from core.core_plugin.stats import log_event
from varibles import TEXT
from database.sqlite_db import user_exists
from .db import get_balance, set_balance
from settings import BANK_TRANSFER_COMMISSION, CURRENCY_NAME_GENITIVE

CURRENCY_INFO_PATH = Path("dev/varibles/currency_info.txt")


class DiceHistoryError(Exception):
    """Базовая ошибка DiceHistory."""
class DiceHistoryLimitError(DiceHistoryError):
    """Попытка увеличить значение выше допустимого лимита."""

class DiceHistory:
    MAX_VALUE = 10

    def __init__(self):
        self._history: dict[int, int] = {}

    async def get(self, user_id: int) -> int:
        """Возвращает текущее значение пользователя. Если пользователя нет — 0."""
        return self._history.get(user_id, 0)

    async def increase(self, user_id: int, amount: int = 1) -> int:
        """Увеличивает значение пользователя и возвращает новое значение."""
        current = await self.get(user_id)
        new_value = current + amount

        if new_value > self.MAX_VALUE:
            raise DiceHistoryLimitError(
                f"Cannot increase user {user_id}: "
                f"{current} + {amount} > {self.MAX_VALUE}"
            )

        self._history[user_id] = new_value
        return new_value

    async def decrease(self, user_id: int, amount: int = 1) -> int:
        """Уменьшает значение пользователя, но не ниже 0."""
        current = await self.get(user_id)
        new_value = max(0, current - amount)

        self._history[user_id] = new_value
        return new_value

    async def remove(self, user_id: int) -> None:
        """Полностью удаляет пользователя из истории."""
        self._history.pop(user_id, None)

    def __contains__(self, user_id: int) -> bool:
        return user_id in self._history

    def __len__(self) -> int:
        return len(self._history)

    def tick(self) -> None:
        for user_id in list(self._history):
            self._history[user_id] -= 1

            if self._history[user_id] <= 0:
                del self._history[user_id]


def edit_currency_info(message, bats: int, rubles: int) -> None:
    """Обновляет данные о валюте в файле."""
    CURRENCY_INFO_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CURRENCY_INFO_PATH.open("w") as f:
        f.write(f"{bats}, {rubles}")

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

    with CURRENCY_INFO_PATH.open("r") as f:
        currency_info = f.read().split(', ') 

    exchange_rate = int(currency_info[0]) / int(currency_info[1])
    return f"{exchange_rate} {CURRENCY_NAME_GENITIVE.lower()} равняются 1 рублю"


async def get_money(message, amount: int) -> None:
    try:
        to_user_id = int(message.text)
        if not await user_exists(to_user_id):
            await message.answer(TEXT("err", "no_bank_account"))
            return

        sender_id = message.from_user.id
        sender_balance = await get_balance(sender_id)
        if sender_balance < amount:
            await message.answer(TEXT("err", "not_enought_money"))
            return

        commission_amount = amount * BANK_TRANSFER_COMMISSION
        credited_amount = amount - commission_amount
        await set_balance(to_user_id, await get_balance(to_user_id) + credited_amount)
        await set_balance(sender_id, sender_balance - amount)

        await message.answer(TEXT("transfer_success"))
        await message.bot.send_message(to_user_id, TEXT("notification", "transfer"))
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
        await message.answer(TEXT("err", "not_id"))


async def send_money(message, amount: int) -> bool:
    if amount <= 0:
        await message.answer(TEXT("err", "not_enought_money"))
        return False

    sender_balance = await get_balance(message.from_user.id)

    if sender_balance < amount:
        await message.answer(TEXT("err", "not_enought_money"))
        return False

    await message.answer(TEXT("ask_for_id"))
    log_event(
        "bank_transfer_initiated",
        bot="bank",
        user_id=message.from_user.id,
        chat_id=message.chat.id,
        metadata={"amount": amount},
    )
    return True


async def bank_get_balance(message) -> float:
    return await get_balance(message.from_user.id)
