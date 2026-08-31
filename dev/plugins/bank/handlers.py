from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from varibles import TEXT
from core.core_plugin.stats import log_command_usage, log_event
from .service import edit_currency_info, view_currency_info, send_money, bank_get_balance, get_money

from database.sqlite_db import user_exists, create_user_if_missing

from settings import (
    BANK_BOT_NAME,
    BANK_MENU_TITLE,
    BANK_TRANSFER_COMMISSION,
    CURRENCY_NAME_GENITIVE,
)

class BankStates(StatesGroup):
    waiting_for_edit = State()
    waiting_for_amount = State()
    waiting_for_recipient = State()

predlojka_router = Router(name="bank-predlojka")
bank_router = Router(name="bank-plugin")


def register_handlers(context):
    admin_id = context.admin_id


    @predlojka_router.message(Command("edit_currency"))
    async def editing_currency(message: Message, state: FSMContext):
        log_command_usage("predlojka", "edit_currency", message)

        if message.chat.id == admin_id:
            await message.answer(TEXT("answer_for_edit_currency"))
            await state.set_state(BankStates.waiting_for_edit)
        else:
            await message.answer(TEXT("not_an_admin"))


    @predlojka_router.message(BankStates.waiting_for_edit)
    async def editing_currency2(message: Message, state: FSMContext):
        try:
            purumpurum = [x.strip() for x in message.text.split(",")]
            a = int(purumpurum[0])
            b = int(purumpurum[1])
            edit_currency_info(message, a, b)
            await message.answer(TEXT("currency_changed"))
        except Exception:
            await message.answer(TEXT("err", "unknown_error"))
        finally:
            await state.clear()





    @bank_router.message(Command("start"))
    async def hello_from_bank_bot(message: Message):
        log_command_usage("bank", "start", message)

        if await user_exists(message.from_user.id):
            await message.answer(f"С возвращением в {BANK_BOT_NAME}!")
        else:
            await create_user_if_missing(
                message.from_user.id,
                message.from_user.first_name,
                message.from_user.last_name
            )
            await message.answer(f"Добро пожаловать в {BANK_BOT_NAME}!")
            log_event("user_registered", bot="bank", user_id=message.from_user.id, chat_id=message.chat.id)


    @bank_router.message(Command("bank"))
    async def bank_meetings(message: Message):
        log_command_usage("bank", "bank", message)

        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="💰Узнать баланс")],
                [KeyboardButton(text="🔁Перевод")],
                [KeyboardButton(text="📈Курс валюты")],
                [KeyboardButton(text="❔Помощь")],
            ],
            resize_keyboard=True,
        )

        await message.answer(
            f"Здравствуйте! Добро пожаловать в {BANK_MENU_TITLE}! Что вы хотели сделать?",
            reply_markup=keyboard
        )


    @bank_router.message(F.text.in_({"💰Узнать баланс", "🔁Перевод", "📈Курс валюты", "❔Помощь"}))
    async def what_do_you_want_from_bank(message: Message, state: FSMContext):
        text = message.text

        if text == "💰Узнать баланс":
            log_event("bank_menu_selected", bot="bank", user_id=message.from_user.id,
                    chat_id=message.chat.id, metadata={"action": "balance"})

            balance = await bank_get_balance(message)
            await message.answer(
                f"Ваш баланс: {balance} {CURRENCY_NAME_GENITIVE}\n"
                f"Ваш id: <code>{message.from_user.id}</code>",
                parse_mode="HTML",
                reply_markup=ReplyKeyboardRemove()
            )

        elif text == "🔁Перевод":
            log_event("bank_menu_selected", bot="bank", user_id=message.from_user.id,
                    chat_id=message.chat.id, metadata={"action": "transfer"})

            await message.answer("Введите сумму перевода:", reply_markup=ReplyKeyboardRemove())
            await state.set_state(BankStates.waiting_for_amount)

        elif text == "📈Курс валюты":
            log_event("bank_menu_selected", bot="bank", user_id=message.from_user.id,
                    chat_id=message.chat.id, metadata={"action": "currency"})

            await message.answer(view_currency_info(), reply_markup=ReplyKeyboardRemove())

        elif text == "❔Помощь":
            log_event("bank_menu_selected", bot="bank", user_id=message.from_user.id,
                    chat_id=message.chat.id, metadata={"action": "help"})

            help_text = rf"""
    💳 *Функции банка*:  
    \- Проверка баланса 
    \- Переводы средств \(комиссия {int(BANK_TRANSFER_COMMISSION * 100)}%\)  
    \- Узнавайте курс {CURRENCY_NAME_GENITIVE.lower()} к рублям

    📈 *О курсе валют*:  
    Курс рассчитывается как общее число батов\, делённое на количество рублей, на которых подкреплена валюта  

    🎉 *Бонусы*:  
    За каждый одобренный пост вам начисляются баты\, их количество зависит от объёма текста в посте \(WIP\)

    📥 Всё просто и удобно\!
            """.strip()

            await message.answer(help_text, parse_mode="MarkdownV2", reply_markup=ReplyKeyboardRemove())


    @bank_router.message(BankStates.waiting_for_amount)
    async def process_transfer_amount(message: Message, state: FSMContext):
        try:
            amount = int(message.text.strip())
            if amount <= 0:
                raise ValueError("Сумма должна быть положительной")

            if await send_money(message, amount):
                await state.update_data(amount=amount)
                await state.set_state(BankStates.waiting_for_recipient)

        except ValueError:
            await message.answer("❗ Пожалуйста, введите корректную положительную сумму.")
            return

        except Exception as e:
            await message.answer("❌ Произошла ошибка при выполнении перевода.")

        finally:
            if await state.get_state() != BankStates.waiting_for_recipient:
                await state.clear()

    @bank_router.message(BankStates.waiting_for_recipient)
    async def process_transfer_recipient(message: Message, state: FSMContext):
        data = await state.get_data()
        amount = int(data.get("amount", 0))
        if amount <= 0:
            await message.answer("❌ Не вижу сумму перевода, начните заново через /bank.")
            await state.clear()
            return

        await get_money(message, amount)
        await state.clear()



    return predlojka_router, bank_router
