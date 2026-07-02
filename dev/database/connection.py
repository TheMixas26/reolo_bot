import sqlite3
from pathlib import Path
from threading import RLock


DB_PATH = Path("dev/database/bot.sqlite3")
_DB_LOCK = RLock()

def _get_connection() -> sqlite3.Connection:
    """Создает папку для базы данных, если ее нет, и возвращает соединение с базой данных"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


_conn = _get_connection()
