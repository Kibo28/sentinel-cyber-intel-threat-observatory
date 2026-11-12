# Cyber Intel — Threat Observatory

![Cyber Intel — Threat Observatory](app/static/assets/cyber-intel-wordmark.png)

A self-hosted cybersecurity intelligence dashboard for Synology NAS. Collect public advisories and news, track material updates in a persistent SQLite archive, and organize findings with favorites and tags.

| Task | Guide |
| --- | --- |
| Install with a ZIP download or Container Manager | [Synology DSM 7 installation](SYNOLOGY_INSTALLATION.md) |
| Install from a Git checkout over SSH | [Deploy from Git](SYNOLOGY_DEPLOYMENT.md) |
| Update the app, back up, or restore | [Update Cyber Intel on Synology](docs/UPDATING.md) |
| Read records, export the archive, or configure the app over HTTP | [HTTP API reference](docs/API.md) |

## Interface preview

The screenshots use illustrative findings.

| Light mode | Dark mode |
| --- | --- |
| ![Cyber Intel home dashboard, light](docs/dashboard-light-demo.png) | ![Cyber Intel home dashboard, dark](docs/dashboard-dark-demo.png) |

## What the dashboard collects

- **CISA Cybersecurity Advisories** and **CERT-FR** alerts, threats, and selected advisories come from public feeds.
- **SANS Internet Storm Center**, **watchTowr Labs**, **BleepingComputer**, **SecurityWeek**, **The Record**, and **Krebs on Security** provide research and news feeds.
- **CISA Known Exploited Vulnerabilities (KEV)** uses the official catalog with an official GitHub mirror as fallback. Recent KEV additions can become material updates to existing CVE records.
- **FIRST EPSS** provides best-effort exploitation probability enrichment for newly collected CVEs.
- **watchTowr Intelligence**, **Cloudflare Radar**, **GreyNoise**, **Ransomware.live**, **NCSC Switzerland**, and **ENISA** are browser links in **Intelligence sources**.

Findings are source-attributed leads and may contain unverified claims. Severity is an editorial triage estimate. Use the linked sources to verify claims and assess exposure in your environment.

## Use the dashboard

- **Sync feeds** starts a feed refresh. By default, the app also collects at startup and daily at 08:00 Europe/Zurich. In **Collection settings**, choose the daily schedule or an interval from 1 minute to 24 hours. The default collection lookback is 7 days for dated feed items and KEV additions. Older findings stay in the archive.
- In **Intelligence sources**, check each feed's status and last check. Use **Add RSS / Atom feed** or **Edit** to manage feeds, and **Add research link** for browser links. CISA KEV and FIRST EPSS have enable switches. Changes apply at the next refresh. Disabling or removing sources preserves their archived findings.
- **New findings** shows new records and material updates. The first visit uses the current archive as the starting point. **Mark all as seen** saves your progress in that browser.
- **History archive** shows saved records. Select **View details** to see the linked sources and timeline. **Copy summary**, **Email draft**, and **Share…** (where supported by the browser) let you share a finding.
- In **View details**, select **Add to favorites**, then **Add tag**. In **Favorites**, search or filter by tag. Favorites and tags are stored in SQLite and shared across browsers on the same installation.
- To receive a digest after a refresh with new findings or material updates, [configure SMTP on the NAS](SYNOLOGY_INSTALLATION.md#email-digests) and enable **Email new findings and material updates** in **Collection settings**.
- **App updates** installs a new dashboard build from GitHub after [one-time NAS setup](docs/UPDATING.md#set-up-the-nas-updater-once).

The app deduplicates by single CVE, canonical source URL, or a conservative match for nearly identical headlines in the same category. A new CISA KEV confirmation can update an existing finding's timeline. A fetch error in **Intelligence sources** means collection for that source failed.

## Archive exports and imports

- **CSV** in **History archive** downloads a flat list of records. `/api/export.json` adds source links and change history.
- **Import history** accepts a JSON object with an `items` array of up to 5,000 records. The dashboard limits files to 15 MB. The [example archive](example/cyber-threat-archive-2026-11-09.json) shows the older dashboard's export format. Imported findings are marked as unverified.
- The archive, favorites, tags, and saved collection settings live in `data/cti.db` by default. For a full recovery or migration, [back up the data directory and local configuration](docs/UPDATING.md#back-up).

## Access and deployment

Anyone who can reach the dashboard can read the archive and use its management API. Keep the service on a trusted private network. For remote access, use a private VPN or an authenticated HTTPS reverse proxy.

Docker runs the service as a non-root user with a read-only root filesystem. The data directory is mounted at `/data`. Keep `.env`, the database, and private backups out of the public repository. [Public repository checklist](PUBLIC_REPOSITORY_CHECKLIST.md)

## Developer tests

The Docker image uses Python 3.12. From the project folder, use a virtual environment to install dependencies and run the test suite.

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt pytest
python -m pytest -q
```
