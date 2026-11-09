"""Opt-in public smoke test using only a synthetic loopback service."""

import argparse
import asyncio
from collections import deque
import contextlib
import ipaddress
import os
from pathlib import Path
import secrets
import signal
import socket
import subprocess
import sys

import aiohttp
from aiohttp import web

from connect import stop_process


class FixedResolver(aiohttp.abc.AbstractResolver):
    """Explicit diagnostic override; HTTPS still verifies the real hostname."""

    def __init__(self, address):
        self.address = ipaddress.ip_address(address)

    async def resolve(self, host, port=0, family=socket.AF_INET):
        return [{"hostname": host, "host": str(self.address), "port": port,
                 "family": socket.AF_INET if self.address.version == 4 else socket.AF_INET6,
                 "proto": 0, "flags": 0}]

    async def close(self):
        pass


async def stop_connector(process):
    if process.returncode is None:
        with contextlib.suppress(ProcessLookupError):
            process.send_signal(signal.CTRL_BREAK_EVENT if os.name == "nt" else signal.SIGINT)
        try:
            await asyncio.wait_for(process.wait(), timeout=15)
        except asyncio.TimeoutError:
            await stop_process(process)


async def smoke(protocol: str, resolve_ip: str | None) -> None:
    hits = []

    async def synthetic(request):
        body = await request.read()
        hits.append((request.raw_path, request.headers.get("Authorization")))
        return web.Response(body=body or b"offload-smoke-ok")

    app = web.Application()
    app.router.add_route("*", "/{path:.*}", synthetic)
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    process = None
    pump = None
    token = secrets.token_urlsafe(32)
    logs = deque(maxlen=15)
    try:
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        origin = f"http://127.0.0.1:{runner.addresses[0][1]}"
        options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {}
        process = await asyncio.create_subprocess_exec(
            sys.executable, str(Path(__file__).with_name("connect.py")), "--url", origin,
            "--once", "--startup-timeout", "70", "--protocol", protocol,
            env={**os.environ, "OFFLOAD_ACCESS_TOKEN": token},
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, **options,
        )
        public_url = None
        ready = asyncio.Event()

        async def read_logs():
            nonlocal public_url
            async for raw in process.stdout:
                line = raw.decode(errors="replace").strip().replace(token, "[redacted]")
                logs.append(line)
                if line.startswith("PUBLIC_URL="):
                    public_url = line.split("=", 1)[1]
                if line.startswith("Tunnel connected."):
                    ready.set()

        pump = asyncio.create_task(read_logs())
        await asyncio.wait_for(ready.wait(), timeout=75)
        if not public_url:
            raise RuntimeError("cloudflared connected without reporting a public URL")
        print(f"Public tunnel connected to the synthetic service: {public_url}", flush=True)
        if resolve_ip:
            print(f"Test client DNS override: {resolve_ip}; hostname/TLS verification remains enabled.", flush=True)
        connector = aiohttp.TCPConnector(resolver=FixedResolver(resolve_ip) if resolve_ip else None)
        async with aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=10)) as client:
            # Allow initial DNS/edge propagation, but never accept an unauthenticated success.
            for attempt in range(20):
                try:
                    async with client.get(public_url + "/health") as response:
                        status = response.status
                        await response.read()
                    if status == 401:
                        break
                    if status < 500:
                        raise RuntimeError(f"Unexpected unauthenticated response: {status}")
                except (aiohttp.ClientConnectorError, asyncio.TimeoutError):
                    if attempt == 19:
                        raise
                await asyncio.sleep(2)
            else:
                raise RuntimeError("Public endpoint did not become reachable")
            assert hits == [], "Unauthenticated traffic reached the service"
            async with client.get(public_url + "/health", headers={"Authorization": "Bearer wrong"}) as response:
                assert response.status == 401, response.status
                await response.read()
            assert hits == [], "An incorrect token reached the service"
            payload = b"offload binary smoke\x00\xff" * 256
            async with client.post(
                public_url + "/echo?source=smoke", data=payload,
                headers={"Authorization": "Bearer " + token},
            ) as response:
                assert response.status == 200, response.status
                assert await response.read() == payload, "Payload changed in transit"
                assert response.headers["Cache-Control"] == "no-store"
            assert hits == [("/echo?source=smoke", None)], hits
        # Exercise the connector's graceful signal handling, not just forced cleanup.
        await stop_connector(process)
        assert process.returncode == 0, process.returncode
        print("PASS: public HTTPS, missing/wrong token -> 401, authorized binary POST -> 200; token stripped.")
        print("Synthetic service and test tunnel stopped.")
    except Exception:
        print("Recent connector output:\n" + "\n".join(logs), file=sys.stderr)
        raise
    finally:
        if process:
            await stop_connector(process)
        if pump:
            pump.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await pump
        await runner.cleanup()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="required: publish a temporary synthetic service")
    parser.add_argument("--protocol", choices=("auto", "http2", "quic"), default="auto")
    parser.add_argument("--resolve-ip", type=ipaddress.ip_address,
                        help="explicit test-only DNS override using an independently resolved Cloudflare edge IP")
    args = parser.parse_args()
    if not args.live:
        parser.error("pass --live to run the public test")
    asyncio.run(smoke(args.protocol, str(args.resolve_ip) if args.resolve_ip else None))
