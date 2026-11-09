# Deploy Cyber Intel — Threat Observatory on Synology DSM 7

This guide assumes the public GitHub repository `Kibo28/sentinel-cyber-intel-threat-observatory`, Synology Container Manager, SSH access, and a working Docker Compose v2 installation.

## A. Publish your source through GitHub Desktop (Mac)

1. Find the local repository in GitHub Desktop → **Repository** → **Show in Finder**.
2. Unzip the GitHub-ready archive. **Copy everything inside it**, including hidden `.github`, `.gitignore`, `.dockerignore`, and `.env.example`, into the existing local repository folder. **Do not copy a new `.git` folder or another parent folder**.
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

4. Create the local environment file:

   ```bash
   cp .env.example .env
   ```

   Configure [access to the persistent data folder](SYNOLOGY_INSTALLATION.md#5-create-the-persistent-data-folder-and-permissions) for your NAS account or the default container account.

5. Edit `.env` using an editor (`vi .env` or via File Station). Before editing locally on a Mac, avoid copying `.env` into your GitHub working tree. At minimum, change `CTI_PASSWORD` to a fresh password of 20+ characters. Generate a safe alphanumeric value on your Mac with `openssl rand -hex 24`; **never commit or paste the value into GitHub**.

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

Open: `http://YOUR_NAS_IP:8791`. Your browser will ask for the `CTI_USERNAME` and `CTI_PASSWORD` from `.env`.

From the NAS, check the unauthenticated health endpoint:

```bash
curl -fsS http://127.0.0.1:8791/health
```

If you configured `BIND_IP` to your LAN address (rather than `0.0.0.0`), use `http://YOUR_NAS_IP:8791/health` instead.

**Expected:** `{"status":"ok"}`. In the browser, go to **Intelligence sources** and review successful or failed feeds. Press **Sync feeds** to request an immediate refresh.

## D. Troubleshooting

- **Image build fails:** capture `sudo docker compose build --no-cache` output; verify Internet/DNS access for Docker package downloads.
- **Container exits.** Run `sudo docker compose logs --tail=200 cyber-intel-observatory` and check that `.env` has a password of at least 20 characters.
- **Port busy:** update `WEB_PORT` in `.env`, then `sudo docker compose up -d --force-recreate`.
- **SQLite permission denied.** Check that the [configured container account](SYNOLOGY_INSTALLATION.md#5-create-the-persistent-data-folder-and-permissions) can write to `data/` and any existing database files.
- **Browser login prompt repeats:** confirm `.env` username/password and restart the container. Clear saved Basic-auth credentials using a private browser window.
- **Sources fail:** check proxy/DNS and the source-status table. Source failures are not equivalent to zero incidents.

## E. Updates and backups

```bash
cd /volume1/docker/sentinel-cyber-intel-threat-observatory
sudo docker compose stop
sudo cp -a data "../cti-observatory-backup-$(date +%Y%m%d)"
git pull --ff-only
sudo docker compose up -d --build
```

Never commit `.env` or `data/`. The GitHub repository is **public**, but the running dashboard should remain **private**. Do not forward port `8791` on your router; use a VPN such as Tailscale or an authenticated HTTPS reverse proxy for remote access. Basic authentication over HTTP is not encrypted.
