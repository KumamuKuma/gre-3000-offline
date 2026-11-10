import { GET, PUT } from "../app/api/code-progress/route";
import { POST } from "../app/api/translate/route";
import * as account from "../app/api/sync-account/route";

const pagesOrigin = "https://kumamukuma.github.io";
const apiRoutes = new Map<string, Record<string, (input: Request) => Promise<Response>>>([
  ["/api/code-progress", { GET, PUT }],
  ["/api/translate", { POST }],
  ["/api/sync-account", { GET: account.GET, POST: account.POST, PUT: account.PUT }],
]);

export default {
  async fetch(request: Request, env: { ACCOUNT_LIMIT: { limit(input: { key: string }): Promise<{ success: boolean }> } }): Promise<Response> {
    const path = new URL(request.url).pathname;
    const handlers = apiRoutes.get(path);
    if (!handlers) return Response.json({ error: "not_found" }, { status: 404 });

    const origin = request.headers.get("Origin");
    if (origin && origin !== pagesOrigin) {
      return Response.json({ error: "origin_not_allowed" }, { status: 403 });
    }

    const allow = `${Object.keys(handlers).join(", ")}, OPTIONS`;
    const headers = new Headers({
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
      Vary: "Origin",
    });
    if (origin) {
      headers.set("Access-Control-Allow-Origin", origin);
      headers.set("Access-Control-Allow-Methods", allow);
      headers.set("Access-Control-Allow-Headers", "Authorization, Content-Type");
      headers.set("Access-Control-Expose-Headers", "Retry-After");
    }

    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers });
    const handler = Object.hasOwn(handlers, request.method) ? handlers[request.method] : undefined;
    if (!handler) {
      headers.set("Allow", allow);
      return Response.json({ error: "method_not_allowed" }, { status: 405, headers });
    }

    try {
      if (path === "/api/sync-account") {
        const { success } = await env.ACCOUNT_LIMIT.limit({ key: request.headers.get("CF-Connecting-IP") ?? "unknown" });
        if (!success) return Response.json({ error: "rate_limited" }, { status: 429, headers });
      }
      const result = await handler(request);
      const response = new Response(result.body, result);
      headers.forEach((value, name) => response.headers.set(name, value));
      return response;
    } catch {
      return Response.json({ error: "service_unavailable" }, { status: 503, headers });
    }
  },
};
