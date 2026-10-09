"""Tareas en segundo plano: una sola corriendo por usuario y tipo, con resultado o error."""
import asyncio

from app.services import background, operations_service


class _Db:
    def close(self):
        pass


def test_job_runs_once_and_reports(monkeypatch):
    monkeypatch.setattr(background, "SessionLocal", _Db)
    calls = []

    async def fn(db, progress):
        calls.append(1)
        progress("paso 1")
        await asyncio.sleep(0.01)
        return {"ok": True}

    async def main():
        first = background.start(99, "t", fn)
        again = background.start(99, "t", fn)  # mientras corre, no se duplica
        assert again is first and first["estado"] == "corriendo"
        await asyncio.sleep(0.05)
        return background.get(99, "t")

    job = asyncio.run(main())
    assert calls == [1]
    assert job["estado"] == "ok" and job["resultado"] == {"ok": True} and job["paso"] == "paso 1"


def test_job_error_is_reported(monkeypatch):
    monkeypatch.setattr(background, "SessionLocal", _Db)

    async def fn(db, progress):
        raise ValueError("se rompió")

    async def main():
        background.start(98, "t", fn)
        await asyncio.sleep(0.01)
        return background.get(98, "t")

    job = asyncio.run(main())
    assert job["estado"] == "error" and "se rompió" in job["error"]
    assert background.get(98, "otro") == {"estado": None}


def test_sync_history_stops_after_empty_streak(monkeypatch):
    from datetime import date

    this_year = date.today().year
    with_data = {this_year: 3, this_year - 1: 2, this_year - 3: 1}
    asked = []

    async def fake_sync(db, user_id, *, year):
        asked.append(year)
        return with_data.get(year, 0)

    monkeypatch.setattr(operations_service, "sync_operations", fake_sync)
    res = asyncio.run(operations_service.sync_history(None, 1, lambda _: None))
    assert res == {"found": 6, "oldest": this_year - 3}
    # Tras el último año con datos, 5 años vacíos y corta
    assert asked[-1] == this_year - 3 - operations_service.HISTORY_EMPTY_STREAK
