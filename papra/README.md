# Home Assistant App: Papra

Minimalistic, self-hosted document archiving platform.

## About

[Papra](https://papra.app) is a clean, minimal document management solution you can run
entirely on your own hardware. This app wraps the official Papra container image and
wires it into the Home Assistant ecosystem, giving you:

- **Persistent storage** with the database in app config storage and documents in `/share/papra`
- **Easy configuration** through the Home Assistant UI
- **Automatic startup** on Home Assistant OS boot

## Installation

1. Add this repository to your Home Assistant app store:
   `https://github.com/chWagnr/ha-apps`
2. Find **Papra** in the app store and click **Install**.
3. Configure at minimum `app_base_url` and `auth_secret` in the app configuration.
4. Start the app.
5. Open the Web UI on port `1221`.

## Documentation

Full configuration reference: [DOCS.md](DOCS.md)

## File Storage

Papra splits its persistent data across the Home Assistant app config directory and
the shared folder.

This includes:

- the SQLite database in `/config/db`
- uploaded and managed documents in `/share/papra/documents`

Inside Home Assistant, the database lives in Papra's app config storage. On the host
this is under `/addon_configs/{REPO}_papra`, where `{REPO}` depends on how the app
repository was added. Inside the container it is available at `/config`. Documents are
stored in the shared folder so they can also be reached via Samba or SSH.

## Backing up

The simplest way to back up Papra is to create a Home Assistant backup. This app is
configured so its app config directory is included in backups.

For a complete backup, make sure you include both:

- `/config/db`
- `/share/papra/documents`

Another way is to make copies of both locations manually.

Note: Papra uses `backup: cold`, so Home Assistant will stop the app during backup
creation and start it again afterwards. This helps keep the SQLite database in a
consistent state.

Note: A backup that includes the app but does not include the `share` directory will
not include your Papra documents.

## Source

- App source: <https://github.com/chWagnr/ha-apps/tree/main/papra>
- Upstream Papra: <https://github.com/papra-hq/papra>
