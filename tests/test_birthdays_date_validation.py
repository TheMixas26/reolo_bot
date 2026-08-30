import asyncio
import types

from tests.support import isolated_project_imports


def test_add_birthday_valid_ddmm(monkeypatch):
    with isolated_project_imports():
        service = __import__("plugins.birthdays.service", fromlist=["add_birthday"]) 

        called = []

        async def fake_upsert(user_id, name, day, month, year, username=None):
            called.append({"user_id": user_id, "name": name, "day": day, "month": month, "year": year, "username": username})

        monkeypatch.setattr(service, "upsert_birthday", fake_upsert)

        context = types.SimpleNamespace(logger_factory=lambda *a, **k: types.SimpleNamespace(say=lambda *a, **k: None))

        result = asyncio.run(service.add_birthday(context, 123, "Test User", "01.02"))

        assert result is True
        assert len(called) == 1
        assert called[0]["day"] == 1
        assert called[0]["month"] == 2
        assert called[0]["year"] == 2000


def test_add_birthday_valid_ddmmyyyy(monkeypatch):
    with isolated_project_imports():
        service = __import__("plugins.birthdays.service", fromlist=["add_birthday"]) 

        called = []

        async def fake_upsert(user_id, name, day, month, year, username=None):
            called.append({"user_id": user_id, "name": name, "day": day, "month": month, "year": year, "username": username})

        monkeypatch.setattr(service, "upsert_birthday", fake_upsert)

        context = types.SimpleNamespace(logger_factory=lambda *a, **k: types.SimpleNamespace(say=lambda *a, **k: None))

        result = asyncio.run(service.add_birthday(context, 321, "Other", "05.11.1990"))

        assert result is True
        assert len(called) == 1
        assert called[0]["day"] == 5
        assert called[0]["month"] == 11
        assert called[0]["year"] == 1990


def test_add_birthday_invalid_date(monkeypatch):
    with isolated_project_imports():
        service = __import__("plugins.birthdays.service", fromlist=["add_birthday"]) 

        called = []

        async def fake_upsert(*args, **kwargs):
            called.append(True)

        monkeypatch.setattr(service, "upsert_birthday", fake_upsert)

        context = types.SimpleNamespace(logger_factory=lambda *a, **k: types.SimpleNamespace(say=lambda *a, **k: None))

        result = asyncio.run(service.add_birthday(context, 111, "Bad", "31.02"))

        assert result is False
        assert len(called) == 0


def test_add_birthday_invalid_string(monkeypatch):
    with isolated_project_imports():
        service = __import__("plugins.birthdays.service", fromlist=["add_birthday"]) 

        called = []

        async def fake_upsert(*args, **kwargs):
            called.append(True)

        monkeypatch.setattr(service, "upsert_birthday", fake_upsert)

        context = types.SimpleNamespace(logger_factory=lambda *a, **k: types.SimpleNamespace(say=lambda *a, **k: None))

        result = asyncio.run(service.add_birthday(context, 222, "BadStr", "abc"))

        assert result is False
        assert len(called) == 0
