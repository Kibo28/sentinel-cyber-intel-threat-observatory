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


def test_favorites_and_tags_persist_independently_of_feed_activity(monkeypatch, tmp_path):
    from app import main

    monkeypatch.setenv("CTI_RUN_ON_START", "false")
    monkeypatch.setattr(main.store, "DB_PATH", str(tmp_path / "cti.db"))
    headers = {"X-CTI-Request": "dashboard"}

    with TestClient(main.app) as client:
        main.store.upsert({"title": "Example report", "url": "https://example.com/report"})
        item = client.get("/api/incidents").json()["items"][0]
        incident = f"/api/incidents/{item['id']}"
        edit = f"{incident}/organization"
        assert client.get(incident).json()["organization"] == {"favorite": False, "tags": {}}
        assert client.patch(edit, json={"favorite": True}).status_code == 403
        assert client.patch(edit, json={"add_tag": "   "}, headers=headers).status_code == 422
        assert client.patch("/api/incidents/missing/organization", json={"favorite": True}, headers=headers).status_code == 404

        def change(**payload):
            response = client.patch(edit, json=payload, headers=headers)
            assert response.status_code == 200
            return response.json()

        assert change(favorite=True) == {"favorite": True, "tags": {}}
        change(add_tag=" PHP ")
        change(add_tag="php")
        assert change(add_tag="crypto")["tags"] == {"php": "PHP", "crypto": "crypto"}
        assert change(remove_tag="CRYPTO")["tags"] == {"php": "PHP"}
        assert change(favorite=False) == {"favorite": False, "tags": {"php": "PHP"}}
        assert client.get("/api/favorites").json() == {"favorites": {}}
        change(favorite=True)
        assert client.get("/api/stats").json()["last_change_id"] == item["change_id"]

    with TestClient(main.app) as client:
        assert client.get("/api/favorites").json() == {"favorites": {item["id"]: {"php": "PHP"}}}
        assert client.get(incident).json()["organization"] == {"favorite": True, "tags": {"php": "PHP"}}


def test_app_update_requires_setup_and_queues_one_request(monkeypatch, tmp_path):
    from app import main, updates

    request = tmp_path / "pending"
    status = tmp_path / "status.json"
    monkeypatch.setattr(updates, "REQUEST", request)
    monkeypatch.setattr(updates, "STATUS", status)
    client = TestClient(main.app)
    headers = {"X-CTI-Request": "dashboard"}

    assert client.get("/api/update").json()["state"] == "disabled"
    assert client.post("/api/update", headers=headers).status_code == 503
    status.write_text('{"state":"idle","revision":""}')
    assert client.post("/api/update").status_code == 403
    assert client.post("/api/update", headers=headers).status_code == 202
    assert request.is_dir()
    assert client.get("/api/update").json()["state"] == "queued"
    assert client.post("/api/update", headers=headers).status_code == 409
