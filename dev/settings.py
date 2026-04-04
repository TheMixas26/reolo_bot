"""Публичные настройки проекта без секретов.

Этот файл предназначен для параметров, которые удобно менять при переиспользовании
репозитория: названия ботов, брендинг, отображаемые названия валюты и прочие
несекретные значения.
"""

PROJECT_NAME = "Предложка Империи"
CHANNEL_NAME = "Имперский Вестник"

MAIN_BOT_NAME = "Предложка"
BANK_BOT_NAME = "Имперское Казначейство"
BANK_MENU_TITLE = "Имперский банк"
RPG_BOT_NAME = "RPG-бот"
RPG_BOT_USERNAME = "@reolo_rpg_bot"

AI_PERSONA_NAME = "Варя"
CREATOR_NAME = "Амодерни Боровски"

CURRENCY_NAME_PLURAL = "Имперские Баты"
CURRENCY_NAME_GENITIVE = "Имперских Батов"
CURRENCY_SHORT_NAME = "IB"
BANK_TRANSFER_COMMISSION = 0.02

CALENDAR_NAME = "Имперский календарь"
CALENDAR_DATE_LABEL = "Имперская дата"
CALENDAR_EVENTS_LABEL = "Имперские праздники"

TEMPLATE_VALUES = {
    "PROJECT_NAME": PROJECT_NAME,
    "CHANNEL_NAME": CHANNEL_NAME,
    "MAIN_BOT_NAME": MAIN_BOT_NAME,
    "BANK_BOT_NAME": BANK_BOT_NAME,
    "BANK_MENU_TITLE": BANK_MENU_TITLE,
    "RPG_BOT_NAME": RPG_BOT_NAME,
    "RPG_BOT_USERNAME": RPG_BOT_USERNAME,
    "AI_PERSONA_NAME": AI_PERSONA_NAME,
    "CREATOR_NAME": CREATOR_NAME,
    "CURRENCY_NAME_PLURAL": CURRENCY_NAME_PLURAL,
    "CURRENCY_NAME_GENITIVE": CURRENCY_NAME_GENITIVE,
    "CURRENCY_SHORT_NAME": CURRENCY_SHORT_NAME,
    "BANK_TRANSFER_COMMISSION_PERCENT": int(BANK_TRANSFER_COMMISSION * 100),
    "CALENDAR_NAME": CALENDAR_NAME,
    "CALENDAR_DATE_LABEL": CALENDAR_DATE_LABEL,
    "CALENDAR_EVENTS_LABEL": CALENDAR_EVENTS_LABEL,
}


def render_text_template(text: str) -> str:
    """Подставляет публичные настройки в текстовые шаблоны."""
    return text.format(**TEMPLATE_VALUES)
