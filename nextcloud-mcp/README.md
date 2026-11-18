# Nextcloud MCP

Home Assistant app packaging for [cloud-py-api/nc_mcp_server](https://github.com/cloud-py-api/nc_mcp_server), including its existing Cospend, files, calendar, contacts and other tools.

The app runs upstream `nc-mcp-server==0.9.0` directly. It adds Home Assistant configuration, an Ingress setup page and a separate Bearer token for the MCP endpoint. No custom Cospend adapter is used.

Start the app, open its web UI, test and save your Nextcloud credentials, then restart. Read [DOCS.md](DOCS.md) for permissions, client setup and HTTPS access.
