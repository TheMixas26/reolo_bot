from __future__ import annotations

import unittest
from datetime import datetime
from unittest.mock import patch

from tests.support import isolated_project_imports


class FixedDayDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 5, 26, 12, 0, 0)


class ThxForMessageTests(unittest.TestCase):
    def test_thx_for_message_returns_string_for_all_types(self):
        with isolated_project_imports():
            utils_module = __import__("plugins.predlojka", fromlist=["thx_for_message"])

        with patch.object(utils_module, "TEXT", side_effect=lambda *keys, **kwargs: f"{'/'.join(keys)}::{kwargs.get('name', '')}"), patch.object(
            utils_module, "datetime", FixedDayDatetime
        ), patch.object(utils_module.random, "random", return_value=0.1):
            for mes_type in ("!", "?", "event", "report", "message", "unexpected"):
                with self.subTest(mes_type=mes_type):
                    rendered = utils_module.thx_for_message("Test User", mes_type)
                    self.assertIsInstance(rendered, str)
                    self.assertTrue(rendered)

    def test_exclamation_branch_chooses_expected_text_bucket(self):
        with isolated_project_imports():
            utils_module = __import__("plugins.predlojka", fromlist=["thx_for_message"])

        branch_cases = (
            (0.10, "thx/day/variants_v"),
            (0.95, "thx/day/secret_variants_v"),
            (0.99, "thx/day/podval_variants_v"),
        )
        for random_value, expected in branch_cases:
            with self.subTest(random_value=random_value):
                with patch.object(utils_module, "TEXT", side_effect=lambda *keys, **kwargs: "/".join(keys)), patch.object(
                    utils_module, "datetime", FixedDayDatetime
                ), patch.object(utils_module.random, "random", return_value=random_value):
                    self.assertEqual(utils_module.thx_for_message("Test User", "!"), expected)

    def test_random_modules_are_not_shadowed(self):
        with isolated_project_imports():
            dialogue_loader = __import__("varibles.dialogue_loader", fromlist=["TEXT"])
            utils_module = __import__("plugins.predlojka", fromlist=["thx_for_message"])

        self.assertTrue(hasattr(dialogue_loader.random, "choice"))
        self.assertTrue(hasattr(utils_module.random, "random"))
