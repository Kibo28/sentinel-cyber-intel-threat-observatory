# Install Cyber Intel — Threat Observatory on Synology DSM 7

This guide covers Synology DS723+ and compatible NAS devices running DSM 7 with **Container Manager**. The image builds locally with Docker Compose and stores the archive in `data/cti.db`.

This guide uses **Synology Container Manager → Project** and the application's existing YAML file. SSH commands cover steps that may need elevated permissions and provide a fallback for building the image. For an existing deployment, see [Update Cyber Intel on Synology](docs/UPDATING.md). For a fresh SSH installation using Git, see [Deploy from Git](SYNOLOGY_DEPLOYMENT.md).

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

3. Upload and extract the ZIP. Move the extracted contents into the project folder so `docker-compose.yml` is at the project root.
4. Check that the files are arranged as follows:

   ```text
   /volume1/docker/sentinel-cyber-intel-threat-observatory/
   ├── app/
   ├── data/
   ├── docs/
   ├── scripts/
   ├── tests/
   ├── Dockerfile
   ├── docker-compose.yml
   ├── requirements.txt
   └── README.md
   ```

   Include the hidden `.dockerignore` file when moving the source files.

**Important:** `Dockerfile`, `docker-compose.yml`, `requirements.txt`, and the `app/` directory must be in the **same project root**. `build: .` in the YAML refers to this directory.

## 3. Verify `requirements.txt`

Use the `requirements.txt` from the same checkout or ZIP as the application. The Dockerfile installs the dependencies listed there during the image build.

## 4. Override the Compose defaults

To customize settings, create **`.env`** beside `docker-compose.yml`:

```bash
cd /volume1/docker/sentinel-cyber-intel-threat-observatory
vi .env
```

Set the values you want to override. Omitted values use the defaults shown here.

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

- `WEB_PORT` sets the NAS port. Change it if another service uses **8791**.
- `BIND_IP` defaults to `0.0.0.0`, which listens on all NAS network interfaces. Set it to your NAS LAN IP to bind to that address.
- `CTI_SYNC_HOUR=8` and `CTI_SYNC_MINUTE=0` schedule the daily refresh for **08:00 Europe/Zurich**.
- `CTI_RUN_ON_START=true` starts a feed collection each time the app starts.
- `CTI_LOOKBACK_DAYS=7` is the lookback for dated feed items and CISA KEV additions (1–60 days). The lookback applies to collection, and older records stay in the archive.

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

For an existing installation, make sure the selected account can write to the database and its containing folder before recreating the container. Use the [existing project name and data mount](docs/UPDATING.md#identify-the-running-project) for changes to a deployed service. If you use dashboard updates, rerun [updater initialization](docs/UPDATING.md#set-up-the-nas-updater-once) after the container starts with the new IDs.

With both settings omitted, the container uses the image's `cti` account (UID **10001**). For that setup, prepare the data folder as follows:

```bash
cd /volume1/docker/sentinel-cyber-intel-threat-observatory
sudo mkdir -p data
sudo chown -R 10001:10001 data
sudo chmod 750 data
```

**Do not change permissions on `/volume1/docker` as a whole**; it may contain unrelated running services. Change only this application's `data/` directory.

## 6. Check the Docker Compose YAML

Use the repository's [`docker-compose.yml`](docker-compose.yml). It builds the image locally from the project root and mounts `./data` at `/data`. The application listens on port `8791` inside the container. Set `WEB_PORT` in `.env` if you need a different port on the NAS.

For deployments that need Compose customizations beyond `.env`, use a local `docker-compose.override.yml`. The NAS updater uses that file with the downloaded build.

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
sudo docker compose config --quiet &&
  sudo docker compose up -d --build &&
  sudo docker compose ps
```

`config --quiet` checks the Compose configuration; `up -d --build` builds and runs it. Once the container starts, you can monitor it through Container Manager.

If Container Manager already created a project, use its existing name with `sudo docker compose -p YOUR_PROJECT_NAME ...`. [Find the project name and folder](docs/UPDATING.md#identify-the-running-project).

## 9. Open and test the dashboard

Open the dashboard in a browser on your private network. Substitute the port from `WEB_PORT` if you changed it.

```text
http://YOUR_NAS_IP:8791
```

At the same address and port, open `/health` and check for `{"status":"ok"}`. From SSH on the NAS, check with `curl -fsS http://YOUR_NAS_IP:8791/health`, using the configured bind address and port.

In the dashboard, open **Intelligence sources** to check collection status. The initial refresh may still be running when the dashboard first opens. Use **Sync feeds** to request an immediate refresh. In **History archive**, select **View details** to see a finding's sources and timeline.

## 10. Daily refresh and source coverage

By default, the service runs a collection at startup and then **daily at 08:00 (Europe/Zurich)** while it remains running.

Use **Collection settings** to choose a daily time set in `.env` or a recurring interval of 1–1,440 minutes. See the [default sources](README.md#what-the-dashboard-collects) and [dashboard controls](README.md#use-the-dashboard).

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

Apply the settings from the deployed project folder with `sudo docker compose up -d`, using `-p YOUR_PROJECT_NAME` if you set a custom project name. If the running build was installed through **App updates**, [update and rebuild the local source](docs/UPDATING.md#update-manually) to apply the settings with current code. In **Collection settings**, select **Send test email**, then enable **Email new findings and material updates**. The app sends a digest when a refresh adds findings or material updates.

## 11. Backup and update without losing history

Follow the [update guide](docs/UPDATING.md) to identify the running project, [back up the archive and configuration](docs/UPDATING.md#back-up), or [restore from backup](docs/UPDATING.md#restore).

### Enable the App updates button

Follow the [one-time NAS updater setup](docs/UPDATING.md#set-up-the-nas-updater-once).

## 12. Troubleshooting

| Problem | Likely cause / action |
|---|---|
| `requirements.txt` is empty | Use the file from the matching ZIP or Git revision, then rebuild the image. |
| `failed to read Dockerfile` or `COPY app` failed | Check that `Dockerfile`, `requirements.txt`, `app/`, and YAML are all in the project root; verify Compose build context. |
| `permission denied` or `unable to open database file` | Check `data/` and any existing SQLite files are writable by the configured UID and GID (Section 5). |
| Port `8791` already allocated | Change `WEB_PORT` in `.env`, then recreate the project/container. |
| `PIDs limit discarded` | Docker could not enforce the container's process limit. Set `CTI_PIDS_LIMIT=-1` in `.env` and recreate the container. |
| Container exits or repeatedly restarts | Check **Container Manager → Container → Log**, or run `sudo docker logs --tail=200 cyber-intel-observatory`. |
| Intelligence feeds are empty or fail | Check NAS DNS/network access and the **Intelligence sources** status. The initial sync can take time. |
| No `git` on Synology | Use GitHub **Download ZIP** and File Station, or install Git separately. |
| `docker compose` unsupported in SSH | Check DSM Docker/Container Manager version, or deploy through Container Manager with a working local image/build mechanism. |
