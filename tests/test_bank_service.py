from __future__ import annotations

import asyncio
import os
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, call, patch

from tests.support import isolated_project_imports


class BankServiceTests(unittest.TestCase):
    def test_dice_history_limits_and_cleanup(self):
        with isolated_project_imports():
            service = __import__("plugins.bank.service", fromlist=["DiceHistory", "DiceHistoryLimitError"])
            history = service.DiceHistory()

            self.assertEqual(asyncio.run(history.get(10)), 0)
            self.assertEqual(asyncio.run(history.increase(10, 3)), 3)
            self.assertEqual(asyncio.run(history.get(10)), 3)
            self.assertEqual(asyncio.run(history.decrease(10, 2)), 1)
            self.assertEqual(asyncio.run(history.decrease(10, 10)), 0)

            with self.assertRaises(service.DiceHistoryLimitError):
                asyncio.run(history.increase(10, 11))

            history._history[7] = 1
            history.tick()
            self.assertNotIn(7, history)

    def test_view_currency_info_reads_rate_from_file(self):
        with isolated_project_imports():
            service = __import__("plugins.bank.service", fromlist=["view_currency_info"])

            with tempfile.TemporaryDirectory() as tmp_dir:
                info_path = Path(tmp_dir) / "currency_info.txt"
                info_path.write_text("20, 5", encoding="utf-8")

                with patch.object(service, "CURRENCY_INFO_PATH", info_path):
                    self.assertEqual(
                        service.view_currency_info(),
                        "4.0 имперских батов равняются 1 рублю",
                    )

    def test_send_money_rejects_insufficient_balance(self):
        with isolated_project_imports():
            service = __import__("plugins.bank.service", fromlist=["send_money"])
            message = types.SimpleNamespace(
                from_user=types.SimpleNamespace(id=7),
                answer=AsyncMock(),
            )

            with patch.object(service, "get_balance", AsyncMock(return_value=15)):
                result = asyncio.run(service.send_money(message, 30))

            self.assertFalse(result)
            message.answer.assert_awaited_once_with(service.TEXT("err", "not_enought_money"))

    def test_get_money_transfers_funds_and_notifies_receiver(self):
        with isolated_project_imports():
            service = __import__("plugins.bank.service", fromlist=["get_money"])
            message = types.SimpleNamespace(
                text="42",
                from_user=types.SimpleNamespace(id=8),
                chat=types.SimpleNamespace(id=99),
                answer=AsyncMock(),
                bot=types.SimpleNamespace(send_message=AsyncMock()),
            )

            async def fake_get_balance(user_id):
                balances = {8: 100.0, 42: 50.0}
                return balances[user_id]

            with patch.object(service, "user_exists", AsyncMock(return_value=True)), \
                 patch.object(service, "get_balance", side_effect=fake_get_balance), \
                 patch.object(service, "set_balance", AsyncMock()) as set_balance_mock, \
                 patch.object(service, "log_event") as log_event_mock:
                asyncio.run(service.get_money(message, 100))

            self.assertEqual(
                set_balance_mock.await_args_list,
                [
                    call(42, 148.0),
                    call(8, 0.0),
                ],
            )
            message.answer.assert_awaited_once_with(service.TEXT("transfer_success"))
            message.bot.send_message.assert_awaited_once_with(42, service.TEXT("notification", "transfer"))
            self.assertEqual(log_event_mock.call_count, 1)

    def test_get_money_rejects_non_numeric_recipient_id(self):
        with isolated_project_imports():
            service = __import__("plugins.bank.service", fromlist=["get_money"])
            message = types.SimpleNamespace(
                text="abc",
                from_user=types.SimpleNamespace(id=8),
                chat=types.SimpleNamespace(id=99),
                answer=AsyncMock(),
                bot=types.SimpleNamespace(send_message=AsyncMock()),
            )

            with patch.object(service, "user_exists", AsyncMock(return_value=True)), \
                 patch.object(service, "get_balance", AsyncMock()) as get_balance_mock, \
                 patch.object(service, "set_balance", AsyncMock()) as set_balance_mock:
                asyncio.run(service.get_money(message, 50))

            get_balance_mock.assert_not_called()
            set_balance_mock.assert_not_called()
            message.answer.assert_awaited_once_with(service.TEXT("err", "not_id"))

    def test_send_money_confirms_transfer_and_logs_init(self):
        with isolated_project_imports():
            service = __import__("plugins.bank.service", fromlist=["send_money"])
            message = types.SimpleNamespace(
                from_user=types.SimpleNamespace(id=7),
                chat=types.SimpleNamespace(id=99),
                answer=AsyncMock(),
            )

            with patch.object(service, "get_balance", AsyncMock(return_value=120)), \
                 patch.object(service, "log_event") as log_event_mock:
                result = asyncio.run(service.send_money(message, 50))

            self.assertTrue(result)
            message.answer.assert_awaited_once_with(service.TEXT("ask_for_id"))
            log_event_mock.assert_called_once()
            self.assertEqual(log_event_mock.call_args.kwargs["metadata"]["amount"], 50)

    def test_send_money_rejects_non_positive_amount(self):
        with isolated_project_imports():
            service = __import__("plugins.bank.service", fromlist=["send_money"])
            message = types.SimpleNamespace(
                from_user=types.SimpleNamespace(id=7),
                chat=types.SimpleNamespace(id=99),
                answer=AsyncMock(),
            )

            with patch.object(service, "get_balance", AsyncMock(return_value=100)), \
                 patch.object(service, "log_event") as log_event_mock:
                result = asyncio.run(service.send_money(message, 0))

            self.assertFalse(result)
            message.answer.assert_awaited_once_with(service.TEXT("err", "not_enought_money"))
            log_event_mock.assert_not_called()

    def test_get_money_skips_transfer_for_missing_receiver_account(self):
        with isolated_project_imports():
            service = __import__("plugins.bank.service", fromlist=["get_money"])
            message = types.SimpleNamespace(
                text="55",
                from_user=types.SimpleNamespace(id=8),
                chat=types.SimpleNamespace(id=99),
                answer=AsyncMock(),
                bot=types.SimpleNamespace(send_message=AsyncMock()),
            )

            with patch.object(service, "user_exists", AsyncMock(return_value=False)), \
                 patch.object(service, "get_balance", AsyncMock()) as get_balance_mock, \
                 patch.object(service, "set_balance", AsyncMock()) as set_balance_mock:
                asyncio.run(service.get_money(message, 20))

            get_balance_mock.assert_not_called()
            set_balance_mock.assert_not_called()
            message.answer.assert_awaited_once_with(service.TEXT("err", "no_bank_account"))
