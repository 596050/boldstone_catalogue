# Cloudflare Worker WebSocket Relay (Colab -> Worker)

This is a **custom tunnel** pattern for Google Colab when inbound connections are blocked:

- A Cloudflare **Durable Object** accepts a **WebSocket** connection from Colab (outbound).
- The Worker exposes HTTP endpoints like:
  - `https://<your-worker>.workers.dev/ollama/*` → forwarded to Colab `http://127.0.0.1:11434/*`
  - `https://<your-worker>.workers.dev/gliner/*` → forwarded to Colab `http://127.0.0.1:8000/*`
- Each HTTP request is serialized to JSON, sent down the WebSocket to Colab, executed locally, and the response is sent back.

## Deploy

Prereqs:

- A Cloudflare account
- `wrangler` installed (`npm i -g wrangler`)
- `CLOUDFLARE_API_TOKEN` set (recommended) or `wrangler login`

From this directory:

```bash
wrangler deploy
wrangler secret put AUTH_TOKEN
```

## Connect from Colab

Your Colab notebook should open:

`wss://<your-worker>.workers.dev/connect?token=<AUTH_TOKEN>`

Once connected, you can call:

```bash
curl -H "Authorization: Bearer <AUTH_TOKEN>" https://<your-worker>.workers.dev/gliner/health
```

