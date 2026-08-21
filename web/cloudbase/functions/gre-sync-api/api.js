import { createHash, timingSafeEqual } from "node:crypto";

export const MAX_CIPHERTEXT_CHARS = 700_000;
export const MAX_REQUEST_BYTES = 701_024;

const SPACE_ID_PATTERN = /^[a-f0-9]{64}$/;
const AUTH_TOKEN_PATTERN = /^gsa_[A-Za-z0-9_-]{43}$/;
const NONCE_PATTERN = /^[A-Za-z0-9_-]{16}$/;
const CIPHERTEXT_PATTERN = /^[A-Za-z0-9_-]+$/;

export function jsonResponse(status, payload, extraHeaders = {}) {
  return {
    status,
    headers: {
      "cache-control": "no-store",
      "content-type": "application/json; charset=utf-8",
      "x-content-type-options": "nosniff",
      ...extraHeaders,
    },
    body: JSON.stringify(payload),
  };
}

export function headerValue(headers, name) {
  if (headers && typeof headers.get === "function") return headers.get(name) ?? "";
  if (!headers || typeof headers !== "object") return "";
  const wanted = name.toLowerCase();
  for (const [key, value] of Object.entries(headers)) {
    if (key.toLowerCase() !== wanted) continue;
    return Array.isArray(value) ? value[0] ?? "" : String(value ?? "");
  }
  return "";
}

export function credentialsFromRequest(request) {
  let spaceId = "";
  try {
    spaceId = new URL(request.url, "http://cloudbase.local").searchParams.get("space") ?? "";
  } catch {
    return null;
  }

  const authorization = headerValue(request.headers, "authorization");
  if (!SPACE_ID_PATTERN.test(spaceId) || !authorization.startsWith("Bearer ")) return null;
  const token = authorization.slice("Bearer ".length);
  if (!AUTH_TOKEN_PATTERN.test(token)) return null;

  return {
    spaceId,
    authHash: createHash("sha256").update(token).digest("hex"),
  };
}

export function authorized(expected, actual) {
  if (!SPACE_ID_PATTERN.test(expected) || !SPACE_ID_PATTERN.test(actual)) return false;
  const left = Buffer.from(expected, "hex");
  const right = Buffer.from(actual, "hex");
  return left.length === right.length && timingSafeEqual(left, right);
}

export function validateEncryptedPayload(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("encrypted progress must be an object");
  }
  const payload = value;
  if (payload.version !== 1 || payload.algorithm !== "AES-256-GCM") {
    throw new Error("unsupported encrypted format");
  }
  if (typeof payload.nonce !== "string" || !NONCE_PATTERN.test(payload.nonce)) {
    throw new Error("invalid nonce");
  }
  if (
    typeof payload.ciphertext !== "string"
    || payload.ciphertext.length < 20
    || payload.ciphertext.length > MAX_CIPHERTEXT_CHARS
    || !CIPHERTEXT_PATTERN.test(payload.ciphertext)
  ) {
    throw new Error("invalid ciphertext");
  }
  return { ciphertext: payload.ciphertext, nonce: payload.nonce };
}

function parseEncryptedBody(body) {
  if (typeof body !== "string" || Buffer.byteLength(body, "utf8") > MAX_REQUEST_BYTES) {
    throw new Error("progress is too large");
  }
  try {
    return validateEncryptedPayload(JSON.parse(body));
  } catch (error) {
    if (error instanceof SyntaxError) throw new Error("invalid progress");
    throw error;
  }
}

function timestamp(value) {
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.valueOf())) throw new Error("clock returned an invalid timestamp");
  return date.toISOString();
}

export function createCodeProgressHandler({ store, now = () => new Date(), onError = console.error } = {}) {
  if (!store || typeof store.get !== "function" || typeof store.upsert !== "function") {
    throw new TypeError("a code-progress store is required");
  }

  return async function handleCodeProgress(request) {
    const method = String(request.method ?? "GET").toUpperCase();
    if (method !== "GET" && method !== "PUT") {
      return jsonResponse(405, { error: "method_not_allowed" }, { allow: "GET, PUT" });
    }

    const credentials = credentialsFromRequest(request);
    if (!credentials) return jsonResponse(401, { error: "invalid_sync_code" });

    try {
      if (method === "GET") {
        const row = await store.get(credentials.spaceId);
        if (!row) return jsonResponse(200, { progress: null, updated_at: null });
        if (!authorized(row.authHash, credentials.authHash)) {
          return jsonResponse(401, { error: "invalid_sync_code" });
        }
        return jsonResponse(200, {
          progress: {
            version: 1,
            algorithm: "AES-256-GCM",
            ciphertext: row.ciphertext,
            nonce: row.nonce,
          },
          updated_at: timestamp(row.updatedAt),
        });
      }

      let encrypted;
      try {
        encrypted = parseEncryptedBody(request.body);
      } catch (error) {
        return jsonResponse(400, { error: error instanceof Error ? error.message : "invalid progress" });
      }

      const existing = await store.get(credentials.spaceId);
      if (existing && !authorized(existing.authHash, credentials.authHash)) {
        return jsonResponse(401, { error: "invalid_sync_code" });
      }

      const updatedAt = timestamp(now());
      const saved = await store.upsert({
        spaceId: credentials.spaceId,
        authHash: credentials.authHash,
        ciphertext: encrypted.ciphertext,
        nonce: encrypted.nonce,
        updatedAt,
      });
      if (!saved) return jsonResponse(401, { error: "invalid_sync_code" });
      return jsonResponse(200, { updated_at: updatedAt });
    } catch (error) {
      onError(error);
      return jsonResponse(500, { error: "sync_service_unavailable" });
    }
  };
}
