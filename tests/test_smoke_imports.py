from __future__ import annotations

import contextlib
import io
import importlib
import py_compile
import unittest
import warnings

from tests.support import discover_project_modules, isolated_project_imports, iter_python_files


class SmokeImportTests(unittest.TestCase):
    def test_all_python_modules_compile_without_syntax_errors(self):
        for path in iter_python_files():
            with self.subTest(path=str(path)):
                py_compile.compile(str(path), doraise=True)

    def test_all_project_modules_import_in_isolation(self):
        for module_name in discover_project_modules():
            with self.subTest(module=module_name):
                with isolated_project_imports(), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
                    io.StringIO()
                ), warnings.catch_warnings():
                    warnings.simplefilter("ignore", ResourceWarning)
                    imported = importlib.import_module(module_name)
                self.assertIsNotNone(imported)
