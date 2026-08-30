from __future__ import annotations

import unittest
from unittest.mock import patch

from tests.support import TextCall, build_sample_kwargs, extract_literal_text_calls


THX_TEXT_CALLS = {
    TextCall(("thx", "day", "variants_v"), ("name",)),
    TextCall(("thx", "day", "podval_variants_v"), ("name",)),
    TextCall(("thx", "day", "secret_variants_v"), ("name",)),
    TextCall(("thx", "day", "variants_q"), ("name",)),
    TextCall(("thx", "day", "events_variants")),
    TextCall(("thx", "day", "report_variants")),
    TextCall(("thx", "day", "message_variants")),
    TextCall(("thx", "night", "variants_v"), ("name",)),
    TextCall(("thx", "night", "podval_variants_v"), ("name",)),
    TextCall(("thx", "night", "secret_variants_v"), ("name",)),
    TextCall(("thx", "night", "variants_q"), ("name",)),
    TextCall(("thx", "night", "events_variants")),
    TextCall(("thx", "night", "report_variants")),
    TextCall(("thx", "night", "message_variants")),
}

USED_TEXT_CALLS = extract_literal_text_calls() | THX_TEXT_CALLS


def resolve_text_key(data: dict, keys: tuple[str, ...]):
    """Разрешает путь так же, как TEXT().

    Поддерживает:
        ("mafia", "table_full")
        ("mafia", "lobby/open")
        ("mafia/stats/header",)
        ("mafia", "role/card/mafia")
    """
    for key in keys:
        for part in key.split("/"):
            if not part:
                continue
            data = data[part]

    return data


class DialogueTextsTests(unittest.TestCase):
    def test_texts_json_contains_every_used_key(self):
        from varibles.dialogue_loader import DIALOGS

        for text_call in sorted(USED_TEXT_CALLS, key=lambda item: item.keys):
            display_key = " -> ".join(text_call.keys)

            with self.subTest(keys=display_key):
                try:
                    value = resolve_text_key(DIALOGS, text_call.keys)
                except KeyError as exc:
                    self.fail(
                        f"Missing dialogue key: {display_key} "
                        f"(missing part: {exc.args[0]!r})"
                    )

                self.assertIsNotNone(value)

    def test_text_returns_string_for_every_used_key(self):
        from varibles import dialogue_loader

        with patch.object(
            dialogue_loader.random,
            "choice",
            side_effect=lambda values: values[0],
        ):
            for text_call in sorted(USED_TEXT_CALLS, key=lambda item: item.keys):
                display_key = " -> ".join(text_call.keys)

                with self.subTest(keys=display_key):
                    rendered = dialogue_loader.TEXT(
                        *text_call.keys,
                        **build_sample_kwargs(text_call.keyword_names),
                    )

                    self.assertIsInstance(rendered, str)
                    self.assertTrue(
                        rendered.strip(),
                        f"Empty text for {display_key}",
                    )