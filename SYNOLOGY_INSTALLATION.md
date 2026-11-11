# Install Cyber Intel — Threat Observatory on Synology DSM 7

Use Container Manager on a compatible Synology NAS such as the DS723+. The project builds an image locally and stores the SQLite archive in `data/cti.db` on the NAS. If you prefer the command line, follow the [SSH deployment quickstart](SYNOLOGY_DEPLOYMENT.md).

## 1. Prerequisites

- Container Manager, access to File Station, and permission to create a project and prepare its data directory.
- An available host port (default: `8791`) and network access from the NAS to download the base image, install Python dependencies, and fetch public feeds.
- SSH access for shell commands in this guide. Enable it in **Control Panel → Terminal & SNMP** if needed, and disable it afterward if you no longer use it.

**Network access:** The dashboard has no login. Anyone who can reach it can read or export records and use the dashboard's management controls. The default Compose configuration publishes the port on all host interfaces. Restrict access with your NAS firewall or private network, and use a private VPN or an authenticated HTTPS reverse proxy for remote access.

## 2. Download the application to Synology

1. In the [GitHub repository](https://github.com/Kibo28/sentinel-cyber-intel-threat-observatory), select **Code → Download ZIP**.
2. In File Station, create `/volume1/docker/sentinel-cyber-intel-threat-observatory/`, or choose another project folder.
3. Upload and extract the ZIP, then move the extracted contents directly into the project folder. The folder that contains `docker-compose.yml` is the project root.

If you use `git clone` instead, follow the [SSH quickstart](SYNOLOGY_DEPLOYMENT.md) and use the cloned directory as the project root.

## 3. Check the project files

Keep `docker-compose.yml`, `Dockerfile`, `requirements.txt`, and `app/` together in the project root. The Compose file uses `build: .`, and the Dockerfile installs the Python dependencies from [`requirements.txt`](requirements.txt). Use the versions in the checkout you are deploying.

## 4. Override the Compose defaults

Create `.env` next to `docker-compose.yml` only if you need to change a default or configure SMTP. Use your NAS LAN address for `BIND_IP` if you want to publish on that interface only.

```dotenv
# Replace this example address with your NAS LAN address.
BIND_IP=192.0.2.10
WEB_PORT=8791
```

| Setting | Default | Effect |
| --- | --- | --- |
| `BIND_IP` | `0.0.0.0` | Address on the NAS where Docker publishes the port. A specific address limits the bind; enforce access separately. |
| `WEB_PORT` | `8791` | Browser-facing port. The container still listens on `8791`. |
| `CTI_UID` / `CTI_GID` | `cti` / `cti` | Container identity. See [data permissions](#5-create-the-persistent-data-folder-and-permissions). |
| `CTI_SYNC_HOUR` / `CTI_SYNC_MINUTE` | `8` / `0` | Daily collection time in Europe/Zurich, including daylight saving time. Used when **Collection settings** is set to daily. |
| `CTI_RUN_ON_START` | `true` | Queue a refresh each time the app starts. Set to `false` to skip it. |
| `CTI_LOOKBACK_DAYS` | `7` | Collection window for dated RSS/Atom entries and CISA KEV additions. The app clamps it to 1–60 days. Existing records are retained. |
| `CTI_PIDS_LIMIT` | `180` | Container process limit. |
| `CTI_SMTP_*` | See [Email digests](#email-digests) | Optional mail server and recipient settings. |

Use a local `docker-compose.override.yml` for Compose changes beyond these variables. For example, `CTI_TIMEZONE` is set in the service environment and is not read from `.env`. Keep both local files on the NAS. After a configuration change, recreate the container using the same project. If you previously updated from the dashboard, [update the local source first](#update-manually) so a manual rebuild uses the intended version.

## 5. Create the persistent data folder and permissions

From an SSH session, go to the project root:

```bash
cd /volume1/docker/sentinel-cyber-intel-threat-observatory
```

With `CTI_UID` and `CTI_GID` omitted, Compose runs as the image's `cti` user (UID and GID 10001). To use that account:

```bash
sudo mkdir -p data
sudo chown -R 10001:10001 data
sudo chmod 750 data
```

Alternatively, set `CTI_UID` and `CTI_GID` in `.env` using the output of `id -u` and `id -g` from a non-root NAS account. The chosen identity needs write access to the directory and any existing SQLite files. Scope ownership or permission changes to this project's `data/` directory.

For a running installation, stop the app before changing database ownership. Recreate the container afterward so it uses the new identity. If the dashboard updater was enabled, [rerun its `init` command](#enable-the-app-updates-button) after recreation to update the request directory permissions.

## 6. Check the Docker Compose YAML

Use the supplied [`docker-compose.yml`](docker-compose.yml). It builds from the local project, mounts `./data` at `/data`, and uses `/data/cti.db`. It runs the app without root privileges by default, drops Linux capabilities, and makes the container root filesystem read-only. The data and updater request mounts are writable; the updater status mount is read-only.

## 7. Create the project using Synology Container Manager

1. Open **Container Manager → Project → Create**.
2. Enter a project name, such as `cyber-intel-observatory`, and select the folder containing `docker-compose.yml`.
3. Choose the option to use or upload the supplied Compose YAML file. Check that it uses `build: .` and mounts `./data:/data`.
4. Start the project. In **Container Manager → Container**, check that `cyber-intel-observatory` is running and becomes healthy.

See [Synology's Container Manager instructions](https://kb.synology.com/en-eu/insights/Use_Container_Manager_to_run_web_app) for the wizard. If the project cannot build the local Dockerfile or resolve values from `.env`, use the SSH fallback.

## 8. SSH fallback: build and launch with Docker Compose

From the project root:

```bash
sudo docker compose config --quiet
sudo docker compose up -d --build
sudo docker compose ps
sudo docker compose logs --tail=100 cyber-intel-observatory
```

Manage the same Compose project throughout. If you specified a project name that differs from the directory name in Container Manager, pass `-p YOUR_PROJECT_NAME` after `docker compose` when managing it over SSH.

## 9. Open and test the dashboard

Open `http://YOUR_NAS_IP:8791` from a browser on your private network. Substitute the value of `WEB_PORT` if you changed it. From the NAS, you can check whether the service responds:

```bash
curl -fsS http://127.0.0.1:8791/health
```

Expected response: `{"status":"ok"}`. If `BIND_IP` is set to the NAS LAN address, use that address instead of `127.0.0.1`. Use the configured host port here as well.

The health endpoint checks that the app responds over HTTP. To verify collection, open **Intelligence sources** and look at the results after the startup refresh or click **Sync feeds**. **Pending** means no check result is recorded for that feed; **Fetch error** means it could not be checked. Once records are available, open **History archive → View details** to verify source links and history.

## 10. Daily refresh and source coverage

By default the app refreshes at startup and daily at 08:00 Europe/Zurich while running. The daily schedule does not catch up on a missed run while the service was off. An interval selected in **Collection settings** takes precedence over the daily schedule and is saved in SQLite. **Sync feeds** queues a refresh without changing the schedule. Only one refresh runs at a time.

Use **Intelligence sources** to add public RSS/Atom feeds or research links and to enable or disable CISA KEV and FIRST EPSS. Custom feeds must use a public HTTP(S) address and a standard port, without embedded credentials. Private and internal feeds are unsupported. Changes apply on the next refresh; disabling or removing a source leaves its existing records in the archive. See [collection and interpretation](README.md#collection-and-interpretation) for the default source list.

### Email digests

Add your mail provider's settings to the NAS project's `.env`:

```dotenv
CTI_SMTP_HOST=smtp.example.com
CTI_SMTP_SECURITY=ssl
CTI_SMTP_PORT=465
CTI_SMTP_USERNAME=observatory@example.com
CTI_SMTP_PASSWORD='your SMTP password'
CTI_SMTP_FROM=observatory@example.com
CTI_SMTP_TO=alerts@example.com
```

Host, sender, and recipient are required. Add credentials if the mail server requires authentication. For STARTTLS, set `CTI_SMTP_SECURITY=starttls`. If the port is omitted, the app uses 465 for `ssl` or 587 for `starttls`. Separate multiple recipients with commas.

From the project root, run `sudo docker compose up -d` to apply the updated environment. In **Collection settings**, click **Send test email** and check the recipients' inboxes. This works before digests are enabled. To receive alerts, turn on **Email new findings and material updates** and save. The app sends one digest after each refresh with new records or material updates. It lists up to ten findings and reports the total counts.

## 11. Backup and update without losing history

### Back up

The database stores records, source links, timelines, source and collection settings, favorites, and tags. Wait for any queued app update to finish, then stop the app before copying the complete `data/` directory, which may also contain SQLite's `-wal` and `-shm` files. Run this from the project root, replacing `../cti-backup.XXXXXX` with a path template in a private, writable location if needed:

```bash
backup_dir=$(mktemp -d ../cti-backup.XXXXXX) &&
  sudo docker compose stop &&
  sudo cp -a data "$backup_dir/data" &&
  sudo docker compose start
```

If copying fails, check the error and use `sudo docker compose start` to bring the app back up. Keep the backup in a private location and back up `.env` and `docker-compose.override.yml` separately if you use them. `.env` may contain SMTP credentials. [History exports](README.md#import-export-and-backup) are useful for analysis; use the database copy for recovery.

### Restore

1. Stop the Compose project. Move the current `data/` directory to a separate recovery location so you can keep it if the restore fails.
2. Copy the backup's entire `data/` directory into the project root. Restore the saved `.env` and Compose override as needed.
3. Verify that the [configured container identity](#5-create-the-persistent-data-folder-and-permissions) can write to the restored directory and database. If the deployment configuration is unchanged, run `sudo docker compose start`. If the configuration changed or you are restoring to a new installation, rebuild and start the project from the intended source version.
4. Check **History archive**, **Favorites**, and **Collection settings**. Keep the old data until you confirm the restore.

### Update manually

Follow the [manual update steps for Git or ZIP installations](docs/UPDATING.md#update-manually).

### Enable the App updates button

Follow the [one-time NAS setup](docs/UPDATING.md#set-up-the-nas-updater-once), then [run updates from the dashboard](docs/UPDATING.md#run-an-update-from-the-dashboard).

## 12. Troubleshooting

| Problem | Check |
| --- | --- |
| Build cannot find `Dockerfile`, `requirements.txt`, or `app/` | Make sure all are next to `docker-compose.yml` at the project root. Check build output and NAS network access if dependency downloads fail. |
| `unable to open database file` or `permission denied` | Check write access to `data/` and existing SQLite files for the [container UID and GID](#5-create-the-persistent-data-folder-and-permissions). |
| Port already allocated | Set an unused `WEB_PORT` in `.env` and recreate the same project. Use that port in the URL and health check. |
| Container exits or restarts | Check **Container Manager → Container → Log** or run `sudo docker compose logs --tail=200 cyber-intel-observatory`. |
| `PIDs limit discarded` | If the NAS cannot enforce the process limit, set `CTI_PIDS_LIMIT=-1` to remove it, then recreate the container. |
| Feed is empty or failing | Check the last status and error in **Intelligence sources**. Verify NAS DNS and network access. An OK result with zero eligible entries can occur when nothing matched the lookback and filters. |
| Test email fails | Check the reported SMTP error, host, port, security mode, credentials, recipients, and the mail server logs. An SMTP acceptance response is not proof of inbox delivery. |
| App updates says setup is required | Start the current project, run the updater's `init` command from its actual project directory, and check the Compose version and mounts. |

Before publishing repository changes, see the [public repository release checklist](PUBLIC_REPOSITORY_CHECKLIST.md).
