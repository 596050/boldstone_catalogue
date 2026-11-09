# External machine connection

For a public HTTPS address with token-authorized requesters and no SSH relay,
see the separate [Cloudflare connector](cloudflare/README.md).

This directory contains a small, dependency-free supervisor for connecting a
TCP service on an external Linux, Windows, or macOS machine back to the source
machine through a public SSH relay (a small VPS, for example).

The relay is an address both machines can reach. Traffic remains encrypted by
SSH, and the forwarded service binds only to loopback on the relay and source.
It is not directly exposed to the internet.

## Requirements

- Python 3.9 or newer on both machines.
- OpenSSH Client (`ssh`) on both machines.
- An account and SSH key accepted by a public SSH server.
- TCP forwarding enabled on that SSH server (`AllowTcpForwarding yes`).

Copy only this directory to the external machine if the repository itself is
not needed there. Use a dedicated, restricted relay account and key.

## Run

Suppose the external service listens at `127.0.0.1:8000`, the relay is
`tunnel@example.net`, and relay port `41080` is available.

On the external machine:

```sh
python tunnel.py external --relay tunnel@example.net --identity /path/to/key --relay-bind-port 41080 --local-port 8000
```

On this source machine:

```sh
python tunnel.py source --relay tunnel@example.net --identity /path/to/key --relay-bind-port 41080 --local-port 8000
```

The source can then connect to `127.0.0.1:8000`. Keep both scripts running.
They reconnect after network interruptions. On Windows, use `py tunnel.py ...`
and a key path such as `C:\Users\name\.ssh\tunnel_ed25519`.

The relay host key must already be in `~/.ssh/known_hosts`. For the first
connection to a relay whose fingerprint you have independently verified, add
`--strict-host-key-checking accept-new`. Use `--dry-run` to inspect the exact
SSH command without connecting, and `--once` for service-manager supervision.

## Service-manager use

For unattended use, run the command at boot with systemd (Linux), Task
Scheduler (Windows), or launchd (macOS). Pass `--once` when the service manager
already handles restart/backoff. Do not put a private key or passphrase in the
command line; use an SSH agent or a narrowly scoped key file.

If port `8000` is already occupied on the source, select another `--local-port`.
Each external service needs a unique `--relay-bind-port` on the relay.
