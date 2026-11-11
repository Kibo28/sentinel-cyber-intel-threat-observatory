# Update Cyber Intel on Synology

**App updates** installs a new version of the dashboard. **Sync feeds** collects new findings using the version you already have.

- If **App updates → Update app** is available, follow [Run an update from the dashboard](#run-an-update-from-the-dashboard).
- If the button says setup is required, [set up the NAS updater once](#set-up-the-nas-updater-once). If your installed version has no **App updates** menu, [update manually](#update-manually) first.
- If you prefer to update by hand, run a fork, or can't use DSM Task Scheduler, follow [Update manually](#update-manually).

## Before each update

1. Let any queued or running app update finish. Wait to request another until the backup is complete.
2. [Back up the entire `data/` folder and your local configuration](../SYNOLOGY_INSTALLATION.md#back-up). The backup briefly stops the app so SQLite can close cleanly. The database contains your archive, favorites, tags, and collection settings. The updater does not make this backup for you.

Shell commands in this guide run **on the NAS over SSH**, from the folder containing the deployed `docker-compose.yml`. Replace the example path if your project lives elsewhere:

```sh
cd /volume1/docker/sentinel-cyber-intel-threat-observatory
```

If you gave the project a custom name in Container Manager, add `-p YOUR_PROJECT_NAME` after `docker compose` in the backup and manual commands. For example: `sudo docker compose -p cyber-intel-observatory ps`. The dashboard updater reads the name of the existing project during setup.

## Run an update from the dashboard

1. **In the dashboard:** Open **App updates** in the sidebar and select **Update app** once. **Update queued** means the request was saved and is waiting for DSM.
2. **In DSM:** To start immediately, open **Control Panel → Task Scheduler**, select **Cyber Intel App Updates** (or the name you chose), then select **Run**. Otherwise, wait for its next scheduled run. The task does nothing when no update is queued.
3. **In the dashboard:** Wait for the result. The NAS checks the latest commit on this project's GitHub `main` branch, builds the image, then replaces the container and waits for its health check. The build may take a few minutes. The dashboard may show **Waiting to reconnect** while the container restarts; the dialog checks again automatically.
4. When you see **Update complete**, select **Reload dashboard**. If it says **The dashboard is already on the latest version**, there's nothing to reload. Open **History archive** and **Favorites** to confirm your data is present.

The updater keeps your existing `data/`, `.env`, and optional `docker-compose.override.yml`. It builds from a separate download and leaves the source files in your project folder as they were. Before a later manual rebuild, [update those local source files](#update-manually) so the rebuild doesn't bring back an older version.

## Set up the NAS updater once

1. **On the NAS over SSH:** Make sure the dashboard is already running from its final project folder. Check that your [Docker Compose supports `up --wait-timeout`](https://docs.docker.com/reference/cli/docker/compose/up/):

   ```sh
   sudo docker compose up --help | grep -F -- --wait-timeout
   ```

   If the option is missing, use the manual method or update Container Manager. The NAS also needs network access to GitHub and the image build dependencies. Both Git and ZIP installations can use the updater for this repository.

2. **On the NAS over SSH:** From the project folder, install the script and let it configure the request folder for the running container:

   ```sh
   sudo cp scripts/cti-update.sh /usr/local/bin/cti-observatory-update &&
     sudo chown root:root /usr/local/bin/cti-observatory-update &&
     sudo chmod 755 /usr/local/bin/cti-observatory-update &&
     sudo /usr/local/bin/cti-observatory-update init "$PWD"
   ```

   If you later change `CTI_UID` or `CTI_GID`, rerun the last command after recreating the container.

3. **In DSM:** Open **Control Panel → Task Scheduler → Create → Scheduled Task → User-defined script**. Fill in these tabs:

   | Tab | What to enter |
   | --- | --- |
   | **General** | Name the task **Cyber Intel App Updates**, select **root** as the user, and enable it. |
   | **Schedule** | Choose a daily schedule and a repeat interval that suits you. Requests wait until a scheduled run unless you select **Run** yourself. |
   | **Task Settings** | Paste the command below into the script field. Replace the path with your actual project folder. |

   ```sh
   /usr/local/bin/cti-observatory-update run "/volume1/docker/sentinel-cyber-intel-threat-observatory"
   ```

   Save the task. To keep logs for troubleshooting, enable **Settings → Save output results** on the Task Scheduler page. See [Synology's Task Scheduler guide](https://kb.synology.com/en-ca/DSM/help/DSM/AdminCenter/system_taskscheduler?version=7).

4. **In the dashboard:** Reopen **App updates**. You should see **Ready to check GitHub for an update** on first setup. When you're ready to deploy, follow the [dashboard steps](#run-an-update-from-the-dashboard).

## Update manually

1. [Back up first](#before-each-update). Use the existing project folder and Compose project name throughout.
2. Update the source files using the method you originally installed with:
   - **Git clone:** Run `git pull --ff-only` from the project folder. Continue only if it succeeds. If Git reports local changes or a diverged branch, resolve those before rebuilding.
   - **ZIP download:** From [the GitHub repository](https://github.com/Kibo28/sentinel-cyber-intel-threat-observatory) or your fork, choose **Code → Download ZIP** and extract it to a separate folder. Copy the new source into your existing project folder: replace `app/` and `scripts/`, and copy `Dockerfile`, `requirements.txt`, `docker-compose.yml`, and `.dockerignore` over the old files. Leave the existing `data/`, `.env`, `docker-compose.override.yml`, and `.cti-update/` where they are.
3. On the NAS over SSH, rebuild the existing project. A restart by itself won't pick up the new source files.

   ```sh
   sudo docker compose config --quiet &&
     sudo docker compose up -d --build &&
     sudo docker compose ps
   ```

4. When the container is healthy, reload the dashboard at its usual address and check **History archive** and **Favorites**. For a command line check, see [test the dashboard](../SYNOLOGY_INSTALLATION.md#9-open-and-test-the-dashboard).

## If an update gets stuck or fails

| What you see | What to do |
| --- | --- |
| **Set up the NAS updater** | Start the current Compose project and complete [the one-time setup](#set-up-the-nas-updater-once) from its actual project folder. |
| **Update queued** after the expected run | In DSM, check that the task is enabled, runs as `root`, and points to the running project's folder. Select **Run** and check **Action → View Result** if task output is enabled. |
| **The update could not be completed** | Read the task output for the download or build error before retrying. |
| **The NAS restored the previous version** | The new container failed to start or pass its health check. Verify that the dashboard opens, then inspect the task output before retrying. |
| **The update and rollback could not be verified**, or the dashboard stays unreachable | Check the task output and **Container Manager → Container → Log**. Over SSH, run `sudo docker compose logs --tail=100 cyber-intel-observatory` from the project folder. Use the [restore procedure](../SYNOLOGY_INSTALLATION.md#restore) if you need to recover the archive from your backup. |

Automatic rollback tries to bring back the previous container image. It does not restore the database to its state before the update.
