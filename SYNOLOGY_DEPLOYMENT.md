# Deploy Cyber Intel on Synology using SSH

This quickstart uses Docker Compose v2 on a DSM 7 NAS with Container Manager installed. For File Station or Container Manager setup, use the [full installation guide](SYNOLOGY_INSTALLATION.md). Run the commands on your NAS after signing in over SSH.

1. Check Compose and clone into a directory where your NAS account can create the project:

   ```bash
   sudo docker compose version
   cd /volume1/docker
   git clone https://github.com/Kibo28/sentinel-cyber-intel-threat-observatory.git
   cd sentinel-cyber-intel-threat-observatory
   ```

   If Git is unavailable, [download and extract the source ZIP](SYNOLOGY_INSTALLATION.md#2-download-the-application-to-synology) and continue from the extracted project root.

2. [Set up write access to `data/`](SYNOLOGY_INSTALLATION.md#5-create-the-persistent-data-folder-and-permissions) for the container account. To bind to a particular NAS address or change the host port, [create a local `.env`](SYNOLOGY_INSTALLATION.md#4-override-the-compose-defaults) next to the Compose file.

3. Validate, build, and start:

   ```bash
   sudo docker compose config --quiet
   sudo docker compose up -d --build
   sudo docker compose ps
   ```

4. Open `http://YOUR_NAS_IP:8791` on your private network, substituting `WEB_PORT` if changed. Verify [the health endpoint and first feed collection](SYNOLOGY_INSTALLATION.md#9-open-and-test-the-dashboard). If the app does not start, inspect the logs:

   ```bash
   sudo docker compose logs --tail=100 cyber-intel-observatory
   ```

The dashboard has no login. Keep the published port on a trusted private network. For ongoing maintenance, see the [step-by-step update guide](docs/UPDATING.md), [backup and restore](SYNOLOGY_INSTALLATION.md#11-backup-and-update-without-losing-history), and [troubleshooting](SYNOLOGY_INSTALLATION.md#12-troubleshooting).
