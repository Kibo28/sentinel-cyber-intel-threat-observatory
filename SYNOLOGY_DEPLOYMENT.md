# Deploy Cyber Intel — Threat Observatory on Synology DSM 7

This guide assumes the public GitHub repository `Kibo28/sentinel-cyber-intel-threat-observatory`, Synology Container Manager, SSH access, and a working Docker Compose v2 installation.

## A. Publish your source through GitHub Desktop (Mac)

1. Find the local repository in GitHub Desktop → **Repository** → **Show in Finder**.
2. Unzip the GitHub-ready archive. **Copy its contents** into the existing local repository folder.
3. In GitHub Desktop → **Changes**, review the files; verify there is **no `.env`, `.db`, private key, token, passwords, or personal backup**.
4. Enter summary `Initial public release: Cyber Intel Threat Observatory`, click **Commit to main**, then **Push origin**.
5. Open `https://github.com/Kibo28/sentinel-cyber-intel-threat-observatory` and verify the project files are at the root.

## B. Clone and configure on Synology

1. Make sure **Container Manager** is installed. Enable **Control Panel → Terminal & SNMP → SSH** temporarily (disable again if not needed). From Mac Terminal:

   ```bash
   ssh YOUR_SYNOLOGY_USER@YOUR_NAS_IP
   ```

2. On the NAS, check availability of Docker and Compose:

   ```bash
   docker version
   docker compose version
   ```

3. Clone the public repository into your existing `/volume1/docker` shared folder:

   ```bash
   cd /volume1/docker
   git clone https://github.com/Kibo28/sentinel-cyber-intel-threat-observatory.git
   cd sentinel-cyber-intel-threat-observatory
   ```

   If `git` is not installed on DSM, use Download ZIP from GitHub and extract it using File Station instead. **Do not run the `chown` for `/volume1/docker` if it contains folders managed by other services**; use a user-writable subfolder or perform the clone with appropriate permissions.

4. Configure [access to the persistent data folder](SYNOLOGY_INSTALLATION.md#5-create-the-persistent-data-folder-and-permissions) for your NAS account or the default container account.

5. To override the Compose defaults, create `.env` beside `docker-compose.yml` using an editor or File Station.

   - `WEB_PORT=8791` — change if occupied.
   - `BIND_IP=YOUR_NAS_LAN_IP` — preferable to `0.0.0.0` if you want to bind only to the LAN address.
   - `CTI_SYNC_HOUR=8` — daily 08:00 Europe/Zurich time.

## C. Build and test

Run from the repository folder:

```bash
sudo docker compose config --quiet
sudo docker compose up -d --build
sudo docker compose ps
sudo docker compose logs --tail=100 cyber-intel-observatory
```

Open `http://YOUR_NAS_IP:8791` from a browser on your private network.

From the NAS, check the health endpoint:

```bash
curl -fsS http://127.0.0.1:8791/health
```

If you configured `BIND_IP` to your LAN address (rather than `0.0.0.0`), use `http://YOUR_NAS_IP:8791/health` instead.

**Expected:** `{"status":"ok"}`. In the browser, go to **Intelligence sources** and review successful or failed feeds. Press **Sync feeds** to request an immediate refresh.

## D. Troubleshooting

- **Image build fails:** capture `sudo docker compose build --no-cache` output; verify Internet/DNS access for Docker package downloads.
- **Container exits.** Run `sudo docker compose logs --tail=200 cyber-intel-observatory` to check the startup error.
- **Port busy:** update `WEB_PORT` in `.env`, then `sudo docker compose up -d --force-recreate`.
- **SQLite permission denied.** Check that the [configured container account](SYNOLOGY_INSTALLATION.md#5-create-the-persistent-data-folder-and-permissions) can write to `data/` and any existing database files.
- **Sources fail:** check proxy/DNS and the source-status table. Source failures are not equivalent to zero incidents.

## E. Updates and backups

```bash
cd /volume1/docker/sentinel-cyber-intel-threat-observatory
sudo docker compose stop
sudo cp -a data "../cti-observatory-backup-$(date +%Y%m%d)"
git pull --ff-only
sudo docker compose up -d --build
```

Keep `.env` and `data/` local. Anyone who can reach the dashboard can access its archive and API. Keep port `8791` on your private network and use a private VPN or an authenticated HTTPS reverse proxy for remote access.
