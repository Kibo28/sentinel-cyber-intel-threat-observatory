# Cyber Intel — Threat Observatory

![Cyber Intel — Threat Observatory](app/static/assets/cyber-intel-wordmark.png)

Cyber Intel is a self-hosted dashboard for tracking public cybersecurity reporting and advisories. It collects RSS, Atom, and CISA Known Exploited Vulnerabilities (KEV) records into a persistent SQLite archive with source links, change history, search, and exports.

## Get started

- **Synology DSM 7:** Follow the [Container Manager installation guide](SYNOLOGY_INSTALLATION.md) for setup, backups, email, and updates. The [SSH deployment quickstart](SYNOLOGY_DEPLOYMENT.md) is an alternative for Docker Compose v2.
- **Already installed?** Follow the [step-by-step update guide](docs/UPDATING.md).
- **Local development:** See [Run locally](#run-locally) below.
- **Integrations:** See the [HTTP API reference](docs/API.md).

The default NAS URL is `http://YOUR_NAS_IP:8791`. The dashboard has no login or per-user permissions. Anyone who can reach it can view and export records, change shared settings, and use any configured email or update controls. Keep it on a trusted LAN or behind a private VPN or an authenticated HTTPS reverse proxy.

## Interface preview

These screenshots show illustrative demonstration records.

| Light mode | Dark mode |
| --- | --- |
| ![Cyber Intel home dashboard, light](docs/dashboard-light-demo.png) | ![Cyber Intel home dashboard, dark](docs/dashboard-dark-demo.png) |

## Use the dashboard

| Where | What to do |
| --- | --- |
| **Home dashboard** | See collection status and recent records, or search across the archive by title, summary, source, vendor, CVE, or a favorite's tag. |
| **Category views** | Browse Cyberattacks, Vulnerabilities, Data breaches, Ransomware, and Technology. Search and filter by severity. |
| **View details** | See the source links, evidence, and change timeline. Use **Copy summary**, **Email draft**, or **Share…** when the browser supports it. |
| **New findings** | See records added or materially updated since the last **Mark all as seen**. The first visit starts with the current archive as the baseline. |
| **Favorites** | In **View details**, choose **Add to favorites**, then enter a tag and select **Add tag**. Search or filter saved records in **Favorites**. Tags are case-insensitive and stay with the record if you remove it from Favorites and later add it again. |
| **History archive** | Browse all records grouped by first-seen date. **CSV ↧** downloads the whole archive regardless of active search or severity filters. |
| **Intelligence sources** | Check feed status and last check dates. Add, edit, disable, or remove RSS/Atom feeds, manage research links, and toggle CISA KEV or FIRST EPSS. Feed changes take effect at the next refresh. |
| **Collection settings** | Choose a daily run or an interval of 1–1,440 minutes. **Sync feeds** queues a refresh immediately, regardless of the schedule. [Optional SMTP digests](SYNOLOGY_INSTALLATION.md#email-digests) cover refreshes with new records or material updates. |
| **App updates** | Queue a new dashboard version for Synology Task Scheduler to install. See [how to set up and run an update](docs/UPDATING.md). |

Favorites, tags, source settings, and collection settings are shared across browsers on the same installation. The color theme and the **New findings** seen marker are stored in each browser. Clearing browser data resets those preferences without deleting the archive.

## Collection and interpretation

- **Official feeds:** CISA Cybersecurity Advisories, CERT-FR Alerts, Threats, and Advisories, plus recent CISA KEV additions from the official JSON catalog or its official GitHub mirror.
- **Research and news feeds:** SANS Internet Storm Center, watchTowr Labs, BleepingComputer, The Record, SecurityWeek, and Krebs on Security.
- **Enrichment:** FIRST EPSS supplies a best-effort exploitation probability for newly collected CVEs. An unavailable value is shown as **Not retrieved**.
- **Research links:** watchTowr Intelligence, Cloudflare Radar, GreyNoise, Ransomware.live, NCSC Switzerland, and ENISA open in your browser. The app does not collect from these pages.

The default schedule runs at startup and at 08:00 Europe/Zurich each day while the service is running. The default lookback is seven days for dated feed entries and CISA KEV additions. It limits collection, so older records already in SQLite stay available. A source with **Fetch error** could not be checked; an **OK** count is the number of eligible entries found, including duplicates.

The app merges records by canonical article URL, a single CVE in vulnerability records, or a near-identical headline in the same category. A CISA KEV listing can add a material update to an existing vulnerability. Severity is a triage estimate. CVSS describes vulnerability severity, and EPSS estimates exploitation probability. A news report or a KEV listing does not establish impact on your systems. Check the linked sources and assess your own exposure.

## Import, export, and backup

- **Import history** accepts a JSON object with an `items` array from the earlier standalone dashboard. The browser limit is 15 MB and the server accepts up to 5,000 items per import. See the [example archive](example/cyber-threat-archive-2026-11-09.json) for the legacy format. Imported records are marked as unverified and deduplicated against the archive.
- **CSV ↧** in **History archive** downloads the record list. [`/api/export.json`](docs/API.md#exports-and-legacy-import) downloads all records plus source links and change history.
- For migration or recovery, [back up the SQLite data directory and deployment settings](SYNOLOGY_INSTALLATION.md#11-backup-and-update-without-losing-history). The exports omit favorites, tags, and settings, and **Import history** does not restore the original change timeline.

## Run locally

From the repository root, with Python 3.12 (the Docker image version):

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt pytest
python -m pytest -q
CTI_DB_PATH=./data/dev-cti.db CTI_RUN_ON_START=false \
  python -m uvicorn app.main:app --host 127.0.0.1 --port 8791
```

Open `http://127.0.0.1:8791`. This example uses a separate development database and skips the startup collection. Use **Sync feeds** to try a collection. Run one app worker so scheduling and sync status stay in a single process.

Keep deployment files and private exports out of Git. See the [public repository checklist](PUBLIC_REPOSITORY_CHECKLIST.md) before publishing changes.
