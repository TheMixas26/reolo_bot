import json, random
from pathlib import Path

DIALOGS = {}

DEV_DIR = Path(__file__).resolve().parents[1]
CORE_TEXTS = DEV_DIR / "core" / "core_plugin" / "texts.json"
PLUGINS_DIR = DEV_DIR / "plugins"


def deep_merge(dst: dict, src: dict):
    """Рекурсивно объединяет словари."""
    for key, value in src.items():
        if (
            key in dst
            and isinstance(dst[key], dict)
            and isinstance(value, dict)
        ):
            deep_merge(dst[key], value)
        else:
            dst[key] = value


def load_json(path: Path) -> dict:
    """Загружает json-файл."""
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def plugin_text_path(plugin) -> Path:
    """Возвращает путь к texts.json для класса плагина."""
    module_parts = plugin.__module__.split(".")
    plugin_dir_name = module_parts[1] if len(module_parts) > 1 else plugin.__name__
    return PLUGINS_DIR / plugin_dir_name / "texts.json"


def iter_plugin_texts() -> list[Path]:
    """Находит тексты всех плагинов без импорта самих плагинов."""
    if not PLUGINS_DIR.exists():
        return []
    return sorted(PLUGINS_DIR.glob("*/texts.json"))


def load_texts(enabled_plugins=None):
    """Загружает тексты ядра и плагинов."""

    DIALOGS.clear()

    # Основные тексты
    if CORE_TEXTS.exists():
        deep_merge(DIALOGS, load_json(CORE_TEXTS))

    text_files = iter_plugin_texts()

    for text_file in text_files:
        if text_file.exists():
            deep_merge(DIALOGS, load_json(text_file))


def TEXT(*keys, **kwargs):
    """Получить строку локализации.

    Функция поддерживает:
        TEXT("a", "b")
        TEXT("a", "b/c")
        TEXT("a/b/c")
        TEXT("a/b", "c/d")
    """

    path = []

    for key in keys:
        if isinstance(key, str):
            path.extend(part for part in key.split("/") if part)
        else:
            path.append(key)

    data = DIALOGS

    try:
        for key in path:
            data = data[key]

        if isinstance(data, list):
            data = random.choice(data)

        if isinstance(data, str) and kwargs:
            data = data.format(**kwargs)

        return data

    except (KeyError, TypeError):
        return f"[MISSING TEXT: {' -> '.join(map(str, keys))}]"


load_texts()


def see_drama_script():
    """Обожаю себя, функция бьуквально называется увидеть сценарий пьесы...."""
    load_texts()
    with open("all_texts.json", "w", encoding="utf-8") as file:
        json.dump(DIALOGS, file, ensure_ascii=False, indent=4)


if __name__ == "__main__":
    see_drama_script()