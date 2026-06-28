from __future__ import annotations

import types
import unittest
from unittest.mock import patch

from tests.support import FakeBot, isolated_project_imports


def _make_context(adapter):
    return types.SimpleNamespace(
        predlojka_bot=FakeBot(),
        tg_adapter=adapter,
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


class SubmissionAcknowledgementTests(unittest.TestCase):
    def test_acknowledge_submission_routes_feedback_by_content_type(self):
        with isolated_project_imports():
            handlers_module = __import__("plugins.predlojka.handlers", fromlist=["_acknowledge_submission", "SubmissionContent"])
            adapter = types.SimpleNamespace()
            handlers_module._configure_runtime(_make_context(adapter))

        message = types.SimpleNamespace(chat=types.SimpleNamespace(id=321), message_id=55)
        cases = (
            ("event", False, "event"),
            ("report", False, "report"),
            ("message", False, "message"),
            ("post", False, "!"),
            ("post", True, "?"),
        )

        for route, is_question, expected_mes_type in cases:
            content = handlers_module.SubmissionContent(
                clean_text="hello",
                public_tags=[],
                is_anonymous=False,
                is_question=is_question,
                wants_ai=False,
                ignore_reaction=False,
                route=route,
            )
            with self.subTest(route=route, is_question=is_question):
                with patch.object(handlers_module, "thx_for_message", return_value="ACK") as thx_mock, patch.object(
                    adapter, "send_message", create=True
                ) as send_mock, patch.object(handlers_module, "_maybe_send_advice") as advice_mock:
                    handlers_module._acknowledge_submission(message, content, "Test User")
                    thx_mock.assert_called_once_with("Test User", mes_type=expected_mes_type)
                    send_mock.assert_called_once_with(message.chat.id, "ACK", reply_markup=handlers_module.q)
                    advice_mock.assert_called_once_with(message, content)

    def test_acknowledge_submission_skips_feedback_when_reaction_is_ignored(self):
        with isolated_project_imports():
            handlers_module = __import__("plugins.predlojka.handlers", fromlist=["_acknowledge_submission", "SubmissionContent"])
            adapter = types.SimpleNamespace()
            handlers_module._configure_runtime(_make_context(adapter))

        message = types.SimpleNamespace(chat=types.SimpleNamespace(id=321), message_id=55)
        content = handlers_module.SubmissionContent(
            clean_text="hello",
            public_tags=[],
            is_anonymous=False,
            is_question=False,
            wants_ai=False,
            ignore_reaction=True,
            route="post",
        )

        with patch.object(handlers_module, "thx_for_message") as thx_mock, patch.object(
            adapter, "send_message", create=True
        ) as send_mock, patch.object(handlers_module, "_maybe_send_advice") as advice_mock:
            handlers_module._acknowledge_submission(message, content, "Test User")
            thx_mock.assert_not_called()
            send_mock.assert_not_called()
            advice_mock.assert_not_called()
