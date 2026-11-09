export interface Env {
  AUTH_TOKEN: string;
  RELAY: DurableObjectNamespace;
}

type RelayTarget = "ollama" | "gliner";

type RelayRequestMessage = {
  type: "request";
  id: string;
  target: RelayTarget;
  method: string;
  path: string;
  headers: Record<string, string>;
  body_b64?: string;
};

type RelayResponseMessage = {
  type: "response";
  id: string;
  status: number;
  headers?: Record<string, string>;
  body_b64?: string;
};

type RelayErrorMessage = {
  type: "error";
  id?: string;
  error: string;
};

function toBase64(buf: ArrayBuffer): string {
  const bytes = new Uint8Array(buf);
  const chunkSize = 0x8000;
  let binary = "";
  for (let i = 0; i < bytes.length; i += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunkSize));
  }
  return btoa(binary);
}

function fromBase64(b64: string): ArrayBuffer {
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes.buffer;
}

function stripHopByHopHeaders(headers: Headers): Record<string, string> {
  const out: Record<string, string> = {};
  headers.forEach((value, key) => {
    const k = key.toLowerCase();
    if (
      k === "host" ||
      k === "connection" ||
      k === "upgrade" ||
      k === "keep-alive" ||
      k === "proxy-authenticate" ||
      k === "proxy-authorization" ||
      k === "te" ||
      k === "trailer" ||
      k === "transfer-encoding" ||
      k === "authorization"
    ) {
      return;
    }
    if (k.startsWith("cf-")) {
      return;
    }
    out[k] = value;
  });
  return out;
}

function isAuthorizedBearer(request: Request, env: Env, url: URL): boolean {
  const header = request.headers.get("authorization") || "";
  const tokenFromHeader = header.toLowerCase().startsWith("bearer ")
    ? header.slice("bearer ".length).trim()
    : null;
  const tokenFromQuery = url.searchParams.get("token");
  const token = tokenFromHeader || tokenFromQuery;
  return Boolean(token && token === env.AUTH_TOKEN);
}

function corsHeaders() {
  return {
    "access-control-allow-origin": "*",
    "access-control-allow-methods": "GET,POST,PUT,PATCH,DELETE,OPTIONS",
    "access-control-allow-headers": "authorization,content-type",
    "access-control-max-age": "86400",
  };
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const id = env.RELAY.idFromName("default");
    const stub = env.RELAY.get(id);
    return stub.fetch(request);
  },
};

export class RelayDO implements DurableObject {
  private ws: WebSocket | null = null;
  private pending = new Map<
    string,
    {
      resolve: (msg: RelayResponseMessage) => void;
      reject: (err: Error) => void;
      timeoutId: number | null;
    }
  >();

  constructor(
    private readonly state: DurableObjectState,
    private readonly env: Env,
  ) {}

  async fetch(request: Request): Promise<Response> {
    const url = new URL(request.url);

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: corsHeaders() });
    }

    if (url.pathname === "/connect") {
      return this.handleConnect(request, url);
    }

    if (!isAuthorizedBearer(request, this.env, url)) {
      return new Response("Unauthorized", { status: 401, headers: corsHeaders() });
    }

    const route = this.parseRoute(url);
    if (!route) {
      return new Response("Not found. Use /ollama/* or /gliner/*", {
        status: 404,
        headers: corsHeaders(),
      });
    }

    if (!this.ws) {
      return new Response("No Colab client connected (WebSocket not established)", {
        status: 503,
        headers: corsHeaders(),
      });
    }

    const body = await request.arrayBuffer();
    const id = crypto.randomUUID();
    const msg: RelayRequestMessage = {
      type: "request",
      id,
      target: route.target,
      method: request.method,
      path: route.upstreamPathWithQuery,
      headers: stripHopByHopHeaders(request.headers),
      body_b64: body.byteLength ? toBase64(body) : undefined,
    };

    let relayResp: RelayResponseMessage;
    try {
      relayResp = await this.sendAndWait(msg, 600_000);
    } catch (e) {
      const err = e instanceof Error ? e.message : String(e);
      return new Response(`Upstream error: ${err}`, {
        status: 504,
        headers: corsHeaders(),
      });
    }

    const headers = new Headers(corsHeaders());
    for (const [k, v] of Object.entries(relayResp.headers ?? {})) {
      try {
        headers.set(k, v);
      } catch {
        // Some headers are restricted in Workers responses.
      }
    }

    const outBody = relayResp.body_b64 ? fromBase64(relayResp.body_b64) : null;
    return new Response(outBody ? outBody : null, {
      status: relayResp.status,
      headers,
    });
  }

  private handleConnect(request: Request, url: URL): Response {
    if (!isAuthorizedBearer(request, this.env, url)) {
      return new Response("Unauthorized", { status: 401, headers: corsHeaders() });
    }

    const upgrade = request.headers.get("upgrade") || "";
    if (upgrade.toLowerCase() !== "websocket") {
      return new Response("Expected WebSocket upgrade", {
        status: 426,
        headers: { ...corsHeaders(), upgrade: "websocket" },
      });
    }

    const pair = new WebSocketPair();
    const client = pair[0];
    const server = pair[1];
    server.accept();

    if (this.ws) {
      try {
        this.ws.close(1012, "replaced");
      } catch {}
      this.ws = null;
    }

    this.ws = server;

    server.addEventListener("message", (evt) => {
      this.onWsMessage(evt);
    });
    server.addEventListener("close", () => {
      this.onWsClose();
    });
    server.addEventListener("error", () => {
      this.onWsClose();
    });

    return new Response(null, {
      status: 101,
      webSocket: client,
    });
  }

  private onWsMessage(evt: MessageEvent): void {
    let msg: RelayResponseMessage | RelayErrorMessage | null = null;
    try {
      msg = JSON.parse(String(evt.data));
    } catch {
      return;
    }

    if (!msg || typeof msg !== "object") {
      return;
    }

    if (msg.type === "response" && typeof (msg as RelayResponseMessage).id === "string") {
      const id = (msg as RelayResponseMessage).id;
      const pending = this.pending.get(id);
      if (!pending) {
        return;
      }
      if (pending.timeoutId !== null) {
        clearTimeout(pending.timeoutId);
      }
      this.pending.delete(id);
      pending.resolve(msg as RelayResponseMessage);
      return;
    }

    if (msg.type === "error") {
      const id = (msg as RelayErrorMessage).id;
      if (!id) {
        return;
      }
      const pending = this.pending.get(id);
      if (!pending) {
        return;
      }
      if (pending.timeoutId !== null) {
        clearTimeout(pending.timeoutId);
      }
      this.pending.delete(id);
      pending.reject(new Error((msg as RelayErrorMessage).error));
    }
  }

  private onWsClose(): void {
    this.ws = null;
    for (const [id, pending] of this.pending.entries()) {
      if (pending.timeoutId !== null) {
        clearTimeout(pending.timeoutId);
      }
      pending.reject(new Error("WebSocket closed"));
      this.pending.delete(id);
    }
  }

  private sendAndWait(msg: RelayRequestMessage, timeoutMs?: number): Promise<RelayResponseMessage> {
    if (!this.ws) {
      return Promise.reject(new Error("WebSocket not connected"));
    }
    const payload = JSON.stringify(msg);
    return new Promise((resolve, reject) => {
      let timeoutId: number | null = null;
      if (timeoutMs && timeoutMs > 0) {
        timeoutId = setTimeout(() => {
          this.pending.delete(msg.id);
          reject(new Error("timeout waiting for Colab"));
        }, timeoutMs) as unknown as number;
      }

      this.pending.set(msg.id, { resolve, reject, timeoutId });

      try {
        this.ws!.send(payload);
      } catch (e) {
        if (timeoutId !== null) {
          clearTimeout(timeoutId);
        }
        this.pending.delete(msg.id);
        reject(e instanceof Error ? e : new Error(String(e)));
      }
    });
  }

  private parseRoute(url: URL): { target: RelayTarget; upstreamPathWithQuery: string } | null {
    const path = url.pathname;
    if (path === "/ollama" || path.startsWith("/ollama/")) {
      const sub = path.slice("/ollama".length) || "/";
      return { target: "ollama", upstreamPathWithQuery: `${sub}${url.search}` };
    }
    if (path === "/gliner" || path.startsWith("/gliner/")) {
      const sub = path.slice("/gliner".length) || "/";
      return { target: "gliner", upstreamPathWithQuery: `${sub}${url.search}` };
    }
    return null;
  }
}
