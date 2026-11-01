import sys
import time

import pytest
from fastapi.testclient import TestClient

from app.api import admin
from app.core.config import get_settings


@pytest.fixture()
def client(migrated, monkeypatch):
    from app.main import app

    monkeypatch.setenv("QSMF_ADMIN_TOKEN", "s3cret-token")
    get_settings.cache_clear()
    yield TestClient(app)
    get_settings.cache_clear()


def test_disabled_without_token_configured(migrated, monkeypatch):
    from app.main import app

    monkeypatch.delenv("QSMF_ADMIN_TOKEN", raising=False)
    get_settings.cache_clear()
    assert TestClient(app).post("/api/v1/admin/refresh", headers={"X-Admin-Token": "x"}).status_code == 404


def test_token_required(client):
    assert client.post("/api/v1/admin/refresh").status_code == 401
    assert client.post("/api/v1/admin/refresh", headers={"X-Admin-Token": "wrong"}).status_code == 401
    assert client.get("/api/v1/admin/refresh").status_code == 401


def wait(client, h):
    for _ in range(100):
        s = client.get("/api/v1/admin/refresh", headers=h).json()
        if not s["running"]:
            return s
        time.sleep(0.1)
    raise AssertionError("refresh did not finish")


def test_refresh_runs_once_at_a_time_and_reports_result(client, monkeypatch):
    h = {"X-Admin-Token": "s3cret-token"}
    monkeypatch.setattr(admin, "STEPS", [["-c", "import time; time.sleep(0.6); print('ok')"]])
    monkeypatch.setattr(admin.sys, "executable", sys.executable)
    # the real command is `python -m app.cli.pipeline <step>`; swap the module for a trivial one to avoid touching data
    monkeypatch.setattr(admin.subprocess, "run", lambda cmd, **kw: __import__("subprocess").CompletedProcess(cmd, 0, "done", ""))
    assert client.post("/api/v1/admin/refresh", headers=h).status_code == 202
    s = wait(client, h)
    assert s["ok"] is True and s["failed_step"] is None and s["finished"]


def test_failure_is_reported_with_the_failing_step(client, monkeypatch):
    h = {"X-Admin-Token": "s3cret-token"}
    monkeypatch.setattr(admin, "STEPS", [["recent"], ["metrics"]])
    calls = []

    def fake(cmd, **kw):
        calls.append(cmd[-1])
        return __import__("subprocess").CompletedProcess(cmd, 1 if cmd[-1] == "metrics" else 0, "", "boom")

    monkeypatch.setattr(admin.subprocess, "run", fake)
    assert client.post("/api/v1/admin/refresh", headers=h).status_code == 202
    s = wait(client, h)
    assert s["ok"] is False and s["failed_step"] == "metrics" and "boom" in s["log_tail"] and calls == ["recent", "metrics"]
    assert client.post("/api/v1/admin/refresh", headers=h).status_code == 202  # lock was released; can run again
    wait(client, h)
