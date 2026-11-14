// Runtime stand-in for the nginx `/api/v1` proxy. The upstream is the API
// service's private URL, which Railway only knows after the service exists,
// so it cannot be baked into a next.config rewrite at image build time.

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const HOP_BY_HOP = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
  "host",
  "content-length",
]);

function apiBase(): string {
  return (process.env.API_INTERNAL_URL || process.env.API_URL || "http://127.0.0.1:8001").replace(
    /\/$/,
    "",
  );
}

async function proxy(request: Request, path: string[]): Promise<Response> {
  const incoming = new URL(request.url);
  const target = `${apiBase()}/api/v1/${path.map(encodeURIComponent).join("/")}${incoming.search}`;
  const headers = new Headers();
  request.headers.forEach((value, key) => {
    if (!HOP_BY_HOP.has(key.toLowerCase())) {
      headers.set(key, value);
    }
  });

  const init: RequestInit = {
    method: request.method,
    headers,
    redirect: "manual",
  };
  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = await request.arrayBuffer();
  }

  let upstream: Response;
  try {
    upstream = await fetch(target, init);
  } catch {
    return Response.json(
      { status: "error", message: "API service is unreachable" },
      { status: 502 },
    );
  }

  const out = new Headers();
  upstream.headers.forEach((value, key) => {
    if (key.toLowerCase() === "set-cookie" || HOP_BY_HOP.has(key.toLowerCase())) {
      return;
    }
    out.set(key, value);
  });
  for (const cookie of upstream.headers.getSetCookie()) {
    out.append("set-cookie", cookie);
  }
  return new Response(upstream.body, { status: upstream.status, headers: out });
}

type Ctx = { params: Promise<{ path: string[] }> };

async function handle(request: Request, ctx: Ctx) {
  const { path } = await ctx.params;
  return proxy(request, path);
}

export const GET = handle;
export const POST = handle;
export const PUT = handle;
export const PATCH = handle;
export const DELETE = handle;
export const HEAD = handle;
