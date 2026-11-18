# Configuration and operation

## Nextcloud connection

1. Start the app and open **Web UI** through Home Assistant Ingress.
2. Enter the Nextcloud base URL (HTTPS, including its installation subpath if applicable), username and a dedicated Nextcloud **app password** from Settings → Security.
3. Select **Test and save**. The test reads the authenticated user profile; it creates or edits no Nextcloud data.
4. Restart the app to activate saved credentials. This avoids replacing upstream's global client while requests are running.
5. Reveal the separate MCP token in the web UI and configure the client.

You can also enter credentials in the app configuration. Cospend projects must be accessible to that Nextcloud user; project share links are not used. The profile test verifies authentication, not whether every optional Nextcloud app is installed. Use `list_cospend_projects` to check Cospend access.

| Option | Purpose |
| --- | --- |
| `nextcloud_url` | HTTPS Nextcloud base URL, without query, fragment or embedded credentials |
| `nextcloud_user` | Nextcloud username |
| `nextcloud_password` | Dedicated app password, stored as a private password option |
| `mcp_token` | Independent MCP Bearer token; generated and persisted when empty |
| `permissions` | Upstream `read` (default), `write`, or `destructive` |
| `allowed_origins` | Exact browser origins allowed to send an Origin header; empty by default |

The server exposes upstream's tool catalog. Permission checks happen when a tool is called: `read` rejects writes; `write` adds creation and editing; `destructive` also permits deletions and other destructive operations. These permissions apply across Nextcloud apps, not only Cospend. Nextcloud user permissions remain an additional limit. Tool semantics and Cospend amount/split handling come from upstream.

Local-file uploads (`upload_file_from_path`) are not enabled. Automatic status-code retries are disabled (`retry_max=0`), and app-password mode avoids cached-login replay. After any uncertain write outcome, read the relevant data before retrying manually.

## MCP clients

- Endpoint: `http://HOME_ASSISTANT:3738/mcp`
- Transport: Streamable HTTP, including upstream JSON/SSE responses and protocol headers.
- Authentication: `Authorization: Bearer YOUR_MCP_TOKEN`
- Healthcheck: `GET /healthz` (no token), with `configured` indicating whether credentials were supplied at startup. It does not probe Nextcloud availability.

For a client supporting a remote HTTP server, configure the URL and Bearer header. Browser clients must additionally use an exact configured `allowed_origins` value; CORS preflight is not provided. Native clients normally send no Origin header.

Port 8099 is exclusively for HA Ingress, is not published and rejects direct connections outside the Supervisor Ingress proxy. The setup page uses a CSRF token. The MCP token does not grant access to this page.

## HTTPS and external access

Publish port 3738 only through a trusted HTTPS reverse proxy or tunnel. Preserve Authorization, Accept and MCP protocol headers, POST/GET/DELETE methods, and SSE streaming without buffering. HA Ingress provides the setup UI, not an external MCP URL. Upstream is embedded in the app and has no separate unauthenticated listening port.

This release uses a static Bearer token; it does not implement OAuth discovery or an OAuth authorization server. External client authentication compatibility must be checked before exposing the endpoint. No reverse proxy, tunnel or external client registration is configured by this app.

## Maintenance and recovery

Runtime dependencies are pinned in `requirements.txt`. Builds for amd64 and aarch64 run through the repository's Nextcloud MCP workflow. Upstream exceptions and HTTP access logs are suppressed in production to avoid logging credentials or API bodies; clients still receive upstream tool results and errors.

To rotate MCP access, set a new 32–256 character token (letters, digits, `_`, `-`) and restart. To rotate Nextcloud access, create a replacement app password, test and save it, restart, then revoke the old app password. Home Assistant backups remain the recovery mechanism for app options. Keep personal credentials and URLs out of this repository.
