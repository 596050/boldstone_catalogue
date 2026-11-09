• Yes. We can use SSH to administer the Mac mini, then run the repository’s authenticated compute worker
  through a Cloudflare Tunnel. The mini initiates the outbound connection, so this does not require router port
  forwarding. Cloudflare documentation
  (https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/)

  First, set up SSH access.

  1. On the Mac mini, open System Settings → General → Sharing → Remote Login. Allow access for your account.
     The information panel shows the correct SSH username. You can also obtain it in Terminal:

     whoami

     Apple’s Remote Login instructions
     (https://support.apple.com/guide/mac-help/allow-a-remote-computer-to-access-your-mac-mchlp1066/mac)

  2. On this MacBook, copy its existing public key:

     pbcopy < /Users/tprice/.ssh/id_rsa.pub

     This is the public half of your existing 4096-bit RSA key. Keep id_rsa, the private half, on this MacBook.

  3. On the Mac mini, open Terminal under the account you intend to use:

     mkdir -p ~/.ssh
     chmod 700 ~/.ssh
     nano ~/.ssh/authorized_keys

     Paste the public key as one complete line, preserving any existing keys. Save with Control-O, Enter, then
     exit with Control-X.

     chmod 600 ~/.ssh/authorized_keys

  4. Back on this MacBook, replace MINIUSER with the username from step 1:

     ssh -i ~/.ssh/id_rsa MINIUSER@toms-mac-mini.local

     If your private key has a passphrase, load it into your SSH agent from Terminal:

     ssh-add --apple-use-keychain ~/.ssh/id_rsa

  For the internet compute connection, we already have the required software in offload_service (utils/
  offload_network/offload_service/README.md). It provides authentication, a durable queue, isolated Docker
  execution, and verified result downloads.

  The installation would work as follows:

  1. Install the prerequisites on the mini: Python 3.10+, cloudflared, and Docker Desktop for its processor
     (https://docs.docker.com/desktop/setup/install/mac-install/). Start Docker Desktop.

     With Homebrew available:

     brew install python cloudflared

  2. Transfer a packaged copy of utils/offload_network over SSH, install it into a dedicated virtual
     environment, and initialize a worker. From the transferred package directory:

     python3 -m venv ~/offload-venv
     ~/offload-venv/bin/python -m pip install ".[cloudflare]"

     docker pull python:3.12-slim

     ~/offload-venv/bin/research-offload init-worker \
       --dir ~/offload-worker \
       --image python:3.12-slim

     This creates a private ~/offload-worker/access-token. The initial image and limits suit a connectivity
     test; your research jobs need their declared dependencies, datasets, and appropriate resource limits.

  3. Create a stable named tunnel using a domain in your Cloudflare account:

     cloudflared tunnel login
     cloudflared tunnel create mac-mini-compute
     cloudflared tunnel route dns mac-mini-compute compute.YOUR_DOMAIN

     These commands create the tunnel credentials and DNS route. Cloudflare setup
     (https://developers.cloudflare.com/tunnel/features/locally-managed-tunnels/create-local-tunnel/)

  4. Start the existing worker and authenticated connector, substituting the tunnel UUID and hostname:

     ~/offload-venv/bin/offload-worker serve \
       --config ~/offload-worker/worker.json \
       --tunnel \
       --tunnel-args \
       --tunnel-id TUNNEL_UUID \
       --credentials-file ~/.cloudflared/TUNNEL_UUID.json \
       --hostname compute.YOUR_DOMAIN

     The requester authenticates with the worker’s access token. That token is separate from the Cloudflare
     tunnel credentials and grants permission to submit code for execution.

  For unattended operation, install this launcher as a macOS LaunchAgent with automatic restart and a startup
  check that waits for Docker. Enable Docker Desktop’s “Start Docker Desktop when you sign in” setting. This
  arrangement starts after login; it does not provide compute before login after a reboot. Docker settings
  (https://docs.docker.com/desktop/settings-and-maintenance/settings/)

  Finally, securely copy the worker token to this MacBook, register the HTTPS endpoint as mac-mini in the
  existing orchestrator, and verify an authenticated job submission and result return. New jobs can then target
  the mini; moving existing admitted jobs requires tracked resubmission.

  The next step is adding the public key on the mini and giving me its login username. That will let me carry
  out the installation remotely.
