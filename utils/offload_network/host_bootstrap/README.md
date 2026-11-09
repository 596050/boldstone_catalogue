# host_bootstrap/ — isolated remote-machine setup kit

This directory holds everything needed to onboard a fresh Windows host into
the fleet-offload cluster. It is intentionally separate from the rest of
`utils/offload_network/` because:

- Nothing in here imports from sibling scripts. The only deps are the host's
  OS + a working SSH connection.
- It is run ONCE per host (or per recovery), then forgotten.
- It contains its own networking fallbacks (Tailscale + WireGuard) so a new
  host can be onboarded without depending on the rest of the cluster.

## Layout

```
host_bootstrap/
├── README.md                          (this file)
├── setup_windows_host.ps1             (the main 9-phase Windows installer)
├── setup_windows_host_macside.sh      (Mac-side companion — ssh-keygen + paste prompt)
├── enable_ssh_scan_amd64_new.ps1      (focused OpenSSH-only kit; useful for hosts
│                                       that already have everything else)
├── bootstrap_windows.ps1              (legacy minimal bootstrap; superseded by
│                                       setup_windows_host.ps1)
├── install_tailscale_windows.ps1      (Tailscale onboarding)
├── diagnose_tailscale.ps1             (troubleshoot Tailscale state)
├── diagnose_wintun_load.ps1           (troubleshoot Wintun driver — the
│                                       blocker that delayed scan-new for days)
├── fix_wintun_conflict.ps1            (manual Wintun cleanup script)
└── wg_fallback/                       (WireGuard hub-and-spoke alternative
                                        if Tailscale ever becomes unavailable)
    ├── README.md
    ├── install_wireguard_mac.sh
    ├── install_wireguard_windows.ps1
    └── wg-mesh-bootstrap.sh
```

## Standard workflow (new host)

1. From Mac: `host_bootstrap/setup_windows_host_macside.sh <new-host-alias>`
   - Generates a dedicated SSH keypair at `~/.ssh/id_ed25519_<alias>`
   - Prints what to paste into elevated PowerShell on the target

2. On the new host (RDP / AnyDesk / console, elevated PowerShell):
   ```powershell
   powershell -ExecutionPolicy Bypass -File setup_windows_host.ps1 `
       -SshPubKey '<pasted-pubkey>' -TailscaleAuthKey '<tsk-...>'
   ```

3. After it succeeds, on Mac:
   - Confirm SSH works: `ssh <alias> hostname`
   - Push the repo: `python3 utils/offload_network/fleet.py sync <alias>`
   - Re-run the .ps1 (Phase 9 builds `libemd.dll` once repo is synced)
   - Add the host to `utils/offload_network/hosts.json`

## When SSH-by-Tailscale fails

`enable_ssh_scan_amd64_new.ps1` is a focused subset for hosts that need ONLY
OpenSSH + authorized_keys + firewall (no repo, no Python, no MSYS2). Useful
when you've got everything else but lost SSH access.

If Tailscale itself is the problem (Wintun driver conflict, etc.) try the
`wg_fallback/` WireGuard kit — it's been pre-staged on all current hosts.

## Invariant

**No script in this directory imports from sibling Python code.** It's a
self-contained kit so a host with NO existing fleet-offload footprint can be
bootstrapped from zero. Don't add `from lib.remote import ps` or
`from fleet import state` here.
