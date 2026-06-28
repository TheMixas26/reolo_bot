from __future__ import annotations

import ast
import importlib
import sqlite3
import sys
import types as py_types
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEV_ROOT = PROJECT_ROOT / "dev"
CONFIG_PATH = DEV_ROOT / "config.py"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(DEV_ROOT) not in sys.path:
    sys.path.insert(0, str(DEV_ROOT))

PROJECT_MODULE_PREFIXES = (
    "achievements",
    "ai",
    "analytics",
    "bank",
    "card_game",
    "config",
    "core",
    "database",
    "handlers",
    "imp_cards",
    "main",
    "plugins",
    "posting",
    "settings",
    "utils",
    "varibles",
)

EXTERNAL_MODULE_PREFIXES = (
    "apscheduler",
    "quickjs",
    "requests",
    "telebot",
    "tinydb",
    "yandex_ai_studio_sdk",
)


@dataclass(frozen=True)
class TextCall:
    keys: tuple[str, ...]
    keyword_names: tuple[str, ...] = ()


def iter_python_files() -> list[Path]:
    ignored_parts = {"__pycache__", ".venv", "site-packages"}
    return sorted(
        path
        for path in DEV_ROOT.rglob("*.py")
        if not any(part in ignored_parts or part.startswith(".") for part in path.parts)
    )


def module_name_for_path(path: Path) -> str:
    return ".".join(path.relative_to(DEV_ROOT).with_suffix("").parts)


def discover_project_modules() -> list[str]:
    modules: list[str] = []
    for path in iter_python_files():
        module_name = module_name_for_path(path)
        if module_name == "config" and not CONFIG_PATH.exists():
            continue
        modules.append(module_name)
    return modules


def extract_literal_text_calls() -> set[TextCall]:
    calls: set[TextCall] = set()
    for path in iter_python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Name) or node.func.id != "TEXT":
                continue

            keys: list[str] = []
            for arg in node.args:
                if not isinstance(arg, ast.Constant) or not isinstance(arg.value, str):
                    keys = []
                    break
                keys.append(arg.value)
            if not keys:
                continue

            keyword_names = tuple(sorted(kw.arg for kw in node.keywords if kw.arg))
            calls.add(TextCall(tuple(keys), keyword_names))
    return calls


def build_sample_kwargs(keyword_names: tuple[str, ...]) -> dict[str, str]:
    samples = {
        "name": "Test User",
        "bot_version": "9.9.9",
    }
    return {name: samples.get(name, f"<{name}>") for name in keyword_names}


def _clear_loaded_modules(prefixes: tuple[str, ...]) -> None:
    for module_name in list(sys.modules):
        if any(module_name == prefix or module_name.startswith(f"{prefix}.") for prefix in prefixes):
            sys.modules.pop(module_name, None)


class FakeMessage:
    def __init__(self, chat_id: int | str = 0, text: str = "", message_id: int = 1):
        self.chat = py_types.SimpleNamespace(id=chat_id)
        self.text = text
        self.caption = text
        self.message_id = message_id


class FakeBot:
    def __init__(self, token: str = "stub-token"):
        self.token = token
        self.message_handlers: list[tuple[object, tuple, dict]] = []
        self.callback_query_handlers: list[tuple[object, tuple, dict]] = []

    @staticmethod
    def _decorator(*args, **kwargs):
        def _wrapper(func):
            return func

        return _wrapper

    message_handler = _decorator
    callback_query_handler = _decorator

    def register_message_handler(self, callback, *args, **kwargs):
        self.message_handlers.append((callback, args, kwargs))
        return None

    def register_callback_query_handler(self, callback, *args, **kwargs):
        self.callback_query_handlers.append((callback, args, kwargs))
        return None

    def send_message(self, chat_id, text, **kwargs):
        return FakeMessage(chat_id=chat_id, text=text)

    def reply_to(self, message, text, **kwargs):
        return FakeMessage(chat_id=getattr(message.chat, "id", 0), text=text)

    def send_document(self, chat_id, document, **kwargs):
        return FakeMessage(chat_id=chat_id)

    def send_photo(self, chat_id, photo, **kwargs):
        return FakeMessage(chat_id=chat_id)

    def send_video(self, chat_id, video, **kwargs):
        return FakeMessage(chat_id=chat_id)

    def send_audio(self, chat_id, audio, **kwargs):
        return FakeMessage(chat_id=chat_id)

    def send_voice(self, chat_id, voice, **kwargs):
        return FakeMessage(chat_id=chat_id)

    def send_sticker(self, chat_id, sticker, **kwargs):
        return FakeMessage(chat_id=chat_id)

    def send_media_group(self, chat_id, media, **kwargs):
        return [FakeMessage(chat_id=chat_id, message_id=index + 1) for index, _ in enumerate(media)]

    def copy_message(self, chat_id, from_chat_id, message_id, **kwargs):
        return FakeMessage(chat_id=chat_id, message_id=message_id)

    def edit_message_text(self, text, *, chat_id, message_id, **kwargs):
        return FakeMessage(chat_id=chat_id, text=text, message_id=message_id)

    def answer_callback_query(self, callback_id, text):
        return None

    def register_next_step_handler(self, message, callback, *args):
        return None

    def delete_message(self, chat_id, message_id):
        return True

    def get_me(self):
        return py_types.SimpleNamespace(id=1)

    def get_chat_member(self, chat_id, user_id):
        user = py_types.SimpleNamespace(id=user_id, first_name="Test", last_name="User", username="tester")
        return py_types.SimpleNamespace(user=user)

    def get_file(self, file_id):
        return py_types.SimpleNamespace(file_path=f"{file_id}.bin")

    def download_file(self, file_path):
        return b"stub"

    def set_my_commands(self, *args, **kwargs):
        return None

    def infinity_polling(self, *args, **kwargs):
        return None

    def __getattr__(self, name):
        def _method(*args, **kwargs):
            return None

        return _method


class ReplyKeyboardRemove:
    pass


class ReplyKeyboardMarkup:
    def __init__(self, row_width: int | None = None):
        self.row_width = row_width
        self.items: list[object] = []

    def add(self, *items):
        self.items.extend(items)


class KeyboardButton:
    def __init__(self, text: str):
        self.text = text


class InlineKeyboardMarkup:
    def __init__(self):
        self.items: list[object] = []

    def add(self, *items):
        self.items.extend(items)


class InlineKeyboardButton:
    def __init__(self, text: str, callback_data: str | None = None):
        self.text = text
        self.callback_data = callback_data


class BotCommand:
    def __init__(self, command: str, description: str):
        self.command = command
        self.description = description


class BotCommandScopeChat:
    def __init__(self, chat_id: int):
        self.chat_id = chat_id


class InputMediaPhoto:
    def __init__(self, media, caption: str | None = None, parse_mode: str | None = None):
        self.media = media
        self.caption = caption
        self.parse_mode = parse_mode


class InputMediaVideo:
    def __init__(self, media, caption: str | None = None, parse_mode: str | None = None):
        self.media = media
        self.caption = caption
        self.parse_mode = parse_mode


class FakeResponse:
    def __init__(self, payload: dict | None = None, content: bytes = b"", status_code: int = 200):
        self._payload = payload or {}
        self.content = content
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        return None


class RequestException(Exception):
    pass


class FakeCondition:
    def __and__(self, other):
        return self

    def __le__(self, other):
        return self

    def __eq__(self, other):
        return self

    def exists(self):
        return self

    def one_of(self, values):
        return self


class Query:
    def __getattr__(self, name):
        return FakeCondition()


class FakeRow(dict):
    def __init__(self, data: dict, doc_id: int):
        super().__init__(data)
        self.doc_id = doc_id


class FakeTable:
    def __init__(self):
        self.rows: list[FakeRow] = []

    def insert(self, record: dict):
        row = FakeRow(record, len(self.rows) + 1)
        self.rows.append(row)
        return row.doc_id

    def search(self, condition):
        return list(self.rows)

    def remove(self, doc_ids: list[int]):
        self.rows = [row for row in self.rows if row.doc_id not in set(doc_ids)]


class TinyDB:
    def __init__(self, *args, **kwargs):
        self.tables: dict[str, FakeTable] = {}

    def table(self, name: str):
        return self.tables.setdefault(name, FakeTable())


class BackgroundScheduler:
    def __init__(self):
        self.jobs: dict[str, object] = {}

    def add_job(self, func, trigger, *args, id: str | None = None, **kwargs):
        job = py_types.SimpleNamespace(func=func, trigger=trigger, id=id, args=args, kwargs=kwargs)
        if id:
            self.jobs[id] = job
        return job

    def get_job(self, job_id: str):
        return self.jobs.get(job_id)

    def start(self):
        return None

    def shutdown(self):
        return None


class QuickJsContext:
    def eval(self, expression: str):
        if "JSON.stringify" in expression:
            return "{}"
        if "format: 'short'" in expression:
            return "stub-short-date"
        if "format: 'full'" in expression:
            return "stub-full-date"
        if "ImperialCalendar({ format: 'iso' })" in expression:
            return {}
        return None


class FakeCompletionModel:
    def configure(self, **kwargs):
        return self

    def run(self, messages):
        choice = py_types.SimpleNamespace(text="stub ai response")
        return py_types.SimpleNamespace(choices=[choice])


class FakeCompletionsClient:
    def completions(self, name: str):
        return FakeCompletionModel()


class AIStudio:
    def __init__(self, *args, **kwargs):
        self.models = FakeCompletionsClient()


def _install_external_stubs() -> list[str]:
    installed_names: list[str] = []

    telebot_module = py_types.ModuleType("telebot")
    telebot_types = py_types.ModuleType("telebot.types")
    telebot_formatting = py_types.ModuleType("telebot.formatting")

    telebot_module.TeleBot = FakeBot
    telebot_module.types = telebot_types
    telebot_types.ReplyKeyboardRemove = ReplyKeyboardRemove
    telebot_types.ReplyKeyboardMarkup = ReplyKeyboardMarkup
    telebot_types.KeyboardButton = KeyboardButton
    telebot_types.InlineKeyboardMarkup = InlineKeyboardMarkup
    telebot_types.InlineKeyboardButton = InlineKeyboardButton
    telebot_types.BotCommand = BotCommand
    telebot_types.BotCommandScopeChat = BotCommandScopeChat
    telebot_types.InputMediaPhoto = InputMediaPhoto
    telebot_types.InputMediaVideo = InputMediaVideo
    telebot_formatting.apply_html_entities = lambda text, entities=None, custom_subs=None: text or ""

    requests_module = py_types.ModuleType("requests")
    requests_module.get = lambda *args, **kwargs: FakeResponse()
    requests_module.post = lambda *args, **kwargs: FakeResponse({"response": []})
    requests_module.exceptions = py_types.SimpleNamespace(RequestException=RequestException)

    quickjs_module = py_types.ModuleType("quickjs")
    quickjs_module.Context = QuickJsContext

    tinydb_module = py_types.ModuleType("tinydb")
    tinydb_module.Query = Query
    tinydb_module.TinyDB = TinyDB

    apscheduler_module = py_types.ModuleType("apscheduler")
    apscheduler_schedulers = py_types.ModuleType("apscheduler.schedulers")
    apscheduler_background = py_types.ModuleType("apscheduler.schedulers.background")
    apscheduler_background.BackgroundScheduler = BackgroundScheduler

    yandex_module = py_types.ModuleType("yandex_ai_studio_sdk")
    yandex_module.AIStudio = AIStudio

    stub_modules = {
        "telebot": telebot_module,
        "telebot.types": telebot_types,
        "telebot.formatting": telebot_formatting,
        "requests": requests_module,
        "quickjs": quickjs_module,
        "tinydb": tinydb_module,
        "apscheduler": apscheduler_module,
        "apscheduler.schedulers": apscheduler_schedulers,
        "apscheduler.schedulers.background": apscheduler_background,
        "yandex_ai_studio_sdk": yandex_module,
    }

    for name, module in stub_modules.items():
        sys.modules[name] = module
        installed_names.append(name)

    return installed_names


@contextmanager
def isolated_project_imports() -> Iterator[None]:
    _clear_loaded_modules(PROJECT_MODULE_PREFIXES + EXTERNAL_MODULE_PREFIXES)
    installed_names = _install_external_stubs()
    real_connect = sqlite3.connect

    def _connect_in_memory(*args, **kwargs):
        kwargs = dict(kwargs)
        kwargs["check_same_thread"] = False
        return real_connect(":memory:", **kwargs)

    with patch("sqlite3.connect", side_effect=_connect_in_memory):
        try:
            yield
        finally:
            _clear_loaded_modules(PROJECT_MODULE_PREFIXES + EXTERNAL_MODULE_PREFIXES)
            for name in reversed(installed_names):
                sys.modules.pop(name, None)


def import_module_fresh(module_name: str):
    return importlib.import_module(module_name)
