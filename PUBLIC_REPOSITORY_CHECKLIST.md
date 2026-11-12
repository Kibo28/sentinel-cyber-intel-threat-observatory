# Public repository release checklist

- [ ] Repository **Kibo28/sentinel-cyber-intel-threat-observatory** is **Public** and contains only reviewed source files.
- [ ] The correct Cyber Intel icon and wordmark assets are present in `app/static/assets/`.
- [ ] No `.env`, API keys, NAS access tokens, SSH keys, user data, SQLite databases, or container logs are staged.
- [ ] Keep private legacy exports out of the public repository. Use the [example archive](example/cyber-threat-archive-2026-11-09.json) to document the import format.
- [ ] [Run the test suite locally](README.md#developer-tests).
- [ ] Decide whether you want an open-source `LICENSE` and contributor policy. Public visibility alone does not grant permission to reuse.
- [ ] Keep the deployed service private behind LAN/VPN/TLS; do not expose TCP/8791 directly.

The public GitHub repository is just the source code. Your NAS deployment, running containers and `.env` remain separate.
