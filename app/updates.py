"""Exchange update requests and status with the updater running on the NAS."""

import json
from pathlib import Path

REQUEST = Path("/run/cti-update/requests/pending")
STATUS = Path("/run/cti-update/status/status.json")


def status():
    try:
        result = json.loads(STATUS.read_text())
    except (OSError, ValueError):
        return {"state": "disabled", "revision": ""}
    if not isinstance(result, dict) or "state" not in result:
        return {"state": "disabled", "revision": ""}
    if result["state"] != "running" and REQUEST.is_dir():
        result["state"] = "queued"
    return result


def request():
    REQUEST.mkdir(mode=0o700)
