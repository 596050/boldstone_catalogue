#!/bin/bash
# Companion to setup_windows_host.ps1 -- everything that has to happen on the
# Mac side to bring up a new Windows host.
#
# Usage:
#   utils/offload_network/setup_windows_host_macside.sh <host-alias>
#
# What it does:
#   1. Generate a dedicated ed25519 SSH key for the new host (~/.ssh/id_ed25519_<host>)
#   2. Print the pubkey + the proven Tailscale auth-key path so you can plug them
#      into the AnyDesk PowerShell paste of setup_windows_host.ps1
#   3. After you confirm setup_windows_host.ps1 finished, this script:
#      - invalidates any stale SSH ControlMaster for the host
#      - smoke-tests ssh <host> python -V
#      - adds an SSH config stanza
#      - prompts you to update hosts.json
#
# Required before running:
#   - You have AnyDesk into the new host
#   - You have a reusable Tailscale auth key (or are skipping Tailscale)

set -euo pipefail

if [ "$#" -lt 1 ]; then
    echo "Usage: $0 <host-alias>  (e.g.  $0 scan-new)" >&2
    exit 1
fi

HOST=$1
KEY_FILE="$HOME/.ssh/id_ed25519_$HOST"

# 1. Generate the per-host key if missing
if [ ! -f "$KEY_FILE" ]; then
    echo "[1/4] generating dedicated SSH key for $HOST"
    ssh-keygen -t ed25519 -N "" -f "$KEY_FILE" -C "mac-to-${HOST}-$(date +%Y-%m-%d)"
else
    echo "[1/4] $KEY_FILE already exists -- reusing"
fi

PUB=$(cat "$KEY_FILE.pub")

# 2. Show the values to paste into AnyDesk PowerShell
echo
echo "[2/4] paste these into AnyDesk elevated PowerShell on $HOST:"
echo
cat <<EOF
\$key = '$PUB'
# IF you have a Tailscale reusable auth key, paste it as \$tsk:
\$tsk = 'tskey-auth-...REPLACE...'

# Download + run the comprehensive setup
Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/<your-repo>/fleet-offload/main/utils/offload_network/setup_windows_host.ps1' -OutFile \$env:TEMP\setup_windows_host.ps1
powershell -ExecutionPolicy Bypass -File \$env:TEMP\setup_windows_host.ps1 -SshPubKey \$key -TailscaleAuthKey \$tsk
EOF
echo
echo "OR, if not serving the script from a repo, scp it instead:"
echo "  scp utils/offload_network/setup_windows_host.ps1 <user>@<temp-IP>:C:/temp/"
echo "  then on the remote:  powershell -ExecutionPolicy Bypass -File C:\\temp\\setup_windows_host.ps1 -SshPubKey '...' -TailscaleAuthKey '...'"

# 3. Wait for the user
echo
read -r -p "[3/4] Press Enter AFTER setup_windows_host.ps1 finished on the remote: " _

# Invalidate any stale SSH control-master so new sessions pick up env changes
ssh -O exit "$HOST" 2>/dev/null || true
rm -f "$HOME/.ssh/cm/"*"@${HOST}:"* 2>/dev/null || true

# Smoke-test
echo
echo "[4/4] smoke test ssh $HOST python -V ..."
if ! ssh -o BatchMode=yes -o ConnectTimeout=15 "$HOST" 'python -V; py -3.12 -V; "host=$env:COMPUTERNAME"' 2>&1; then
    echo "FAIL -- did the SSH config entry exist? Maybe add one:"
    cat <<EOF
Host $HOST
    HostName <tailnet-magicdns-name>      # e.g. scan-amd64-new
    User <remote-user>
    IdentityFile $KEY_FILE
EOF
    exit 1
fi

echo
echo "OK. To finish:"
echo "  1. Edit utils/offload_network/hosts.json -- add a stanza for $HOST."
echo "  2. Run:  utils/offload_network/fleet.py sync $HOST"
echo "  3. Run:  utils/offload_network/fleet.py status"
