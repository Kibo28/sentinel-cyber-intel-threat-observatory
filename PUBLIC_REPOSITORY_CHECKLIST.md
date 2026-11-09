# Public repository release checklist

- [ ] Repository **Kibo28/sentinel-cyber-intel-threat-observatory** is **Public** and contains only reviewed source files.
- [ ] The correct Cyber Intel icon and wordmark assets are present in `app/static/assets/`.
- [ ] No `.env`, API keys, NAS access tokens, SSH keys, user data, SQLite databases, or container logs are staged.
- [ ] Keep `legacy_history.json` out of the public repo; it is distributed separately as optional unverified sample history.
- [ ] Run `python -m pytest -q` locally; confirm GitHub Actions tests pass after push.
- [ ] Decide whether you want an open-source `LICENSE` and contributor policy. Public visibility alone does not grant permission to reuse.
- [ ] Keep the deployed service private behind LAN/VPN/TLS; do not expose TCP/8791 directly.

The public GitHub repository is just the source code. Your NAS deployment, running containers and `.env` remain separate.
