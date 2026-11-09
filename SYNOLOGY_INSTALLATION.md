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

> **Security:** The *GitHub source repository* can be public; your **NAS dashboard, `.env` file, and database should remain private**. Do not forward TCP port 8791 on your router. This MVP uses HTTP Basic authentication, so avoid accessing it over unencrypted networks.

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
   ├── .env.example
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

## 4. Configure your private `.env` file

Create a file named **`.env`** beside `docker-compose.yml`. The easiest way, if SSH is enabled, is:

```bash
cd /volume1/docker/sentinel-cyber-intel-threat-observatory
cp .env.example .env
```

Alternatively, download `.env.example` to your Mac, rename the copy to `.env`, edit it, and upload it to the project folder in File Station. Hidden files beginning with `.` may not be visible unless hidden-file display is enabled.

Set values similar to the following (**replace the password**):

```dotenv
# Browser access
WEB_PORT=8791
BIND_IP=0.0.0.0

# Dashboard login — use a unique random password (minimum 20 characters)
CTI_USERNAME=admin
CTI_PASSWORD=REPLACE_WITH_A_UNIQUE_RANDOM_PASSWORD_AT_LEAST_20_CHARS

# Feed refresh — local Switzerland time
CTI_SYNC_HOUR=8
CTI_SYNC_MINUTE=0
CTI_RUN_ON_START=true
CTI_LOOKBACK_DAYS=7
```

- `WEB_PORT`: external NAS port. Change it if **8791** is already used by another service.
- `BIND_IP`: `0.0.0.0` listens on all NAS network interfaces; setting your actual NAS LAN IP limits binding to that address. Neither option adds encryption or replaces firewall rules.
- `CTI_USERNAME` / `CTI_PASSWORD`: HTTP Basic login credentials. The application **refuses to start** if the password is shorter than 20 characters or still contains the placeholder.
- `CTI_SYNC_HOUR=8` / `CTI_SYNC_MINUTE=0`: daily refresh at **08:00 Europe/Zurich**; daylight-saving changes are handled by the application.
- `CTI_RUN_ON_START=true`: attempt a first feed collection shortly after startup.

To generate a password on a Mac or SSH shell:

```bash
openssl rand -hex 24
```

**Never commit `.env` to GitHub**, paste the password into an issue, or store it in the public README. The repository should contain `.env.example` only.

## 5. Create the persistent data folder and permissions

The application runs inside the container as a non-root user with **UID 10001**. That user must be able to write to the mapped `data/` folder.

Open an SSH session to your NAS (if necessary, enable SSH temporarily in **Control Panel → Terminal & SNMP**):

```bash
ssh YOUR_SYNOLOGY_USER@YOUR_NAS_IP
```

Then run:

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
    ports:
      - "${BIND_IP:-0.0.0.0}:${WEB_PORT:-8791}:8080"
    environment:
      CTI_USERNAME: "${CTI_USERNAME:?Set CTI_USERNAME in .env}"
      CTI_PASSWORD: "${CTI_PASSWORD:?Set CTI_PASSWORD in .env}"
      CTI_TIMEZONE: "Europe/Zurich"
      CTI_SYNC_HOUR: "${CTI_SYNC_HOUR:-8}"
      CTI_SYNC_MINUTE: "${CTI_SYNC_MINUTE:-0}"
      CTI_RUN_ON_START: "${CTI_RUN_ON_START:-true}"
      CTI_LOOKBACK_DAYS: "${CTI_LOOKBACK_DAYS:-7}"
      CTI_DB_PATH: /data/cti.db
    volumes:
      - ./data:/data
    security_opt:
      - no-new-privileges:true
    cap_drop: [ALL]
    pids_limit: 180
    mem_limit: 768m
    read_only: true
    tmpfs:
      - /tmp:size=64m,mode=1777
```

The application listens on **port 8080 inside the container** and is published on **port 8791 of your NAS**. Do not change the internal port unless you also modify the application's Docker startup command.

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
6. Confirm `.env` is in the same folder as the YAML. If Container Manager does not resolve the `${...}` variables, use the SSH Compose method below rather than pasting your password directly into a public YAML file.
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

You should receive a sign-in prompt. Use `CTI_USERNAME` and `CTI_PASSWORD` from your private `.env`.

Test the health endpoint:

```bash
curl -fsS http://127.0.0.1:8791/health
```

Expected output:

```json
{"status":"ok"}
```

If `BIND_IP` is set to the NAS's specific LAN IP, use `http://YOUR_NAS_IP:8791/health` instead of `127.0.0.1`.

After login, check:

1. **Home:** Summary counters and most recent findings.
2. **Cyberattacks, Vulnerabilities, Data Breaches, Ransomware, Technology:** Category filtering.
3. **History:** Open an incident to view details, sources and material updates.
4. **Intelligence sources:** Check each feed's success/error status and last synchronization.
5. **Sync feeds:** Run the collection manually and verify the updates appear.
6. **Theme toggle:** Check both light and dark modes.

The dashboard does not automatically import historical findings from earlier standalone HTML reports. Use the **Import history** feature only with a compatible JSON export. Older sample reports should be treated as **unverified** until checked against original sources.

## 10. Daily refresh and source coverage

By default, the service runs a collection at startup and then **daily at 08:00 (Europe/Zurich)** while it remains running.

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

## 12. Troubleshooting

| Problem | Likely cause / action |
|---|---|
| `requirements.txt` is empty | Restore the four dependency lines listed in Section 3, then rebuild the image. |
| `CTI_PASSWORD` missing, placeholder, or too short | Set a unique 20+-character password in `.env`; recreate the container. |
| `failed to read Dockerfile` or `COPY app` failed | Check that `Dockerfile`, `requirements.txt`, `app/`, and YAML are all in the project root; verify Compose build context. |
| `permission denied` or `unable to open database file` | Check `data/` exists and is writable by UID `10001` (Section 5). |
| Port `8791` already allocated | Change `WEB_PORT` in `.env`, then recreate the project/container. |
| Container exits or repeatedly restarts | Check **Container Manager → Container → Log**, or run `sudo docker compose logs --tail=200 cyber-intel-observatory`. |
| Dashboard asks repeatedly for credentials | Confirm `.env` values, then recreate; try a private browser window to avoid cached HTTP Basic credentials. |
| Intelligence feeds are empty or fail | Check NAS DNS/network access and the **Intelligence sources** status. The initial sync can take time. |
| No `git` on Synology | Use GitHub **Download ZIP** and File Station, or install Git separately. |
| `docker compose` unsupported in SSH | Check DSM Docker/Container Manager version, or deploy through Container Manager with a working local image/build mechanism. |

## 13. Security checklist for a public GitHub project

- [ ] Commit `Dockerfile`, `docker-compose.yml`, `requirements.txt`, `app/`, `.env.example`, and documentation.
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
