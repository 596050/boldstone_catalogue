# Cloudflare public HTTPS connector

Run `connect.py` on the external machine to give a local HTTP service a public
HTTPS address. The source machine, or any other requester, can call that address
using the shared access token. Requesters need no tunnel software or SSH account.

```text
Requester -- HTTPS + access token --> Cloudflare
                                         |
                              outbound tunnel connection
                                         |
                      external machine: authentication gateway
                                         |
                                local HTTP service
```

Default mode creates a random `https://...trycloudflare.com` address without a
Cloudflare account, domain, or VPS. The machine must already be running the HTTP
service you want to expose (for example, an API on `127.0.0.1:8000`). This script
forwards HTTP requests; it does not install a compute worker or execute jobs itself.

## Install once on the external machine

Requires Python **3.10+**, the dependencies in `requirements.txt`, and
[`cloudflared`](https://developers.cloudflare.com/tunnel/downloads/).
Copy this subdirectory to the external machine, excluding `.runtime` and `.venv`.

Linux/macOS, from this directory:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

On macOS, install the tunnel client with `brew install cloudflared`.
On Linux, use the [Cloudflare package repository](https://pkg.cloudflare.com/index.html)
or the matching binary from the downloads page. Put it on `PATH` or pass its
absolute path with `--cloudflared`.

Windows PowerShell, from this directory:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Download the Windows executable from the same Cloudflare downloads page. Put it
on `PATH` as `cloudflared.exe`, or add
`--cloudflared 'C:\Tools\cloudflared.exe'` to the commands below. No virtual
environment activation or PowerShell execution-policy change is necessary.

## Start the connector

With your service running at `127.0.0.1:8000`, on Linux/macOS:

```sh
.venv/bin/python connect.py --url http://127.0.0.1:8000
```

On Windows:

```powershell
.\.venv\Scripts\python.exe connect.py --url http://127.0.0.1:8000 --cloudflared 'C:\Tools\cloudflared.exe'
```

The script creates a random token in `.runtime/access-token.txt` on first run,
reuses it on subsequent runs, and prints `PUBLIC_URL=https://...trycloudflare.com`.
Wait for `Tunnel connected` before making requests; new DNS may take a few seconds
or longer to become available depending on the resolver. The token is never
printed in connector logs. The default token location is relative to the script,
regardless of your working directory.

Keep the command running. Ctrl+C stops the tunnel and gateway. The script
restarts `cloudflared` after process exit with increasing delays (up to 60 seconds);
each Quick Tunnel process restart gets a **new URL**, printed again. `cloudflared`
also handles transient network reconnection internally.

To check executable discovery, configuration and the local TCP listener without
opening a public tunnel or generating a token, add `--check`.

## Call it from the source or any other machine

Transfer `.runtime/access-token.txt` securely to each authorized requester, for
example as `access-token.txt`. The same shared token grants access to every HTTP
path and supported method of the selected service.

Linux/macOS (replace the example URL with the printed one):

```sh
OFFLOAD_TOKEN="$(tr -d '\r\n' < access-token.txt)"
curl --fail-with-body -H "Authorization: Bearer $OFFLOAD_TOKEN" https://example.trycloudflare.com/health
```

Windows PowerShell:

```powershell
$offloadToken = (Get-Content -Raw .\access-token.txt).Trim()
Invoke-RestMethod -Uri 'https://example.trycloudflare.com/health' -Headers @{ Authorization = "Bearer $offloadToken" }
```

Use a route your local service actually provides; `/health` is only an example.
Missing, incorrect, or duplicate token headers return `401` before the local
service receives the request. Tokens in URLs/query strings are not accepted.
A browser address bar alone cannot supply the token; use an HTTP client that can
set headers. This is shared-token API access, not an interactive sign-in page.

The gateway consumes the `Authorization` header. If your application needs its
own `Authorization` header, start with `--auth-header X-Offload-Token` and send
`X-Offload-Token: <access token>` separately; the application header then passes
through unchanged. This mode also works with Cloudflare Access configurations
that consume the `Authorization` header upstream.

You can provide `OFFLOAD_ACCESS_TOKEN` in the connector environment instead of a
file (32-256 letters, digits, `_` or `-`), or select `--token-file /private/path`.
Use a randomly generated value. To revoke the existing shared token, stop the
connector, move its token file aside, then restart and distribute the new token.
On POSIX the file is created with mode `600`; on Windows protect it with your
user-profile NTFS permissions. Do not commit tokens or tunnel credentials.

## Stable hostname using an existing Cloudflare account

A [locally managed named tunnel](https://developers.cloudflare.com/tunnel/advanced/local-management/create-local-tunnel/)
uses your own domain and survives connector restarts. First create a tunnel and
DNS route using Cloudflare's setup flow, for example on your administration machine:

```sh
cloudflared tunnel login
cloudflared tunnel create external-worker
cloudflared tunnel route dns external-worker worker.example.com
```

Record the resulting tunnel UUID and securely copy **that tunnel's** credentials
JSON to the external machine. Its account-wide `cert.pem` is not needed to run
this connector. These commands require a domain configured in your Cloudflare
account and create real account/DNS resources.

Start the external machine's connector with all three named-tunnel options:

```sh
.venv/bin/python connect.py --url http://127.0.0.1:8000 \
  --tunnel-id 11111111-2222-3333-4444-555555555555 \
  --credentials-file /private/path/tunnel-credentials.json \
  --hostname worker.example.com
```

On Windows use `.\.venv\Scripts\python.exe` and Windows paths; put the options
on one line. The UUID must match the supplied credentials and existing DNS route.
This mode uses locally managed credentials JSON, not a dashboard connector token.
The script creates an isolated temporary configuration pointing the hostname to
the authenticated gateway, with a final `404` rule for unmatched hostnames.
It does not edit your existing Cloudflare configuration, create DNS records, or
provision an account. Caller tokens are separate from the tunnel credential.

## Behavior and limits

- HTTPS terminates at Cloudflare; the outbound tunnel is encrypted. Cloudflare
  can process HTTP traffic. Gateway-to-service traffic uses loopback HTTP by
  default; HTTPS origins verify certificates normally.
- The gateway binds only to `127.0.0.1` and accepts only loopback origin addresses.
  `localhost` is normalized to `127.0.0.1`; use `[::1]` for an IPv6-only service.
- HTTP GET, HEAD, POST, PUT, PATCH, DELETE and OPTIONS are supported. Response
  bodies stream; uploads are buffered, limited to 16 MiB and 16 concurrent
  requests by default. Adjust with `--max-body-mib` and `--max-concurrent`.
- Redirects and cookies are returned to the caller; the gateway does not follow
  redirects, rewrite application URLs/cookie domains, or share client cookies.
  Configure your application's external URL if it emits absolute local URLs.
- Responses request `no-store` caching, including Cloudflare's CDN-specific
  header. Do not configure account cache rules that override this for the service.
- WebSockets, protocol upgrades, raw TCP/UDP, arbitrary ports, and browser CORS
  configuration are outside this HTTP connector. Unsupported upgrades return `501`.
- Cloudflare [Quick Tunnels](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/)
  have no uptime guarantee, allow at most 200 in-flight requests, and do not
  support server-sent events (SSE). Use a named tunnel for a stable URL or SSE.
  Other Cloudflare request-size and timeout limits still apply.
- `--request-timeout` controls gateway upload/upstream idle time (default 300s).
  Upstream failure/timeout returns `502`/`504`. A failure after response headers
  closes the stream so the client can detect a truncated response.
- Outbound connectivity to Cloudflare is required. If QUIC/UDP is blocked, try
  `--protocol http2` (TCP); the network must allow Cloudflare Tunnel connectivity.
  A startup that does not connect within `--startup-timeout` (120s) exits with an
  error. An allocated URL alone does not prove the tunnel is connected.
- If a connected Quick Tunnel hostname returns `NXDOMAIN`, compare the requester's
  DNS resolver with a public resolver. During validation here, normal DNS failed
  while routing to a Cloudflare edge with the original hostname/TLS verification
  succeeded. The script does not change system DNS settings.
- `--once` disables process restarts for use under systemd, launchd, or Windows
  Task Scheduler. Use absolute paths for the interpreter, script and token file.
  The script does not install an auto-start service.

## Tests

```sh
.venv/bin/python -m unittest discover -s . -p 'test_connect.py' -v
```

On Windows substitute `.\.venv\Scripts\python.exe`. Tests use temporary local
HTTP servers and simulated child processes; they do not publish a public URL.
If `cloudflared` is installed, they also validate a generated named-tunnel
configuration using its local ingress validator; no account is required.

An opt-in public test publishes **only a synthetic service**, verifies missing/
wrong tokens and an authorized binary POST, then stops the connector:

```sh
.venv/bin/python smoke_test.py --live
```

`smoke_test.py --live --resolve-ip <independently-resolved-Cloudflare-edge-IP>`
explicitly overrides DNS for the test client only. It retains the public hostname
and normal TLS certificate verification. This is a diagnostic, not proof that
normal hostname resolution works. See [VALIDATION.md](VALIDATION.md) for the
recorded results and platform coverage.
