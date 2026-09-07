from __future__ import annotations

import asyncio
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from tests.support import isolated_project_imports


class PermisionsTests(unittest.TestCase):
    def test_permission_rank_hierarchy(self):
        with isolated_project_imports():
            permissions = __import__("core.permissions", fromlist=["has_rank", "ROLE_RANK"])

            self.assertTrue(permissions.has_rank("member", "member"))
            self.assertTrue(permissions.has_rank("admin", "member"))
            self.assertTrue(permissions.has_rank("owner", "admin"))
            self.assertFalse(permissions.has_rank("trusted", "admin"))
            self.assertFalse(permissions.has_rank("member", "trusted"))

    def test_get_role_prioritizes_owner_and_defaults_to_member(self):
        with isolated_project_imports():
            permissions = __import__("core.permissions", fromlist=["get_role"])

            async def run_checks():
                with patch.object(permissions, "fetchval", AsyncMock(return_value="trusted")):
                    self.assertEqual(await permissions.get_role(42, owner_id=99), "trusted")
                    self.assertEqual(await permissions.get_role(99, owner_id=99), "owner")

                with patch.object(permissions, "fetchval", AsyncMock(return_value=None)):
                    self.assertEqual(await permissions.get_role(42, owner_id=99), "member")

                with patch.object(permissions, "fetchval", AsyncMock(return_value="admin")):
                    self.assertEqual(await permissions.get_role(42, owner_id=99), "admin")

            asyncio.run(run_checks())

    def test_set_role_and_required_role_reject_unknown_values(self):
        with isolated_project_imports():
            permissions = __import__("core.permissions", fromlist=["set_role", "set_required_role"])

            with self.assertRaises(ValueError):
                asyncio.run(permissions.set_role(1, "god"))

            with self.assertRaises(ValueError):
                asyncio.run(permissions.set_required_role("cmd", "god"))

    def test_admin_commands_are_rejected_for_non_admins(self):
        with isolated_project_imports():
            admin_service = __import__("plugins.admin_utils.service", fromlist=["set_commands"])

            context = types.SimpleNamespace(
                admin_id=10,
                predlojka_bot=types.SimpleNamespace(set_my_commands=AsyncMock()),
                bank_bot=None,
                rpg_bot=None,
            )
            message = types.SimpleNamespace(from_user=types.SimpleNamespace(id=7))

            asyncio.run(admin_service.set_commands(context, message))

            context.predlojka_bot.set_my_commands.assert_not_called()

    def test_command_registry_reads_sections_and_formats_descriptions(self):
        with isolated_project_imports():
            admin_service = __import__("plugins.admin_utils.service", fromlist=["_load_command_registry", "_normalize_section_name"])
            context = types.SimpleNamespace(
                logger=types.SimpleNamespace(warning=lambda *args, **kwargs: None),
                predlojka_bot=types.SimpleNamespace(send_message=AsyncMock()),
                admin=1,
            )

            with tempfile.TemporaryDirectory() as tmp_dir:
                commands_file = Path(tmp_dir) / "command_list.txt"
                commands_file.write_text(
                    "[predlojka_user]\nstart - Запустить бота\n[bank_admin]\ntransfer - Перевод\n",
                    encoding="utf-8",
                )

                with patch.object(admin_service, "COMMANDS_FILE_PATH", commands_file):
                    registry = admin_service._load_command_registry(context)

            self.assertIn("predlojka_user", registry)
            self.assertEqual(registry["predlojka_user"][0].command, "start")
            self.assertEqual(registry["predlojka_user"][0].description, "Запустить бота")
            self.assertEqual(registry["bank_admin"][0].command, "transfer")
            self.assertEqual(admin_service._normalize_section_name(" [bank_admin] "), "bank_admin")

    def test_has_permission_checks_role_and_command_override(self):
        with isolated_project_imports():
            filters_module = __import__("core.filters", fromlist=["HasPermission"])
            context = types.SimpleNamespace(admin_id=10)
            event = types.SimpleNamespace(from_user=types.SimpleNamespace(id=7))
            policy = filters_module.HasPermission(context, default="member", command="some_command")

            async def run_checks():
                with patch.object(filters_module.permissions, "get_required_role", AsyncMock(return_value="admin")), \
                     patch.object(filters_module.permissions, "get_role", AsyncMock(return_value="trusted")):
                    self.assertFalse(await policy(event))

                with patch.object(filters_module.permissions, "get_required_role", AsyncMock(return_value="trusted")), \
                     patch.object(filters_module.permissions, "get_role", AsyncMock(return_value="trusted")):
                    self.assertTrue(await policy(event))

            asyncio.run(run_checks())

    def test_get_commands_for_set_appends_admin_commands_when_requested(self):
        with isolated_project_imports():
            admin_service = __import__("plugins.admin_utils.service", fromlist=["get_commands_for_set"])
            context = types.SimpleNamespace()

            registry = {
                "predlojka_user": ["user_command"],
                "predlojka_admin": ["admin_command"],
            }

            with patch.object(admin_service, "_load_command_registry", return_value=registry):
                self.assertEqual(admin_service.get_commands_for_set(context, "predlojka"), ["user_command"])
                self.assertEqual(
                    admin_service.get_commands_for_set(context, "predlojka", include_admin=True),
                    ["user_command", "admin_command"],
                )
