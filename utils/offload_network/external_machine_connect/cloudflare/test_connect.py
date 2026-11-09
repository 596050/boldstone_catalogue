"""Local integration tests; these never open a public tunnel."""

import argparse
import asyncio
import contextlib
import gzip
import io
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import aiohttp
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from multidict import CIMultiDict
from yarl import URL

import connect


TOKEN = "test_access_" + "a" * 32
AUTH = {"Authorization": "Bearer " + TOKEN}


class GatewayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.hits = []
        self.release_stream = asyncio.Event()

        async def origin(request):
            body = await request.read()
            self.hits.append((request.raw_path, dict(request.headers), body))
            if request.path == "/redirect":
                return web.Response(status=302, headers={"Location": "/private"})
            if request.path == "/cookies":
                return web.Response(headers=CIMultiDict([
                    ("Set-Cookie", "a=1; Path=/"), ("Set-Cookie", "b=2; Path=/"),
                ]))
            if request.path == "/gzip":
                return web.Response(body=gzip.compress(b"payload"), headers={"Content-Encoding": "gzip"})
            if request.path == "/stream":
                response = web.StreamResponse(headers={"Content-Type": "application/octet-stream"})
                await response.prepare(request)
                await response.write(b"first\n")
                await self.release_stream.wait()
                await response.write(b"last\n")
                return response
            if request.path == "/slow":
                await self.release_stream.wait()
                return web.Response(text="done")
            if request.path == "/head":
                return web.Response(body=b"12345")
            return web.Response(status=201, body=body or b"ok")

        app = web.Application(handler_args={"auto_decompress": False})
        app.router.add_route("*", "/{path:.*}", origin)
        self.origin = TestServer(app)
        await self.origin.start_server()
        self.addAsyncCleanup(self.origin.close)
        self.client = await self.gateway()

    async def asyncTearDown(self):
        self.release_stream.set()

    async def gateway(self, **kwargs):
        app = connect.create_app(str(self.origin.make_url("/")), TOKEN, **kwargs)
        client = TestClient(TestServer(app), cookie_jar=aiohttp.DummyCookieJar(), auto_decompress=False)
        await client.start_server()
        self.addAsyncCleanup(client.close)
        return client

    async def test_unauthorized_requests_never_reach_service(self):
        for headers in ({}, {"Authorization": "Bearer wrong"}, {"Authorization": "Bearer " + "é" * 43},
                        CIMultiDict([("Authorization", "Bearer " + TOKEN), ("Authorization", "Bearer " + TOKEN)])):
            async with self.client.post("/job", headers=headers, data=b"must not be delivered") as response:
                self.assertEqual(response.status, 401)
                self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(self.hits, [])

    async def test_post_bytes_path_and_status_are_preserved_and_token_is_stripped(self):
        payload = b"\x00\xffbinary\n" * 100
        path = "/job%2Fpart?x=%2F&x=a+b"
        async with self.client.post(URL(path, encoded=True), headers=AUTH, data=payload) as response:
            self.assertEqual(response.status, 201)
            self.assertEqual(await response.read(), payload)
            self.assertEqual(response.headers["Cache-Control"], "no-store")
        raw_path, headers, body = self.hits[0]
        self.assertEqual(raw_path, path)
        self.assertEqual(body, payload)
        self.assertNotIn("Authorization", headers)

    async def test_separate_header_preserves_service_authorization(self):
        client = await self.gateway(auth_header="X-Offload-Token")
        async with client.get("/", headers={"X-Offload-Token": TOKEN, "Authorization": "Bearer origin-secret"}) as response:
            self.assertEqual(response.status, 201)
        self.assertNotIn("X-Offload-Token", self.hits[0][1])
        self.assertEqual(self.hits[0][1]["Authorization"], "Bearer origin-secret")

    async def test_redirects_return_to_client_without_fetching_destination(self):
        async with self.client.get("/redirect", headers=AUTH, allow_redirects=False) as response:
            self.assertEqual(response.status, 302)
            self.assertEqual(response.headers["Location"], "/private")
        self.assertEqual(len(self.hits), 1)

    async def test_cookies_are_forwarded_but_not_shared_between_requesters(self):
        async with self.client.get("/cookies", headers=AUTH) as response:
            self.assertEqual(len(response.headers.getall("Set-Cookie")), 2)
        async with self.client.get("/", headers=AUTH) as response:
            await response.read()
        self.assertNotIn("Cookie", self.hits[-1][1])

    async def test_encoded_upload_and_response_are_not_silently_decompressed(self):
        payload = gzip.compress(b"encoded upload")
        async with self.client.post("/", headers={**AUTH, "Content-Encoding": "gzip"}, data=payload) as response:
            self.assertEqual(await response.read(), payload)
        self.assertEqual(self.hits[0][2], payload)
        async with self.client.get("/gzip", headers=AUTH) as response:
            self.assertEqual(gzip.decompress(await response.read()), b"payload")
            self.assertEqual(response.headers["Content-Encoding"], "gzip")

    async def test_response_streams_before_upstream_finishes(self):
        async with self.client.get("/stream", headers=AUTH) as response:
            first = await asyncio.wait_for(response.content.readline(), 2)
            self.assertEqual(first, b"first\n")
            self.release_stream.set()
            self.assertEqual(await response.read(), b"last\n")

    async def test_head_has_no_body_and_preserves_length(self):
        async with self.client.head("/head", headers=AUTH) as response:
            self.assertEqual(response.headers["Content-Length"], "5")
            self.assertEqual(await response.read(), b"")

    async def test_oversized_fixed_and_chunked_uploads_never_reach_service(self):
        client = await self.gateway(max_body=32)

        async def chunks():
            yield b"x" * 20
            yield b"x" * 20

        for data in (b"x" * 40, chunks()):
            async with client.post("/", headers=AUTH, data=data) as response:
                self.assertEqual(response.status, 413)
        self.assertEqual(self.hits, [])

    async def test_connection_nominated_headers_are_removed(self):
        async with self.client.get("/", headers={**AUTH, "Connection": "X-Private", "X-Private": "remove"}) as response:
            await response.read()
        self.assertNotIn("X-Private", self.hits[0][1])

    async def test_websockets_and_trace_are_explicitly_rejected(self):
        async with self.client.get("/", headers={**AUTH, "Upgrade": "websocket", "Connection": "Upgrade"}) as response:
            self.assertEqual(response.status, 501)
        async with self.client.request("TRACE", "/", headers=AUTH) as response:
            self.assertEqual(response.status, 405)
        self.assertEqual(self.hits, [])

    async def test_upstream_timeout_and_failure_have_gateway_errors(self):
        client = await self.gateway(timeout=0.05)
        async with client.get("/slow", headers=AUTH) as response:
            self.assertEqual(response.status, 504)
        self.release_stream.set()
        await self.origin.close()
        async with self.client.get("/", headers=AUTH) as response:
            self.assertEqual(response.status, 502)

    async def test_concurrent_limit_rejects_excess_work(self):
        client = await self.gateway(max_concurrent=1)
        async with client.get("/stream", headers=AUTH) as first:
            await first.content.readline()
            async with client.get("/", headers=AUTH) as second:
                self.assertEqual(second.status, 503)
            self.release_stream.set()
            await first.read()
        self.assertEqual(len(self.hits), 1)


class ConfigurationTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("cloudflared"), "cloudflared is not installed")
    def test_named_ingress_is_accepted_by_cloudflared(self):
        with tempfile.TemporaryDirectory(prefix="offload named test ") as directory:
            config = Path(directory) / "config.yml"
            args = connect.parse_args([
                "--url", "http://127.0.0.1:8000", "--tunnel-id", "11111111-2222-3333-4444-555555555555",
                "--credentials-file", str(Path(directory) / "credentials.json"), "--hostname", "worker.example.com",
            ])
            config.write_text(json.dumps(connect.tunnel_config(args, "http://127.0.0.1:8765")), encoding="utf-8")
            result = subprocess.run(
                [shutil.which("cloudflared"), "tunnel", "--config", str(config), "ingress", "validate"],
                env=connect.child_environment(), capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_only_loopback_origins_are_accepted(self):
        self.assertEqual(connect.local_url("http://localhost:8000"), "http://127.0.0.1:8000")
        self.assertEqual(connect.local_url("http://[::1]:8000"), "http://[::1]:8000")
        for value in ("http://example.com", "http://127.0.0.1@evil.example", "file:///tmp/file",
                      "http://127.0.0.1/base", "http://127.0.0.1/?token=x", "http://0.0.0.0:8000"):
            with self.assertRaises(argparse.ArgumentTypeError):
                connect.local_url(value)

    def test_token_persists_with_private_permissions(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            path = Path(directory) / "token"
            first = connect.load_token(path)
            self.assertEqual(first, connect.load_token(path))
            self.assertEqual(len(first), 43)
            if os.name != "nt":
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                path.chmod(0o644)
                with self.assertRaises(ValueError):
                    connect.load_token(path)

    def test_empty_environment_token_fails_closed(self):
        with patch.dict(os.environ, {connect.TOKEN_ENV: ""}):
            with self.assertRaises(ValueError):
                connect.load_token(Path("unused"))

    def test_child_cannot_inherit_a_different_tunnel_or_the_requester_token(self):
        with patch.dict(os.environ, {connect.TOKEN_ENV: TOKEN, "TUNNEL_TOKEN": "secret", "TUNNEL_URL": "http://unsafe", "PATH": "keep"}):
            child = connect.child_environment()
            self.assertNotIn(connect.TOKEN_ENV, child)
            self.assertNotIn("TUNNEL_TOKEN", child)
            self.assertNotIn("TUNNEL_URL", child)
            self.assertEqual(child["PATH"], "keep")


class SupervisorTests(unittest.IsolatedAsyncioTestCase):
    async def test_idle_connector_exits_on_signal_and_reaps_its_child(self):
        app = web.Application()
        server = TestServer(app)
        await server.start_server()
        self.addAsyncCleanup(server.close)
        fake_child = "import time; print('Registered tunnel connection', flush=True); time.sleep(10)"
        program = (
            f"import sys; sys.path.insert(0, {str(Path(connect.__file__).parent)!r}); import connect; "
            f"connect.tunnel_command = lambda *args: [sys.executable, '-c', {fake_child!r}]; "
            f"raise SystemExit(connect.main(['--url', {str(server.make_url('/'))!r}, "
            "'--cloudflared', sys.executable, '--once']))"
        )
        options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {}
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-c", program, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
            env={**os.environ, connect.TOKEN_ENV: TOKEN}, **options,
        )
        try:
            while True:
                line = await asyncio.wait_for(process.stdout.readline(), timeout=5)
                self.assertTrue(line, "Connector exited before it was ready")
                if line.startswith(b"Tunnel connected."):
                    break
            process.send_signal(signal.CTRL_BREAK_EVENT if os.name == "nt" else signal.SIGINT)
            # The child would sleep for ten seconds; prompt EOF proves it was terminated/reaped.
            await asyncio.wait_for(process.communicate(), timeout=3)
            self.assertEqual(process.returncode, 0)
        finally:
            await connect.stop_process(process)

    async def test_once_propagates_process_failure(self):
        args = connect.parse_args(["--url", "http://127.0.0.1:8000", "--once"])
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            result = await connect.supervise(args, [sys.executable, "-c", "raise SystemExit(7)"], TOKEN, asyncio.Event())
        self.assertEqual(result, 7)

    async def test_startup_timeout_terminates_child(self):
        args = connect.parse_args(["--url", "http://127.0.0.1:8000", "--startup-timeout", "0.2"])
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            result = await asyncio.wait_for(connect.supervise(
                args, [sys.executable, "-c", "import time; time.sleep(30)"], TOKEN, asyncio.Event()
            ), timeout=4)
        self.assertEqual(result, 1)

    async def test_stop_interrupts_backoff(self):
        args = connect.parse_args(["--url", "http://127.0.0.1:8000", "--reconnect-delay", "60"])
        stopping = asyncio.Event()
        asyncio.get_running_loop().call_later(0.3, stopping.set)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            result = await asyncio.wait_for(connect.supervise(
                args, [sys.executable, "-c", "raise SystemExit(7)"], TOKEN, stopping
            ), timeout=3)
        self.assertEqual(result, 0)


if __name__ == "__main__":
    unittest.main()
