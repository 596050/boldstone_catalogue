# Validation — 2026-09-09

Environment: macOS arm64, Python 3.14.7, aiohttp 3.14.3,
cloudflared 2026.8.3. Linux and Windows were not available for execution; their
installation commands and portable process/signal paths are supplied but are
not claimed as tested on those operating systems.

Local suite: **22 tests passed** (`python -m unittest discover -s . -p test_connect.py -v`).
Tests exercise real loopback HTTP servers, token rejection before origin
access, binary/encoded bodies, path/query preservation, HEAD, streaming,
redirects, cookie isolation, body/concurrency limits, errors, and child-process
cleanup. The named-tunnel configuration is checked by cloudflared's own local
ingress validator. No named tunnel or account/DNS resources were provisioned.

The first public Quick Tunnel connected successfully but client requests failed
at DNS resolution. The local resolver `192.168.0.1` returned `NXDOMAIN` for
`transactions-evanescence-large-plenty.trycloudflare.com`; querying `1.1.1.1`
returned `104.16.230.132` and `104.16.231.132`. A second generated hostname also
failed normal resolution during the smoke-test retry window. The cause beyond
these observed resolver responses was not established.

The initial failure cleanup exposed an idle-event-loop signal wakeup bug. Signal
handling now schedules shutdown using `loop.call_soon_threadsafe`; a regression
test checks that an idle connector exits promptly and reaps its child.

Public smoke test with an explicit test-client DNS override:

```sh
.venv/bin/python smoke_test.py --live --resolve-ip 104.16.230.132
```

Result: **PASS** through
`https://epa-organizational-relay-yamaha.trycloudflare.com`:

- Missing token: HTTP `401`; zero origin requests.
- Incorrect token: HTTP `401`; zero origin requests.
- Correct token: HTTP `200`; binary POST response matches the original bytes.
- Gateway strips the requester token before forwarding; `Cache-Control: no-store` is returned.
- SIGINT exits cleanly with status `0`; the synthetic service and tunnel stop.
- Process inspection after completion found no remaining test connector/cloudflared process.

TLS certificate/hostname verification remained enabled. This result verifies
the public routing and authentication path with a DNS override, **not** normal
DNS availability on this network. The URL above is an expired test endpoint,
not a persistent service. No real application or repository content was exposed.
