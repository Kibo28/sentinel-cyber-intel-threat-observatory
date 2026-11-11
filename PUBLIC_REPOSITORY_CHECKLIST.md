# Public repository release checklist

- [ ] Review the staged diff, including images and [example archives](example/). Publish only material approved for public distribution; historical reports should be marked as unverified.
- [ ] Keep `.env`, local Compose overrides, SQLite databases, updater state, credentials, logs, backups, and private exports out of Git. Review staged files even when ignore rules are in place.
- [ ] Verify that the icon, wordmark, and documentation links work. Run `python -m pytest -q` from the repository root. There is no GitHub Actions test workflow in this checkout.
- [ ] Confirm that the installation and API guides reflect any changes to Compose settings, routes, data storage, or dashboard controls.
- [ ] Decide whether to add an explicit license and contribution policy before inviting third-party reuse.
- [ ] Keep the running dashboard private. Back up the deployed SQLite data and local configuration before updating.

The public repository distributes the app and documentation. The NAS deployment and its archive stay separate.
