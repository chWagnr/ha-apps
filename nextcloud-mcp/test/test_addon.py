import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch
import httpx
from nc_mcp_server.server import get_client
from nc_mcp_server.permissions import PermissionLevel, set_permission_level
from addon import build_apps, create_setup, persist_options, upstream_config, validate_options

OPTIONS = {"nextcloud_url": "https://cloud.example/nextcloud", "nextcloud_user": "test", "nextcloud_password": "private-app-password", "mcp_token": "a" * 64}
HEADERS = {"Authorization": "Bearer " + OPTIONS["mcp_token"], "Accept": "application/json, text/event-stream"}
def rpc_data(response):
    if response.headers.get("content-type", "").startswith("text/event-stream"):
        return json.loads(next(line[6:] for line in response.text.splitlines() if line.startswith("data: ")))
    return response.json()

class AddonTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.gateway, self.setup = await build_apps(OPTIONS)
        ready, self.stop_lifespan = asyncio.Event(), asyncio.Event()
        async def lifespan_task():
            async with self.gateway.upstream.router.lifespan_context(self.gateway.upstream):
                ready.set()
                await self.stop_lifespan.wait()
        self.lifespan_task = asyncio.create_task(lifespan_task())
        await ready.wait()
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.gateway), base_url="http://addon")
    async def asyncTearDown(self):
        await self.client.aclose()
        self.stop_lifespan.set()
        await self.lifespan_task
        await get_client().close()
    async def rpc(self, method, params=None):
        return await self.client.post("/mcp", headers=HEADERS, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}})
    async def test_real_upstream_initialize_and_tools(self):
        response = await self.rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(rpc_data(response)["result"]["serverInfo"]["name"], "nc-mcp-server")
        names = {tool["name"] for tool in rpc_data(await self.rpc("tools/list"))["result"]["tools"]}
        for name in ("list_cospend_projects", "create_cospend_bill", "list_directory", "list_calendars"):
            self.assertIn(name, names)
        self.assertNotIn("upload_file_from_path", names)
        self.assertGreater(len(names), 100)
    async def test_auth_origin_and_health(self):
        self.assertEqual((await self.client.get("/healthz")).status_code, 200)
        self.assertEqual((await self.client.post("/mcp", json={})).status_code, 401)
        self.assertEqual((await self.client.post("/mcp", headers={**HEADERS, "Origin": "https://evil.example"}, json={})).status_code, 403)
        self.assertEqual((await self.client.get("/other", headers=HEADERS)).status_code, 404)
    async def test_read_permission_blocks_actual_upstream_write(self):
        with patch.object(get_client(), "ocs_post_json", new_callable=AsyncMock) as write:
            response = rpc_data(await self.rpc("tools/call", {"name": "create_cospend_bill", "arguments": {"project_id": "test", "what": "Test", "amount": 12.34, "payer": 1, "payed_for": [1, 2]}}))
            self.assertTrue(response["result"]["isError"])
            self.assertIn("permission", str(response).lower())
            write.assert_not_awaited()
    async def test_write_mode_calls_existing_cospend_tool(self):
        set_permission_level(PermissionLevel.WRITE)
        try:
            with patch.object(get_client(), "ocs_post_json", new_callable=AsyncMock, return_value=42) as write:
                response = rpc_data(await self.rpc("tools/call", {"name": "create_cospend_bill", "arguments": {
                    "project_id": "test", "what": "Test", "amount": 12.34, "payer": 1,
                    "payed_for": [1, 2], "date": "2026-11-16"}}))
                self.assertFalse(response["result"].get("isError", False))
                write.assert_awaited_once()
                self.assertEqual(write.call_args.kwargs["json_data"]["amount"], 12.34)
                self.assertEqual(write.call_args.kwargs["json_data"]["payedFor"], "1,2")
            with patch.object(get_client(), "ocs_delete", new_callable=AsyncMock) as delete:
                response = rpc_data(await self.rpc("tools/call", {"name": "delete_cospend_bill", "arguments": {
                    "project_id": "test", "bill_id": 42}}))
                self.assertTrue(response["result"]["isError"])
                delete.assert_not_awaited()
        finally:
            set_permission_level(PermissionLevel.READ)

    async def test_setup_ingress(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.setup), base_url="http://setup") as client:
            self.assertEqual((await client.get("/status")).status_code, 403)
        self.assertEqual((await self.client.get("/mcp-token", headers=HEADERS)).status_code, 404)

class ConfigTests(unittest.IsolatedAsyncioTestCase):
    async def test_generated_token_is_persisted(self):
        persist = AsyncMock()
        gateway, _ = await build_apps({}, persist=persist)
        self.assertRegex(gateway.options["mcp_token"], r"^[a-f0-9]{64}$")
        persist.assert_awaited_once_with({"mcp_token": gateway.options["mcp_token"]})
        self.assertIsNone(gateway.upstream)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=gateway), base_url="http://addon") as client:
            response = await client.post("/mcp", headers={"Authorization": "Bearer " + gateway.options["mcp_token"]})
            self.assertEqual(response.status_code, 503)
    async def test_setup_csrf_save_and_failed_probe(self):
        for success in (True, False):
            persist = AsyncMock()
            probe = AsyncMock(side_effect=None if success else Exception(OPTIONS["nextcloud_password"]))
            setup = create_setup(validate_options(OPTIONS), persist=persist, probe=probe, ingress_check=lambda _: True)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=setup), base_url="http://setup") as client:
                csrf = (await client.get("/status")).json()["csrf"]
                self.assertEqual((await client.post("/mcp-token")).status_code, 403)
                headers = {"X-Setup-CSRF": csrf}
                self.assertEqual((await client.post("/mcp-token", headers=headers)).json()["token"], OPTIONS["mcp_token"])
                data = {key: OPTIONS[key] for key in ("nextcloud_url", "nextcloud_user", "nextcloud_password")}
                response = await client.post("/connection", headers=headers, json=data)
                self.assertEqual(response.status_code, 200 if success else 400)
                self.assertNotIn(OPTIONS["nextcloud_password"], response.text)
                if success:
                    persist.assert_awaited_once_with(data, replace=True)
                    self.assertTrue((await client.get("/status")).json()["restart_required"])
                else:
                    persist.assert_not_awaited()
    async def test_supervisor_options_merge_and_verification(self):
        saved = {"permissions": "read", "unrelated": "keep"}
        def handler(request):
            self.assertEqual(request.headers["authorization"], "Bearer supervisor-secret")
            if request.method == "POST":
                saved.update(json.loads(request.content)["options"])
            return httpx.Response(200, json={"result": "ok", "data": {"options": dict(saved)}})
        await persist_options({"mcp_token": "a" * 64}, token="supervisor-secret", transport=httpx.MockTransport(handler))
        self.assertEqual(saved["unrelated"], "keep")
        self.assertEqual(saved["mcp_token"], "a" * 64)
    def test_config_no_retries(self):
        config = upstream_config(validate_options(OPTIONS))
        self.assertTrue(config.is_app_password)
        self.assertEqual(config.retry_max, 0)
        self.assertEqual(config.upload_root, "")
        self.assertEqual(config.permission_level.value, "read")
    def test_invalid_options(self):
        for extra in ({"nextcloud_url": "http://cloud.example"}, {"nextcloud_url": "https://user:secret@cloud.example"}, {"nextcloud_url": "https://cloud.example?secret=x"}, {"permissions": "edit"}, {"mcp_token": "short"}, {"allowed_origins": ["https://example.org/"]}):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                validate_options({**OPTIONS, **extra})
