# Update Cyber Intel on Synology

Use **App updates** to install a new dashboard build. Use **Sync feeds** to collect new findings.

| Your installation | Update method |
| --- | --- |
| **App updates → Update app** is enabled | [Update from the dashboard](#update-from-the-dashboard). |
| **App updates** asks you to set up the NAS updater | [Set up the NAS updater once](#set-up-the-nas-updater-once). |
| The dashboard has no **App updates** menu, Compose lacks `--wait-timeout`, or you want to deploy a fork or a specific revision | [Update manually](#update-manually). |

## Identify the running project

Open SSH on the NAS. Inspect the existing container before changing anything.

```sh
sudo docker inspect --format 'Folder={{index .Config.Labels "com.docker.compose.project.working_dir"}}
Project={{index .Config.Labels "com.docker.compose.project"}}
Image={{.Config.Image}}
{{range .Mounts}}{{if eq .Destination "/data"}}Data mount={{.Type}} {{.Source}}{{end}}{{end}}' cyber-intel-observatory
```

Enter the **Folder** from that output. Set `CTI_PROJECT` to the **Project** value, which may be a custom Container Manager project name. Set `CTI_DATA_DIR` to the host path after `Data mount=bind`. The commands below use these example values. Keep the same SSH session or set them again when you reconnect.

```sh
cd /volume1/docker/sentinel-cyber-intel-threat-observatory
CTI_PROJECT=sentinel-cyber-intel-threat-observatory
CTI_DATA_DIR="$PWD/data"
```

For a custom bind mount, set `CTI_DATA_DIR` to its actual path and make sure `docker-compose.override.yml` maps that path to `/data`. For a Docker-managed volume, back up and restore the volume using your deployment's volume tooling. Record the original data mount so you can compare it after the update.

## Back up

1. Wait for any queued or running app update to finish. Keep **App updates** idle until the backup is complete.
2. Create a private backup directory beside the project and save the local Compose configuration. Record the printed path. If any command fails, resolve the error before stopping the container.

   ```sh
   CTI_BACKUP=$(sudo mktemp -d "$PWD/../cyber-intel-backup.XXXXXX") &&
     printf '%s\n' "$CTI_BACKUP" &&
     sudo mkdir "$CTI_BACKUP/config" &&
     (
       set -e
       sudo cp -a docker-compose.yml "$CTI_BACKUP/config/"
       for file in .env docker-compose.override.yml; do
           if [ -f "$file" ]; then
               sudo cp -a "$file" "$CTI_BACKUP/config/"
           fi
       done
     )
   ```

3. Stop the existing container so SQLite can close, then copy the full data folder. Confirm the copy succeeds and includes `cti.db`.

   ```sh
   sudo docker stop cyber-intel-observatory &&
     sudo cp -a "$CTI_DATA_DIR" "$CTI_BACKUP/data" &&
     sudo test -s "$CTI_BACKUP/data/cti.db"
   ```

4. Start the existing container again, even if the copy failed. Resolve any backup error before updating.

   ```sh
   sudo docker start cyber-intel-observatory
   ```

The database holds the archive, favorites, tags, saved sources, and collection settings. The local configuration can contain SMTP credentials. Keep the backup private. Use [History archive exports](../README.md#archive-exports-and-imports) for sharing findings and this backup for recovery.

## Update from the dashboard

1. [Identify the running project](#identify-the-running-project) and [back it up](#back-up).
2. In the dashboard sidebar, open **App updates** and select **Update app**. **Update queued** means the NAS has a request to process.
3. Wait for the next scheduled run, or start it now in DSM under **Control Panel → Task Scheduler**. Select **Cyber Intel App Updates** (or the name you chose) and click **Run**.
4. Leave the update dialog open. The task downloads the latest commit on this repository's GitHub `main` branch, builds it, replaces the container, and waits for its health check. The dialog may show **Waiting to reconnect** during the restart and polls automatically.
5. When you see **Update complete**, select **Reload dashboard**. If the message is **The dashboard is already on the latest version**, continue to [verify the update](#verify-the-update).

The updater builds from a separate download in `.cti-update/` and uses the project folder's data mount, `.env`, and optional `docker-compose.override.yml`. Update your local source files before a later manual rebuild. Rebuilding from an older ZIP or checkout can bring back that older build.

## Set up the NAS updater once

1. Start the app from its final project folder. If the running build has no **App updates** menu or the project has no `scripts/cti-update.sh`, follow the [manual update procedure](#update-manually) first. The NAS needs outbound access to GitHub and the image build dependencies.
2. On the NAS, check whether Compose offers the required option. If the command prints no match, use the manual procedure or upgrade Container Manager. [Docker Compose options](https://docs.docker.com/reference/cli/docker/compose/up/)

   ```sh
   sudo docker compose up --help | grep -F -- --wait-timeout
   ```

3. From the project folder on the NAS, install the host script and initialize the request and status folders. Initialization reads the Compose project name and the running container's UID and GID.

   ```sh
   sudo cp scripts/cti-update.sh /usr/local/bin/cti-observatory-update &&
     sudo chown root:root /usr/local/bin/cti-observatory-update &&
     sudo chmod 755 /usr/local/bin/cti-observatory-update &&
     sudo /usr/local/bin/cti-observatory-update init "$PWD"
   ```

   If you recreate the project with a different name, UID, or GID, rerun `init` from the project folder after the new container starts. If a release updates the host script, repeat the install commands with that version of the script.

4. In DSM, open **Control Panel → Task Scheduler → Create → Scheduled Task → User-defined script**. Set the following values and save. [Synology Task Scheduler guide](https://kb.synology.com/index.php/en-ro/DSM/help/DSM/AdminCenter/system_taskscheduler?version=7)

   | Tab | What to enter |
   | --- | --- |
   | **General** | Name the task **Cyber Intel App Updates**, choose **root** as the user, and enable the task. |
   | **Schedule** | Choose when DSM checks for a queued request. You can also run the task on demand. |
   | **Task Settings** | Paste the command below into **Run command**, using the path from [Identify the running project](#identify-the-running-project). |

   ```sh
   /usr/local/bin/cti-observatory-update run "/volume1/docker/sentinel-cyber-intel-threat-observatory"
   ```

   In Task Scheduler, use **Settings → Save output results** to retain task output for troubleshooting.

5. Reopen **App updates** in the dashboard. On first setup it should say **Ready to check GitHub for an update**. The task processes requests only when one is queued. Anyone who can access the dashboard can queue a request, so keep access on your trusted network.

Both Git and ZIP installations can use the dashboard updater. It always targets this repository's `main` branch. Keep local Compose customizations in `docker-compose.override.yml` so the updater can apply them to the downloaded build.

## Update manually

1. [Identify the running project](#identify-the-running-project) and [back it up](#back-up). Keep the original project folder and name throughout.
2. Bring the source files up to date using your installation method.

   **Git clone.** Check the branch, remote, and working tree, then record the current commit. If the branch or remote differs from the one you intend to deploy, or you have uncommitted changes, resolve that before continuing.

   ```sh
   git status --short --branch
   git remote -v
   git rev-parse HEAD
   ```

   When the running image is tagged `cti-observatory-update:<commit>`, record the commit from the image name as the running build. To update the branch, run the following command and continue only if it succeeds.

   ```sh
   git pull --ff-only
   ```

   To deploy a specific commit you have fetched, use `git switch --detach COMMIT_SHA` in place of the pull.

   **ZIP download.** On [GitHub](https://github.com/Kibo28/sentinel-cyber-intel-threat-observatory) or your fork, select **Code → Download ZIP** on the branch or revision you want. Extract it in a separate directory. In the deployed project folder, replace `app/` and `scripts/`, and copy over `Dockerfile`, `requirements.txt`, `docker-compose.yml`, and the hidden `.dockerignore`. Keep the previous source archive or a copy of the old source files for rollback. Keep the deployed `data/`, `.env`, `docker-compose.override.yml`, and `.cti-update/` in place.

3. From the same project folder, validate the Compose configuration and rebuild the service. A restart alone still uses the existing image.

   ```sh
   sudo docker compose -p "$CTI_PROJECT" config --quiet &&
     sudo docker compose -p "$CTI_PROJECT" up -d --build cyber-intel-observatory &&
     sudo docker compose -p "$CTI_PROJECT" ps
   ```

4. [Verify the update](#verify-the-update). If the build fails, check the error from `docker compose up`. If the container starts but stays unhealthy, use the logs below.

## Verify the update

1. In Container Manager, check that **cyber-intel-observatory** is running and healthy. From SSH, you can check the same container directly.

   ```sh
   sudo docker inspect --format 'Image={{.Config.Image}} Health={{.State.Health.Status}}' cyber-intel-observatory
   ```

2. Open the dashboard at its usual address and port. Open `/health` at that address and expect `{"status":"ok"}`.
3. Compare the `/data` mount with the one recorded in [Identify the running project](#identify-the-running-project). In **History archive**, find a record from before the update. If you use **Favorites**, open a saved record and check its tags. Confirm saved source and schedule settings if you customized them.

## Troubleshoot an update

| What you see | What to check |
| --- | --- |
| **Set up the NAS updater** or **The NAS updater request folder is unavailable** | Check that the running Compose project includes the updater mounts. Run the [setup commands](#set-up-the-nas-updater-once) from the folder reported by Docker. |
| **Update queued** past the expected run | In DSM, verify the task is enabled, runs as `root`, and points to the active project folder. Select **Run**, then **Action → View Result** once the task finishes if output saving is enabled. |
| **The update could not be completed** | Read the DSM task output for the download or build error before retrying. |
| **The NAS restored the previous version** | Verify that the dashboard opens. Read the task output for the deployment or health-check error before retrying. |
| **The update and rollback could not be verified** or the dashboard stays unreachable | Check the DSM task output and the container logs. If you need to roll back manually, select the last working Git commit or restore the last working ZIP source files, then [rebuild the project](#update-manually). [Restore the data backup](#restore) if the database also needs recovery. |

```sh
sudo docker logs --tail=100 cyber-intel-observatory
```

Dashboard rollback attempts to redeploy the previous image. Recovering the database to its pre-update state requires a backup.

### If favorites or tags are missing

Open `/api/favorites` at the dashboard's usual address.

- **A map of saved records**. Reload the dashboard, clear the search, and select **All tags** in **Favorites**.
- **`404`**. Check the running image. It may be an older build without Favorites. Update the deployed source and rebuild using the correct project.
- **`{"favorites":{}}`**. Check whether **History archive** still shows older records. Compare the `/data` mount from [Identify the running project](#identify-the-running-project) with the one you recorded. If it changed, point the project back to the original data folder. If the original database is unavailable, look for a backup made after you saved the favorites.

## Restore

These steps assume a bind-mounted data folder and a backup from [Back up](#back-up). Restoring replaces the live archive, favorites, and saved settings with the state at backup time. Keep the current data copy in case it contains newer findings.

1. Confirm the live path in [Identify the running project](#identify-the-running-project). If you reconnected, set `CTI_BACKUP` to the backup path printed during the backup step. Wait for any queued or running update to finish.
2. Stage a copy of the backup with its ownership and permissions. Then stop the container, save the current data directory as `data-before-restore` in the printed recovery folder, and move the staged copy into place.

   ```sh
   sudo test -s "$CTI_BACKUP/data/cti.db" &&
     CTI_RECOVERY=$(sudo mktemp -d "${CTI_DATA_DIR%/*}/cyber-intel-recovery.XXXXXX") &&
     printf '%s\n' "$CTI_RECOVERY" &&
     sudo cp -a "$CTI_BACKUP/data" "$CTI_RECOVERY/restored-data" &&
     sudo docker stop cyber-intel-observatory &&
     sudo mv "$CTI_DATA_DIR" "$CTI_RECOVERY/data-before-restore" &&
     sudo mv "$CTI_RECOVERY/restored-data" "$CTI_DATA_DIR"
   ```

3. After the restore succeeds, start the container with `sudo docker start cyber-intel-observatory`. If the final move fails, put `"$CTI_RECOVERY/data-before-restore"` back at `"$CTI_DATA_DIR"` before starting. If you need to recover deployment settings, review the files in `"$CTI_BACKUP/config"`, restore the required settings, and recreate the service from a known-good build.
4. [Verify the update](#verify-the-update) against records and settings present at the time of the backup.
