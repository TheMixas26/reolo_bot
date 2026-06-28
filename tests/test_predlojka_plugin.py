from __future__ import annotations

import types
import unittest

from tests.support import FakeBot, isolated_project_imports


def _make_context(bot: FakeBot):
    return types.SimpleNamespace(
        predlojka_bot=bot,
        tg_adapter=types.SimpleNamespace(),
        admin_id=100,
        config=types.SimpleNamespace(
            channel=200,
            channel_red=201,
            chat_mishas_den=202,
            backup_chat=203,
            HIBERNATION=False,
        ),
        post_publisher=types.SimpleNamespace(),
        telegram_admin_target=types.SimpleNamespace(),
    )


class PredlojkaPluginTests(unittest.TestCase):
    def test_register_handlers_uses_context_bot_and_runtime(self):
        with isolated_project_imports():
            handlers_module = __import__("plugins.predlojka.handlers", fromlist=["register_handlers"])
            bot = FakeBot()
            context = _make_context(bot)

            handlers_module.register_handlers(context)

            self.assertIs(handlers_module.plugin_context, context)
            self.assertIs(handlers_module.predlojka_telegram_adapter, context.tg_adapter)
            self.assertEqual(handlers_module.admin, context.admin_id)
            self.assertEqual(len(bot.message_handlers), 2)
            self.assertEqual(len(bot.callback_query_handlers), 10)

            handlers_module.register_handlers(context)
            self.assertEqual(len(bot.message_handlers), 2)
            self.assertEqual(len(bot.callback_query_handlers), 10)

    def test_submission_tags_are_parsed_as_control_and_public_tags(self):
        with isolated_project_imports():
            service_module = __import__("plugins.predlojka.service", fromlist=["_parse_submission_text"])

            content = service_module._parse_submission_text("Текст #анон #вопрос #мем #Мем email#не-тег")

            self.assertEqual(content.clean_text, "Текст email#не-тег")
            self.assertEqual(content.public_tags, ["#мем"])
            self.assertTrue(content.is_anonymous)
            self.assertTrue(content.is_question)
            self.assertFalse(content.wants_ai)
            self.assertEqual(content.route, "post")

    def test_route_tags_are_control_tags_not_public_tags(self):
        with isolated_project_imports():
            service_module = __import__("plugins.predlojka.service", fromlist=["_parse_submission_text"])

            content = service_module._parse_submission_text("#dm #event #ai #ignore Привет #важно")

            self.assertEqual(content.clean_text, "Привет")
            self.assertEqual(content.public_tags, ["#важно"])
            self.assertEqual(content.route, "message")
            self.assertTrue(content.wants_ai)
            self.assertTrue(content.ignore_reaction)
            self.assertFalse(content.is_question)


if __name__ == "__main__":
    unittest.main()
