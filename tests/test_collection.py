import asyncio
import socket
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi.testclient import TestClient

from app import ingest, main, notifications, preferences, store
from app.public_feed import read_public_feed
from app.rss import read_feed

WRITE_HEADER = {"X-CTI-Request": "dashboard"}


@pytest.fixture
def database(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "cti.db"))
    monkeypatch.setenv("CTI_RUN_ON_START", "false")
    monkeypatch.setattr(main, "HOUR", -1)
    store.init_db()


def test_sources_save_validate_and_survive_restart(database):
    with TestClient(main.app) as client:
        original = client.get("/api/sources").json()["config"]
        assert original["feeds"]
        edited = {**original, "kev_enabled": False, "epss_enabled": False}
        edited["feeds"] = [{"name": "Custom feed", "url": "https://example.org/feed", "enabled": False}]
        edited["external"] = [{"name": "Research link", "url": "https://example.org/research"}]
        invalid = {**edited, "feeds": [{"name": "Local", "url": "http://127.0.0.1/feed"}]}
        assert client.put("/api/sources", json=invalid, headers=WRITE_HEADER).status_code == 422
        assert client.put("/api/sources", json=edited).status_code == 403
        saved = client.put("/api/sources", json=edited, headers=WRITE_HEADER)
        assert saved.status_code == 200
        assert client.put("/api/sources", json=edited, headers=WRITE_HEADER).status_code == 409

    with TestClient(main.app) as client:
        sources = client.get("/api/sources").json()
        assert [(feed["name"], feed["enabled"]) for feed in sources["feeds"]] == [("Custom feed", False), ("CISA KEV", False)]
        assert sources["external"][0]["name"] == "Research link"
        assert sources["config"]["revision"] == 1


def test_settings_range_and_email_toggle(database, monkeypatch):
    monkeypatch.delenv("CTI_SMTP_HOST", raising=False)
    with TestClient(main.app) as client:
        assert client.get("/api/settings").json()["interval_minutes"] is None
        assert client.put("/api/settings", json={"interval_minutes": 0}, headers=WRITE_HEADER).status_code == 422
        assert client.put("/api/settings", json={"interval_minutes": 1441}, headers=WRITE_HEADER).status_code == 422
        assert client.put("/api/settings", json={"email_enabled": True}, headers=WRITE_HEADER).status_code == 422
        result = client.put("/api/settings", json={"interval_minutes": 1440}, headers=WRITE_HEADER)
        assert result.status_code == 200
        assert client.get("/api/stats").json()["interval_minutes"] == 1440
        saved = client.put("/api/settings", json={"revision": 1, "interval_minutes": 1}, headers=WRITE_HEADER)
        assert saved.json()["interval_minutes"] == 1


def test_scheduler_runs_an_overdue_interval(database, monkeypatch):
    assert store.save_setting("collection", {"interval_minutes": 1}, 0)
    earlier = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
    with store.connect() as db:
        db.execute("INSERT INTO sync_runs(started, completed) VALUES (?, ?)", (earlier, earlier))
    monkeypatch.setitem(ingest.STATE, "finished", None)
    queued = []
    monkeypatch.setattr(main, "queue_sync", queued.append)

    async def stop(_):
        raise asyncio.CancelledError

    monkeypatch.setattr(main.asyncio, "sleep", stop)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(main.schedule_loop(main.app))
    assert queued == [main.app]


def test_sync_collects_enabled_sources_and_emails_only_new_activity(database, monkeypatch):
    monkeypatch.setenv("CTI_SMTP_HOST", "smtp.example.org")
    monkeypatch.setenv("CTI_SMTP_FROM", "observatory@example.org")
    monkeypatch.setenv("CTI_SMTP_TO", "alerts@example.org")
    monkeypatch.setenv("CTI_SMTP_SECURITY", "ssl")
    config = preferences.SourceConfig(
        feeds=[{"name": "Enabled", "url": "https://example.org/feed"},
               {"name": "Disabled", "url": "https://example.org/disabled", "enabled": False}],
        external=[], kev_enabled=False, epss_enabled=False,
    )
    assert store.save_setting("sources", config.model_dump(exclude={"revision"}), 0)
    assert store.save_setting("collection", {"email_enabled": True}, 0)
    collected = []

    def feed_items(source, *_):
        collected.append(source.name)
        return [{"title": "New ransomware advisory", "severity": "High", "url": "https://example.org/advisory"}]

    monkeypatch.setattr(ingest, "feed_items", feed_items)
    connection = MagicMock()
    monkeypatch.setattr(notifications.smtplib, "SMTP_SSL", MagicMock(return_value=connection))

    assert ingest.sync_all()["new"] == 1
    cursor = store.stats()["last_change_id"]
    assert cursor > 0 and store.list_items()[0]["change_id"] == cursor
    assert ingest.sync_all()["duplicate"] == 1
    assert store.stats()["last_change_id"] == cursor
    assert collected == ["Enabled", "Enabled"]
    smtp = connection.__enter__.return_value
    smtp.send_message.assert_called_once()
    message = smtp.send_message.call_args.args[0]
    assert message["To"] == "alerts@example.org"
    assert "New ransomware advisory" in message.get_content()


def test_public_rss_pins_dns_and_blocks_redirect_to_private_address(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *_args, **_kw: [
        (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 443)),
    ])
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(302, headers={"Location": "https://127.0.0.1/feed"})

    with httpx.Client(transport=httpx.MockTransport(respond), follow_redirects=True) as client:
        with pytest.raises(ValueError, match="public address"):
            read_public_feed(client, "https://example.org/feed")
    assert len(requests) == 1
    assert requests[0].url.host == "93.184.216.34"
    assert requests[0].headers["host"] == "example.org"
    assert requests[0].extensions["sni_hostname"] == "example.org"


def test_utf16_rss_rejects_dtd_and_entities():
    feed = '<?xml version="1.0" encoding="UTF-16"?><!DOCTYPE rss [<!ENTITY name "expanded">]><rss><channel><item><title>&name;</title></item></channel></rss>'
    with pytest.raises(ValueError, match="DTD"):
        read_feed(feed.encode("utf-16"))
