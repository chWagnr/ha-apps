"""Home Assistant packaging and access control for the unmodified nc_mcp_server."""
import asyncio
import hmac
import json
import logging
import os
import re
import secrets
import signal
from contextlib import asynccontextmanager
from pathlib import Path
from time import gmtime, monotonic
from urllib.parse import urlsplit

import httpx
import uvicorn
from nc_mcp_server.config import Config
from nc_mcp_server.permissions import PermissionLevel
from nc_mcp_server.server import create_server, get_client
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response
from starlette.routing import Route

INGRESS_ADDRESSES = {"172.30.32.2", "::ffff:172.30.32.2"}
LOGGER = logging.getLogger("nextcloud_mcp.addon")


def validate_options(raw):
    options = {"nextcloud_url": "", "nextcloud_user": "", "nextcloud_password": "",
               "mcp_token": "", "permissions": "read", "allowed_origins": [], **raw}
    for key in ("nextcloud_url", "nextcloud_user", "nextcloud_password", "mcp_token"):
        if not isinstance(options[key], str) or len(options[key]) > 4096:
            raise ValueError("Invalid text option.")
    if options["nextcloud_url"]:
        try:
            url = urlsplit(options["nextcloud_url"])
            valid = (url.scheme == "https" and url.hostname and not url.username and not url.password
                     and not url.query and not url.fragment and url.port != 0
                     and not re.search(r"[\s\\]", options["nextcloud_url"]))
        except ValueError:
            valid = False
        if not valid:
            raise ValueError("Use an HTTPS Nextcloud base URL without credentials, query or fragment.")
        options["nextcloud_url"] = options["nextcloud_url"].rstrip("/")
    if options["permissions"] not in ("read", "write", "destructive"):
        raise ValueError("Invalid permissions; use read, write or destructive.")
    if options["mcp_token"] and not re.fullmatch(r"[A-Za-z0-9_-]{32,256}", options["mcp_token"]):
        raise ValueError("MCP token must contain 32–256 letters, digits, underscores or hyphens.")
    origins = options["allowed_origins"]
    if not isinstance(origins, list):
        raise ValueError("Allowed origins must be a list.")
    for origin in origins:
        try:
            url = urlsplit(origin)
            valid = (url.scheme in ("http", "https") and url.hostname and not url.username
                     and not url.password and not url.path and not url.query and not url.fragment
                     and origin == f"{url.scheme}://{url.netloc}" and url.port != 0)
        except (ValueError, TypeError, AttributeError):
            valid = False
        if not valid:
            raise ValueError("Use exact HTTP(S) origins without a trailing slash.")
    return options


async def persist_options(patch, *, replace=False, token=None, transport=None):
    token = token or os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        raise ValueError("Supervisor access is required to save add-on options.")
    try:
        async with httpx.AsyncClient(base_url="http://supervisor", timeout=5, follow_redirects=False,
                                     transport=transport, headers={"Authorization": f"Bearer {token}"}) as client:
            async def request(method, path, **kwargs):
                response = await client.request(method, "/addons/self/" + path, **kwargs)
                response.raise_for_status()
                payload = response.json()
                if payload["result"] != "ok":
                    raise ValueError()
                return payload.get("data", {})
            current = (await request("GET", "info"))["options"]
            if not isinstance(current, dict):
                raise ValueError()
            if not replace and any(current.get(key) and current[key] != value for key, value in patch.items()):
                raise ValueError()
            await request("POST", "options", json={"options": {**current, **patch}})
            verified = (await request("GET", "info"))["options"]
            if any(verified.get(key) != value for key, value in patch.items()):
                raise ValueError()
    except Exception:
        raise ValueError("Cannot confirm saved add-on options. Check Supervisor and restart the app.") from None


async def probe_connection(options):
    """Read only the authenticated user; no MCP state or Nextcloud data is changed."""
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
            response = await client.get(options["nextcloud_url"] + "/ocs/v2.php/cloud/user",
                                        params={"format": "json"},
                                        auth=(options["nextcloud_user"], options["nextcloud_password"]),
                                        headers={"OCS-APIRequest": "true", "Accept": "application/json"})
            response.raise_for_status()
            data = response.json()["ocs"]
            if data["meta"]["status"] != "ok" or not data["data"].get("id"):
                raise ValueError()
    except httpx.HTTPStatusError as exc:
        LOGGER.warning("Nextcloud connection test returned HTTP %d.", exc.response.status_code)
        raise ValueError("Connection test failed. Check URL, user and app password.") from None
    except httpx.TimeoutException:
        LOGGER.warning("Nextcloud connection test timed out.")
        raise ValueError("Connection test failed. Check URL, user and app password.") from None
    except Exception:
        raise ValueError("Connection test failed. Check URL, user and app password.") from None


def upstream_config(options):
    return Config(nextcloud_url=options["nextcloud_url"], user=options["nextcloud_user"],
                  password=options["nextcloud_password"], permission_level=PermissionLevel(options["permissions"]),
                  host="0.0.0.0", port=3738, retry_max=0, is_app_password=True, upload_root="")


class Gateway:
    def __init__(self, upstream, options):
        self.upstream = upstream
        self.options = options

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.upstream(scope, receive, send)
        request = Request(scope, receive)
        method = request.method if request.method in {"GET", "POST", "DELETE"} else "OTHER"
        if request.url.path == "/healthz" and request.method == "GET":
            response = JSONResponse({"status": "ok", "configured": self.upstream is not None})
        elif not hmac.compare_digest(request.headers.get("authorization", "").encode(),
                                     ("Bearer " + self.options["mcp_token"]).encode()):
            if request.url.path == "/mcp":
                LOGGER.warning("MCP %s rejected (401): missing or invalid Bearer token.", method)
            response = JSONResponse({"error": "Unauthorized"}, status_code=401,
                                    headers={"WWW-Authenticate": 'Bearer realm="nextcloud-mcp"'})
        elif request.headers.get("origin") and request.headers["origin"] not in self.options["allowed_origins"]:
            if request.url.path == "/mcp":
                LOGGER.warning("MCP %s rejected (403): origin is not allowed.", method)
            response = JSONResponse({"error": "Origin not allowed"}, status_code=403)
        elif request.url.path != "/mcp":
            response = JSONResponse({"error": "Not found"}, status_code=404)
        elif self.upstream is None:
            LOGGER.warning("MCP %s unavailable (503): configure Nextcloud and restart the app.", method)
            response = JSONResponse({"error": "Configure Nextcloud in the add-on web UI and restart."}, status_code=503)
        else:
            started = monotonic()
            # Preserve upstream HTTP methods, SSE streaming and protocol headers.
            # Never forward the separate MCP credential into the upstream application.
            scope = {**scope, "headers": [(k, v) for k, v in scope["headers"] if k.lower() != b"authorization"]}
            async def secure_send(message):
                if message["type"] == "http.response.start":
                    status = message["status"]
                    LOGGER.log(logging.WARNING if status >= 400 else logging.INFO,
                               "MCP %s sent HTTP %d headers after %.0f ms.", method, status,
                               (monotonic() - started) * 1000)
                    message = {**message, "headers": [*message["headers"], (b"cache-control", b"no-store"),
                                                      (b"x-content-type-options", b"nosniff")]}
                await send(message)
            try:
                return await self.upstream(scope, receive, secure_send)
            except Exception:
                LOGGER.error("MCP %s failed while processing the request.", method)
                raise
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        await response(scope, receive, send)


def create_setup(options, *, persist=persist_options, probe=probe_connection, ingress_check=None):
    csrf = secrets.token_hex(32)
    busy = asyncio.Lock()
    restart_required = False
    ingress_check = ingress_check or (lambda address: address in INGRESS_ADDRESSES)

    async def endpoint(request):
        nonlocal restart_required
        if not request.client or not ingress_check(request.client.host):
            return JSONResponse({"message": "Ingress access only."}, status_code=403)
        path = request.url.path
        if request.method == "GET":
            if path == "/":
                return HTMLResponse(Path(__file__).with_name("setup.html").read_text())
            if path == "/setup.js":
                return Response(Path(__file__).with_name("setup.js").read_text(), media_type="text/javascript")
            if path == "/status":
                return JSONResponse({"csrf": csrf, "restart_required": restart_required,
                                     "message": "Restart the app to activate the saved connection." if restart_required
                                     else "Configure Nextcloud with a username and app password. Permissions: " + options["permissions"]})
        if path not in ("/connection", "/mcp-token"):
            return JSONResponse({"message": "Not found."}, status_code=404)
        if request.method != "POST":
            return JSONResponse({"message": "Use POST."}, status_code=405)
        if not hmac.compare_digest(request.headers.get("x-setup-csrf", "").encode(), csrf.encode()):
            return JSONResponse({"message": "Reload the setup page."}, status_code=403)
        if path == "/mcp-token":
            return JSONResponse({"token": options["mcp_token"]})
        if request.headers.get("content-type", "").split(";")[0] != "application/json":
            return JSONResponse({"message": "Use application/json."}, status_code=415)
        if busy.locked():
            return JSONResponse({"message": "Connection test already running."}, status_code=429)
        async with busy:
            stage = "validating settings"
            try:
                body = bytearray()
                async for chunk in request.stream():
                    body.extend(chunk)
                    if len(body) > 16384:
                        return JSONResponse({"message": "Request too large."}, status_code=413)
                data = json.loads(body)
                if not isinstance(data, dict) or set(data) != {"nextcloud_url", "nextcloud_user", "nextcloud_password"}:
                    raise ValueError()
                candidate = validate_options({**options, **data})
                if not all(candidate[key] for key in data):
                    raise ValueError()
                stage = "testing Nextcloud connection"
                LOGGER.info("Testing Nextcloud connection from the setup page.")
                await probe(candidate)
                LOGGER.info("Nextcloud connection test passed.")
                stage = "saving app options"
                await persist({key: candidate[key] for key in data}, replace=True)
                restart_required = True
                LOGGER.info("Nextcloud settings saved. Restart the app to activate them.")
                return JSONResponse({"message": "Connection successful. Saved in add-on options. Restart the app to activate. No data was changed."})
            except Exception:
                LOGGER.warning("Nextcloud setup failed while %s.", stage)
                return JSONResponse({"message": "Cannot test or save connection. Check URL, user, app password and Supervisor access."}, status_code=400)

    app = Starlette(routes=[Route(path, endpoint, methods=["GET", "POST"]) for path in
                            ("/", "/setup.js", "/status", "/connection", "/mcp-token")])
    async def secure_headers(request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = "default-src 'none'; script-src 'self'; style-src 'unsafe-inline'; connect-src 'self'; form-action 'none'; base-uri 'none'"
        return response
    app.add_middleware(BaseHTTPMiddleware, dispatch=secure_headers)
    return app


async def build_apps(raw, *, persist=persist_options):
    options = validate_options(raw)
    if not options["mcp_token"]:
        options["mcp_token"] = secrets.token_hex(32)
        await persist({"mcp_token": options["mcp_token"]})
        LOGGER.info("Generated and saved an MCP Bearer token.")
    configured = all(options[key] for key in ("nextcloud_url", "nextcloud_user", "nextcloud_password"))
    upstream = create_server(upstream_config(options)).streamable_http_app() if configured else None
    return Gateway(upstream, options), create_setup(options, persist=persist)


async def main(options_path="/data/options.json"):
    gateway, setup = await build_apps(json.loads(Path(options_path).read_text()))
    servers = [uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=port, proxy_headers=False,
                                            access_log=False, log_config=None))
               for app, port in ((gateway, 3738), (setup, 8099))]
    async with gateway.upstream.router.lifespan_context(gateway.upstream) if gateway.upstream else empty_lifespan():
        # The upstream lifespan is managed here, once, for graceful session cleanup.
        for server in servers:
            server.config.lifespan = "off"
        tasks = [asyncio.create_task(server.serve()) for server in servers]
        loop = asyncio.get_running_loop()
        def stop():
            for server in servers:
                server.should_exit = True
        for signum in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(signum, stop)
        LOGGER.info("Starting MCP on port 3738 and setup on port 8099 (Nextcloud configured: %s, permissions: %s).",
                    "yes" if gateway.upstream else "no", gateway.options["permissions"])
        if gateway.upstream is None:
            LOGGER.warning("Nextcloud settings are incomplete. Use the Home Assistant setup page.")
        try:
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        finally:
            stop()
            await asyncio.gather(*tasks)
            if gateway.upstream:
                await get_client().close()
            LOGGER.info("Nextcloud MCP stopped.")


@asynccontextmanager
async def empty_lifespan():
    yield


if __name__ == "__main__":
    # Library logs can contain credentials and API data. Emit only the app's
    # own messages, including when an upstream exception reaches Uvicorn.
    logging.basicConfig(handlers=[logging.NullHandler()], force=True)
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s.%(msecs)03dZ %(levelname)s %(message)s",
                                  datefmt="%Y-%m-%dT%H:%M:%S")
    formatter.converter = gmtime
    handler.setFormatter(formatter)
    LOGGER.addHandler(handler)
    LOGGER.setLevel(logging.INFO)
    LOGGER.propagate = False
    try:
        asyncio.run(main())
    except (Exception, SystemExit):
        LOGGER.error("Nextcloud MCP failed to run. Check app options, Supervisor access and port availability.")
        raise SystemExit(1) from None
