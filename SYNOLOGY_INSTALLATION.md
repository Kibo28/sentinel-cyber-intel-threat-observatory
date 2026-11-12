# Install Cyber Intel — Threat Observatory on Synology DSM 7

> **Project:** [sentinel-cyber-intel-threat-observatory](https://github.com/Kibo28/sentinel-cyber-intel-threat-observatory)  
> **Platform:** Synology DS723+ (or compatible NAS), DSM 7, **Container Manager**  
> **Deployment:** Docker Compose (`docker-compose.yml`) with local image build  
> **Default access:** `http://YOUR_NAS_IP:8791` (LAN only)  
> **Data:** Persistent SQLite database stored in `data/cti.db`

This guide uses **Synology Container Manager → Project** and the application's existing YAML file. SSH commands are provided for the steps that may require elevated permissions and as a fallback if Container Manager cannot build a local Dockerfile.

## 1. Prerequisites

- Synology DSM 7 with **Container Manager** installed from Package Center.
- Access to **File Station** and **Container Manager** with administrator permissions.
- Network access from the NAS to download the Python base image, Python packages, and public intelligence feeds.
- An available NAS port (the example uses **8791**).
- Source files from the [public GitHub repository](https://github.com/Kibo28/sentinel-cyber-intel-threat-observatory).

> **Network access.** Anyone who can reach the dashboard can access its archive and API. Keep the dashboard on a trusted private network and keep `.env` and the database local.

## 2. Download the application to Synology

1. On GitHub, open the repository and select **Code → Download ZIP**.
2. In DSM, open **File Station** and create this directory if it does not exist:

   ```text
   /volume1/docker/sentinel-cyber-intel-threat-observatory/
   ```

3. Upload and extract the ZIP. **Move the extracted contents into the project folder**, not an extra nested repository folder.
4. Check that the files are arranged as follows:

   ```text
   /volume1/docker/sentinel-cyber-intel-threat-observatory/
   ├── app/
   ├── data/
   ├── docs/
   ├── tests/
   ├── Dockerfile
   ├── docker-compose.yml
   ├── requirements.txt
   └── README.md
   ```

   The archive also contains hidden files such as `.gitignore`, `.dockerignore`, and `.github/`.

**Important:** `Dockerfile`, `docker-compose.yml`, `requirements.txt`, and the `app/` directory must be in the **same project root**. `build: .` in the YAML refers to this directory.

## 3. Verify `requirements.txt`

The file **must not be empty**. The current app requires these dependencies:

```text
fastapi==0.128.2
uvicorn==0.48.0
httpx==0.28.1
beautifulsoup4==4.14.3
```

Do not place those entries in the Compose YAML: Docker installs them during the image build using the `Dockerfile`.

## 4. Override the Compose defaults

To customize settings, create **`.env`** beside `docker-compose.yml`:

```bash
cd /volume1/docker/sentinel-cyber-intel-threat-observatory
vi .env
```

Set the values you want to override:

```dotenv
# Browser access
WEB_PORT=8791
BIND_IP=0.0.0.0

# Feed refresh — local Switzerland time
CTI_SYNC_HOUR=8
CTI_SYNC_MINUTE=0
CTI_RUN_ON_START=true
CTI_LOOKBACK_DAYS=7
```

- `WEB_PORT`: external NAS port. Change it if **8791** is already used by another service.
- `BIND_IP`: `0.0.0.0` listens on all NAS network interfaces; setting your actual NAS LAN IP limits binding to that address. Neither option adds encryption or replaces firewall rules.
- `CTI_SYNC_HOUR=8` / `CTI_SYNC_MINUTE=0`: daily refresh at **08:00 Europe/Zurich**; daylight-saving changes are handled by the application.
- `CTI_RUN_ON_START=true`: attempt a first feed collection shortly after startup.

Keep your `.env` file local to the NAS.

## 5. Create the persistent data folder and permissions

Open an SSH session to your NAS (if necessary, enable SSH temporarily in **Control Panel → Terminal & SNMP**).

```bash
ssh YOUR_SYNOLOGY_USER@YOUR_NAS_IP
```

If a non-root NAS account can write to the project's `data/` folder and any existing database files through its UID or primary GID, Compose can run with those IDs. Run these commands while signed in as that account:

```bash
id -u
id -g
```

Add the two values to the project's `.env`. Replace the example values with your results.

```dotenv
CTI_UID=1026
CTI_GID=100
```

For an existing installation, apply the updated Compose file and `.env` from the project directory with `sudo docker compose up -d --force-recreate`. If the database belongs to another UID, make sure the selected account can write to it and its containing folder before recreating the container.

With both settings omitted, the container uses the image's `cti` account (UID **10001**). For that setup, prepare the data folder as follows:

```bash
cd /volume1/docker/sentinel-cyber-intel-threat-observatory
sudo mkdir -p data
sudo chown -R 10001:10001 data
sudo chmod 750 data
```

**Do not change permissions on `/volume1/docker` as a whole**; it may contain unrelated running services. Change only this application's `data/` directory.

## 6. Check the Docker Compose YAML

The repository includes `docker-compose.yml`; **use that file** rather than creating a new configuration from scratch. The important parts are:

```yaml
services:
  cyber-intel-observatory:
    build: .
    container_name: cyber-intel-observatory
    restart: unless-stopped
    user: "${CTI_UID:-cti}:${CTI_GID:-cti}"
    ports:
      - "${BIND_IP:-0.0.0.0}:${WEB_PORT:-8791}:8791"
    environment:
      CTI_TIMEZONE: "Europe/Zurich"
      CTI_SYNC_HOUR: "${CTI_SYNC_HOUR:-8}"
      CTI_SYNC_MINUTE: "${CTI_SYNC_MINUTE:-0}"
      CTI_RUN_ON_START: "${CTI_RUN_ON_START:-true}"
      CTI_LOOKBACK_DAYS: "${CTI_LOOKBACK_DAYS:-7}"
      CTI_SMTP_HOST: "${CTI_SMTP_HOST:-}"
      CTI_SMTP_PORT: "${CTI_SMTP_PORT:-}"
      CTI_SMTP_SECURITY: "${CTI_SMTP_SECURITY:-ssl}"
      CTI_SMTP_USERNAME: "${CTI_SMTP_USERNAME:-}"
      CTI_SMTP_PASSWORD: "${CTI_SMTP_PASSWORD:-}"
      CTI_SMTP_FROM: "${CTI_SMTP_FROM:-}"
      CTI_SMTP_TO: "${CTI_SMTP_TO:-}"
      CTI_DB_PATH: /data/cti.db
    volumes:
      - ./data:/data
      - ./.cti-update/requests:/run/cti-update/requests
      - ./.cti-update/status:/run/cti-update/status:ro
    security_opt:
      - no-new-privileges:true
    cap_drop: [ALL]
    pids_limit: "${CTI_PIDS_LIMIT:-180}"
    mem_limit: 768m
    read_only: true
    tmpfs:
      - /tmp:size=64m,mode=1777
```

The application listens on **port 8791 inside the container**. Docker publishes it on **port 8791 of your NAS** by default. Set `WEB_PORT` in `.env` to choose a different NAS port.

> **Note:** The YAML uses `build: .`, not a pre-published Docker Hub image. The **Dockerfile and source code must be available to the build process**. Support for building from a local Compose project can vary with DSM/Container Manager versions; use the SSH fallback in Section 8 if Project creation cannot build the image.

## 7. Create the project using Synology Container Manager

1. Open **Container Manager → Project → Create**.
2. Enter a project name, for example: `cyber-intel-observatory`.
3. Set the project path to:

   ```text
   /volume1/docker/sentinel-cyber-intel-threat-observatory
   ```

4. Select the option to **use an existing `docker-compose.yml`**, or choose the corresponding YAML source option offered by your DSM version.
5. Review the displayed YAML; verify that it includes `build: .` and the `./data:/data` volume.
6. If you customized the defaults, confirm `.env` is in the same folder as the YAML. If Container Manager fails to resolve the `${...}` variables, use the SSH Compose method below.
7. Finish the project wizard and start/build the project.
8. In **Container Manager → Container**, look for **`cyber-intel-observatory`** and check its status and logs.

Expected state: the container is running, then its Docker health check reports healthy. Initial feed collection may continue after the web server starts.

## 8. SSH fallback: build and launch with Docker Compose

If the Container Manager interface fails to build the Dockerfile or the YAML variables are not resolved, open SSH and run:

```bash
cd /volume1/docker/sentinel-cyber-intel-threat-observatory
sudo docker compose config --quiet
sudo docker compose up -d --build
sudo docker compose ps
sudo docker compose logs --tail=100 cyber-intel-observatory
```

`config --quiet` checks the Compose configuration; `up -d --build` builds and runs it. Once the container starts, you can monitor it through Container Manager.

**Avoid starting a second copy with the same port while a Container Manager project is already running.** Manage the same Compose project in only one way at a time.

## 9. Open and test the dashboard

In a browser on your home or office LAN, visit:

```text
http://YOUR_NAS_IP:8791
```

Test the health endpoint:

```bash
curl -fsS http://127.0.0.1:8791/health
```

Expected output:

```json
{"status":"ok"}
```

If `BIND_IP` is set to the NAS's specific LAN IP, use `http://YOUR_NAS_IP:8791/health` instead of `127.0.0.1`.

In the dashboard, check:

1. **Home:** Summary counters and most recent findings.
2. **Cyberattacks, Vulnerabilities, Data Breaches, Ransomware, Technology:** Category filtering.
3. **History:** Open an incident to view details, sources and material updates.
4. **Intelligence sources:** Check each feed's success/error status and last synchronization.
5. **Sync feeds:** Run the collection manually and verify the updates appear.
6. **Theme toggle:** Check both light and dark modes.

The dashboard does not automatically import historical findings from earlier standalone HTML reports. Use the **Import history** feature only with a compatible JSON export. Older sample reports should be treated as **unverified** until checked against original sources.

## 10. Daily refresh and source coverage

By default, the service runs a collection at startup and then **daily at 08:00 (Europe/Zurich)** while it remains running.

Use **Collection settings** to set a recurring refresh interval of 1–1,440 minutes or 1–24 hours. Use **Sync feeds** for an immediate refresh. Manage public RSS and Atom feeds and research links in **Intelligence sources**. Disabled and removed feeds retain their archived records.

### Email digests

Set the following values in the NAS project's `.env` file using your mail provider's SMTP settings:

```dotenv
CTI_SMTP_HOST=smtp.example.com
CTI_SMTP_PORT=465
CTI_SMTP_SECURITY=ssl
CTI_SMTP_USERNAME=observatory@example.com
CTI_SMTP_PASSWORD='your SMTP password'
CTI_SMTP_FROM=observatory@example.com
CTI_SMTP_TO=alerts@example.com
```

Use `CTI_SMTP_SECURITY=starttls` with the port provided by your mail service, commonly `587`, if it requires STARTTLS. List multiple recipients in `CTI_SMTP_TO` separated by commas. Keep the SMTP settings in the NAS `.env` file.

Apply the configuration with `sudo docker compose --env-file .env up -d --build`. In **Collection settings**, click **Send test email** to check the SMTP configuration, then enable email digests if you want alerts. The app sends one digest per refresh that adds new findings or material updates. **Email draft** in a finding's details opens your own mail app for manual sharing.

The current version automatically processes selected public feeds, including CISA KEV, CERT-FR, SANS Internet Storm Center, watchTowr Labs, BleepingComputer, SecurityWeek, The Record and Krebs on Security. EPSS is used for best-effort enrichment. Other observatories may be linked as research resources rather than automatically ingested.

A feed returning an error **does not** mean that no threats exist. Review failures under **Intelligence sources**. Deduplication primarily uses canonical source URLs and CVEs; a material KEV change can update an existing finding.

## 11. Backup and update without losing history

The SQLite archive is kept in:

```text
/volume1/docker/sentinel-cyber-intel-threat-observatory/data/cti.db
```

To back up consistently, stop the app before copying its database files:

```bash
cd /volume1/docker/sentinel-cyber-intel-threat-observatory
sudo docker compose stop
sudo cp -a data "../cyber-intel-data-backup-$(date +%Y%m%d)"
sudo docker compose start
```

To update an SSH-cloned Git checkout after backing up:

```bash
cd /volume1/docker/sentinel-cyber-intel-threat-observatory
git pull --ff-only
sudo docker compose up -d --build
```

If you installed from a GitHub ZIP instead of `git clone`, download the new source ZIP and replace the **source files only**; preserve your existing `.env` and `data/` folder. Restart/rebuild through Container Manager (or Docker Compose SSH).

### Enable the App updates button

Install and start this version on the NAS once using the manual instructions above. In the NAS project folder, install the updater and give the running container permission to queue requests.

```sh
sudo cp scripts/cti-update.sh /usr/local/bin/cti-observatory-update
sudo chown root:root /usr/local/bin/cti-observatory-update
sudo chmod 755 /usr/local/bin/cti-observatory-update
sudo /usr/local/bin/cti-observatory-update init "$PWD"
```

In DSM, open **Control Panel → Task Scheduler → Create → Scheduled Task → User-defined script**. Select `root` and set the task to repeat throughout the day at the shortest interval available. Use this command in **Task Settings**, adjusting the project path if needed.

```sh
/usr/local/bin/cti-observatory-update run /volume1/docker/sentinel-cyber-intel-threat-observatory
```

Open **App updates → Update app** in the dashboard. The scheduled task deploys the latest commit on this project's GitHub `main` branch and reports its progress. The updater stages the release and builds it before replacing the running container. If the new container fails its health check, the task attempts to restore the previous image.

The updater works with manual ZIP and Git installations. It uses your existing `.env`, `data/` and `docker-compose.override.yml` if present. Put local Compose customizations in that override file so the updater can apply them to each new release. Keep the dashboard on your private network, since anyone who can open it can queue an update.

## 12. Troubleshooting

| Problem | Likely cause / action |
|---|---|
| `requirements.txt` is empty | Restore the four dependency lines listed in Section 3, then rebuild the image. |
| `failed to read Dockerfile` or `COPY app` failed | Check that `Dockerfile`, `requirements.txt`, `app/`, and YAML are all in the project root; verify Compose build context. |
| `permission denied` or `unable to open database file` | Check `data/` and any existing SQLite files are writable by the configured UID and GID (Section 5). |
| Port `8791` already allocated | Change `WEB_PORT` in `.env`, then recreate the project/container. |
| `PIDs limit discarded` | Docker could not enforce the container's process limit. Set `CTI_PIDS_LIMIT=-1` in `.env` and recreate the container. |
| Container exits or repeatedly restarts | Check **Container Manager → Container → Log**, or run `sudo docker compose logs --tail=200 cyber-intel-observatory`. |
| Intelligence feeds are empty or fail | Check NAS DNS/network access and the **Intelligence sources** status. The initial sync can take time. |
| No `git` on Synology | Use GitHub **Download ZIP** and File Station, or install Git separately. |
| `docker compose` unsupported in SSH | Check DSM Docker/Container Manager version, or deploy through Container Manager with a working local image/build mechanism. |

## 13. Security checklist for a public GitHub project

- [ ] Commit `Dockerfile`, `docker-compose.yml`, `requirements.txt`, `app/`, and documentation.
- [ ] **Never commit `.env`**, passwords, API keys, NAS addresses, certificates, SSH keys, `data/cti.db`, logs, or private exports.
- [ ] Keep the public repository separate from the running NAS data volume.
- [ ] Do not expose TCP/8791 directly to the Internet. Prefer Tailscale/VPN or an authenticated HTTPS reverse proxy for remote access.
- [ ] Review source links and validate reports: feed items are intelligence leads, not automatically verified breaches.
- [ ] Keep DSM and Container Manager updated; back up `data/` before upgrading.

---

## Add this guide to GitHub

Save this document in the repository root as **`SYNOLOGY_INSTALLATION.md`**, then commit and push it using GitHub Desktop (or upload it with GitHub's **Add file → Upload files** interface).

You can link it from `README.md` with:

```markdown
[Synology DSM 7 installation guide](SYNOLOGY_INSTALLATION.md)
```
