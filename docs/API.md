# HTTP API reference

The dashboard and API share the same base URL. The examples use `http://127.0.0.1:8791`; use your configured NAS address and port for a deployed instance. The app has no built-in authentication and does not serve Swagger, ReDoc, or an OpenAPI document. Keep the API reachable only by trusted clients.

All write requests require `X-CTI-Request: dashboard`. This header is a browser request safeguard, not an API credential. Include `Content-Type: application/json` when sending JSON.

## Read endpoints

| Method and path | Response |
| --- | --- |
| `GET /health` | `{"status":"ok"}` if the app responds. Check `/api/sources` for feed health. |
| `GET /api/stats` | Record counts, latest collection run, sync status, schedule, and latest change ID. |
| `GET /api/incidents` | `items` with pagination. Query parameters: `category`, `severity`, `q`, `limit` (default 500, capped at 2,000), and `offset` (default 0). `q` searches title, summary, CVE, and source name. |
| `GET /api/incidents/{id}` | Record details, source links, change history, and an `organization` object with its favorite state and tags. Returns 404 if the record is missing. |
| `GET /api/favorites` | `favorites` maps saved record IDs to tag dictionaries. |
| `GET /api/sources` | Configured feed status, research links, and editable `config` with its revision. |
| `GET /api/settings` | Collection schedule, email toggle, whether SMTP settings are present, and the revision. |
| `GET /api/update` | NAS updater `state` and `revision` (commit SHA when known). Reports `disabled` if updater status is unavailable. |

For example, fetch a page of vulnerability records:

```bash
curl -fsS 'http://127.0.0.1:8791/api/incidents?category=Vulnerabilities&limit=100&offset=0'
```

Records are sorted newest first by `first_seen`. Increase `offset` by the number of returned items to get the next page. For a single download containing the whole archive, use an export.

## Write endpoints

| Method and path | Request and result |
| --- | --- |
| `POST /api/sync` | No body. Returns 202 when queued or 409 when a refresh is already queued or running. Read `/api/stats` for progress. |
| `PATCH /api/incidents/{id}/organization` | Send any of `favorite` (boolean), `add_tag`, or `remove_tag`. Tags are trimmed, compared without regard to case, and limited to 40 characters. Returns the updated organization. |
| `PUT /api/sources` | Send the entire `config` from `GET /api/sources` with your edits and the current `revision`. Returns the saved configuration and status. |
| `PUT /api/settings` | Send `revision`, `interval_minutes` (1–1,440 or `null` for daily), and `email_enabled`. Enabling digests requires SMTP settings. |
| `POST /api/settings/test-email` | No body. Sends to the recipients configured on the NAS and returns the number of `refused_recipients`. SMTP configuration errors can return 422; delivery attempt failures can return 502. |
| `POST /api/update` | No body. Returns 202 when queued, 409 if an update is active, or 503 if the updater is unavailable. Read `/api/update` for progress. Requires [NAS setup](../SYNOLOGY_INSTALLATION.md#enable-the-app-updates-button). |

When saving sources or settings, a 409 means the revision is stale. Fetch the latest data and reapply your edits before retrying. For source configuration:

- `feeds` holds up to 50 entries with `name`, `url`, `category` (`auto` or one of the five dashboard categories), `source_type` (`news`, `research`, or `official`), and `enabled`.
- `external` holds up to 50 research links with `name`, `url`, and optional `note`. The server does not fetch these links.
- `kev_enabled` and `epss_enabled` control the built-in CISA KEV and FIRST EPSS services. Source and link names are unique regardless of case; these two built-in names are reserved.

## Exports and legacy import

- `GET /api/export.csv` downloads a flat list of all records.
- `GET /api/export.json` returns `exported_at` and an `items` array containing the records with their source links and change history.
- `POST /api/import` expects an object containing an `items` array with at most 5,000 records. The [legacy example](../example/cyber-threat-archive-2026-11-09.json) shows supported fields. Use `headline` or `title`, and add context such as `type`, `description`, `date`, and `sources` when available. Results report `new`, `duplicate`, and `updated` counts.

A minimal import body looks like this:

```json
{
  "items": [
    {
      "headline": "Illustrative incident report",
      "type": "Cyberattack",
      "sources": [["Example source", "https://example.com/report"]]
    }
  ]
}
```

Import marks records as unverified. It does not replay exported change history or restore the original record metadata. Neither export includes favorites, tags, or collection settings. Use a [SQLite backup](../SYNOLOGY_INSTALLATION.md#11-backup-and-update-without-losing-history) to migrate or restore an installation.
