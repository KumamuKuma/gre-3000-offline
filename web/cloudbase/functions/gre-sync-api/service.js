import { headerValue, jsonResponse } from "./api.js";

export const DEFAULT_ALLOWED_ORIGIN =
  "https://kuma-d9gnt6m3d6b8050f8-1472025206.tcloudbaseapp.com";
export const DEFAULT_GATEWAY_ORIGIN =
  "https://kuma-d9gnt6m3d6b8050f8-1472025206.ap-shanghai.app.tcloudbase.com";
export const DEFAULT_ALLOWED_ORIGINS = `${DEFAULT_ALLOWED_ORIGIN},${DEFAULT_GATEWAY_ORIGIN}`;

function requestPath(url) {
  try {
    const pathname = new URL(url, "http://cloudbase.local").pathname;
    return pathname.length > 1 ? pathname.replace(/\/$/, "") : pathname;
  } catch {
    return "";
  }
}

function parseAllowedOrigins(value) {
  const origins = (Array.isArray(value) ? value : String(value ?? "").split(","))
    .map((origin) => String(origin).trim())
    .filter(Boolean);
  return origins.length ? [...new Set(origins)] : [DEFAULT_ALLOWED_ORIGIN];
}

export function corsHeaders(headers, allowedOrigins = DEFAULT_ALLOWED_ORIGINS) {
  const origin = headerValue(headers, "origin");
  const configuredOrigins = parseAllowedOrigins(allowedOrigins);
  const allowedOrigin = origin || configuredOrigins[0];
  if (!configuredOrigins.includes(allowedOrigin)) return null;
  return {
    "access-control-allow-origin": allowedOrigin,
    "access-control-allow-methods": "GET, PUT, POST, OPTIONS",
    "access-control-allow-headers": "Authorization, Content-Type",
    "access-control-expose-headers": "Retry-After",
    "access-control-max-age": "86400",
    vary: "Origin",
  };
}

function addCors(response, cors) {
  return { ...response, headers: { ...response.headers, ...cors } };
}

export function createCloudBaseApiHandler({
  codeProgressHandler,
  translateHandler,
  allowedOrigin = process.env.CORS_ALLOW_ORIGIN || DEFAULT_ALLOWED_ORIGINS,
} = {}) {
  if (typeof codeProgressHandler !== "function" || typeof translateHandler !== "function") {
    throw new TypeError("code-progress and translate handlers are required");
  }

  return async function handleCloudBaseApi(request) {
    const path = requestPath(request.url);
    const knownPath = path === "/api/code-progress" || path === "/api/translate";
    const cors = corsHeaders(request.headers, allowedOrigin);
    if (!cors) return jsonResponse(403, { error: "origin_not_allowed" });
    if (!knownPath) return addCors(jsonResponse(404, { error: "not_found" }), cors);

    if (String(request.method ?? "GET").toUpperCase() === "OPTIONS") {
      return {
        status: 204,
        headers: {
          "cache-control": "no-store",
          "x-content-type-options": "nosniff",
          ...cors,
        },
        body: "",
      };
    }

    const response = path === "/api/code-progress"
      ? await codeProgressHandler(request)
      : await translateHandler(request);
    return addCors(response, cors);
  };
}
