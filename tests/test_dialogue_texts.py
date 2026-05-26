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


class DialogueTextsTests(unittest.TestCase):
    def test_texts_json_contains_every_used_key(self):
        from varibles.dialogue_loader import DIALOGS

        for text_call in sorted(USED_TEXT_CALLS, key=lambda item: item.keys):
            with self.subTest(keys=" -> ".join(text_call.keys)):
                value = DIALOGS
                for key in text_call.keys:
                    self.assertIn(key, value, f"Missing dialogue key: {' -> '.join(text_call.keys)}")
                    value = value[key]

    def test_text_returns_string_for_every_used_key(self):
        from varibles import dialogue_loader

        with patch.object(dialogue_loader.random, "choice", side_effect=lambda values: values[0]):
            for text_call in sorted(USED_TEXT_CALLS, key=lambda item: item.keys):
                with self.subTest(keys=" -> ".join(text_call.keys)):
                    rendered = dialogue_loader.TEXT(*text_call.keys, **build_sample_kwargs(text_call.keyword_names))
                    self.assertIsInstance(rendered, str)
                    self.assertTrue(rendered.strip(), f"Empty text for {' -> '.join(text_call.keys)}")

    def test_name_placeholders_are_interpolated(self):
        from varibles import dialogue_loader

        expected_name = "Тест"
        named_calls = [text_call for text_call in USED_TEXT_CALLS if "name" in text_call.keyword_names]
        with patch.object(dialogue_loader.random, "choice", side_effect=lambda values: values[0]):
            for text_call in sorted(named_calls, key=lambda item: item.keys):
                with self.subTest(keys=" -> ".join(text_call.keys)):
                    rendered = dialogue_loader.TEXT(*text_call.keys, name=expected_name)
                    self.assertIn(expected_name, rendered)
