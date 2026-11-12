# Deploy Cyber Intel from Git on Synology DSM 7

Use this procedure for a fresh installation from a Git checkout. For a ZIP download or a Container Manager installation, see the [Synology installation guide](SYNOLOGY_INSTALLATION.md). To keep an existing archive and deployment, follow the [update guide](docs/UPDATING.md).

## 1. Connect to the NAS

Install **Container Manager** from Package Center and enable SSH in **Control Panel → Terminal & SNMP**. Connect from your computer.

```sh
ssh YOUR_SYNOLOGY_USER@YOUR_NAS_IP
```

On the NAS, check that Git and Docker Compose are available.

```sh
git --version
sudo docker compose version
```

If Git is unavailable, use the [ZIP installation procedure](SYNOLOGY_INSTALLATION.md#2-download-the-application-to-synology).

## 2. Clone and configure

From a shared folder your NAS account can write to, clone the repository. The example uses `/volume1/docker`.

```sh
cd /volume1/docker
git clone https://github.com/Kibo28/sentinel-cyber-intel-threat-observatory.git
cd sentinel-cyber-intel-threat-observatory
```

1. Set [Compose options in `.env`](SYNOLOGY_INSTALLATION.md#4-override-the-compose-defaults) if you need a different port, LAN bind address, or collection schedule.
2. [Prepare the persistent data folder](SYNOLOGY_INSTALLATION.md#5-create-the-persistent-data-folder-and-permissions) so the container account can write to it.
3. [Build and start the project over SSH](SYNOLOGY_INSTALLATION.md#8-ssh-fallback-build-and-launch-with-docker-compose).
4. [Open the dashboard and check service health](SYNOLOGY_INSTALLATION.md#9-open-and-test-the-dashboard).

For later upgrades, follow the [dashboard or manual update procedure](docs/UPDATING.md).
