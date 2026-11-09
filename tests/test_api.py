from unittest.mock import AsyncMock

from fastapi.testclient import TestClient


def test_dashboard_and_api_work_without_credentials(monkeypatch, tmp_path):
    monkeypatch.delenv("CTI_USERNAME", raising=False)
    monkeypatch.delenv("CTI_PASSWORD", raising=False)
    monkeypatch.setenv("CTI_RUN_ON_START", "false")

    from app import main

    monkeypatch.setattr(main.store, "DB_PATH", str(tmp_path / "cti.db"))
    monkeypatch.setattr(main, "run_sync", AsyncMock())

    with TestClient(main.app) as client:
        for path in (
            "/",
            "/static/app.js",
            "/static/app.css",
            "/static/assets/cyber-intel-icon.png",
            "/api/stats",
            "/api/incidents",
            "/api/sources",
            "/api/export.json",
            "/api/export.csv",
        ):
            assert client.get(path).status_code == 200, path

        headers = {"X-CTI-Request": "dashboard"}
        payload = {"items": [{"headline": "Sample incident"}]}
        assert client.post("/api/import", json=payload).status_code == 403
        assert client.post("/api/import", json=payload, headers=headers).json()["new"] == 1
        item = client.get("/api/incidents").json()["items"][0]
        assert client.get(f"/api/incidents/{item['id']}").json()["title"] == "Sample incident"
        assert client.post("/api/sync").status_code == 403
        assert client.post("/api/sync", headers=headers).status_code == 202
