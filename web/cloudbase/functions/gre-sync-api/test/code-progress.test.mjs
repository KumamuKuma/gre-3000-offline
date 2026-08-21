import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import test from "node:test";
import {
  createCodeProgressHandler,
  MAX_CIPHERTEXT_CHARS,
  validateEncryptedPayload,
} from "../api.js";
import {
  createCloudBaseStorageStore,
} from "../cloudbase-storage-store.js";
import {
  createCloudBaseApiHandler,
  DEFAULT_ALLOWED_ORIGIN,
  DEFAULT_GATEWAY_ORIGIN,
} from "../service.js";
import { createTranslateHandler, decodeEntities } from "../translate.js";

const SPACE_ID = "a".repeat(64);
const AUTH_TOKEN = `gsa_${"A".repeat(43)}`;
const OTHER_AUTH_TOKEN = `gsa_${"B".repeat(43)}`;
const AUTH_HASH = createHash("sha256").update(AUTH_TOKEN).digest("hex");
const ENCRYPTED = {
  version: 1,
  algorithm: "AES-256-GCM",
  ciphertext: "Ab_-".repeat(8),
  nonce: "A1_-A1_-A1_-A1_-",
};
const UPDATED_AT = "2026-08-21T01:02:03.000Z";

function request(method = "GET", token = AUTH_TOKEN, body = "") {
  return {
    method,
    url: `https://example.test/api/code-progress?space=${SPACE_ID}`,
    headers: { authorization: `Bearer ${token}` },
    body,
  };
}

function responseJson(response) {
  return JSON.parse(response.body);
}

function memoryStore(initial = null) {
  let row = initial;
  return {
    async get(spaceId) {
      assert.equal(spaceId, SPACE_ID);
      return row;
    },
    async upsert(next) {
      if (row && row.authHash !== next.authHash) return false;
      row = { ...next };
      return true;
    },
    value() {
      return row;
    },
  };
}

function cloudStorage(initial = null) {
  let fileContent = initial ? Buffer.from(JSON.stringify(initial), "utf8") : null;
  const uploads = [];
  return {
    client: {
      async getUploadMetadata({ cloudPath }) {
        return { data: { fileId: `cloud://test-env/${cloudPath}` } };
      },
      async downloadFile({ fileID }) {
        assert.match(fileID, /^cloud:\/\/test-env\/gre-sync\/[a-f0-9]{64}\.json$/);
        if (!fileContent) {
          const error = new Error("文件不存在");
          error.code = "STORAGE_FILE_NONEXIST";
          throw error;
        }
        return { fileContent };
      },
      async uploadFile({ cloudPath, fileContent: nextFileContent }) {
        assert.equal(cloudPath, `gre-sync/${SPACE_ID}.json`);
        fileContent = Buffer.from(nextFileContent);
        uploads.push({ cloudPath, fileContent: Buffer.from(nextFileContent) });
        return { fileID: `cloud://test-env/${cloudPath}` };
      },
    },
    uploads,
    value() {
      return fileContent ? JSON.parse(fileContent.toString("utf8")) : null;
    },
  };
}

test("GET preserves the existing /api/code-progress response contract", async () => {
  const store = memoryStore({
    authHash: AUTH_HASH,
    ciphertext: ENCRYPTED.ciphertext,
    nonce: ENCRYPTED.nonce,
    updatedAt: UPDATED_AT,
  });
  const handle = createCodeProgressHandler({ store });

  const response = await handle(request());

  assert.equal(response.status, 200);
  assert.equal(response.headers["cache-control"], "no-store");
  assert.deepEqual(responseJson(response), { progress: ENCRYPTED, updated_at: UPDATED_AT });
});

test("GET returns an empty space without storing or returning plaintext", async () => {
  const handle = createCodeProgressHandler({ store: memoryStore() });
  const response = await handle(request());
  assert.equal(response.status, 200);
  assert.deepEqual(responseJson(response), { progress: null, updated_at: null });
  assert.doesNotMatch(response.body, /stars|lists|settings/);
});

test("malformed credentials and a mismatched bearer token are rejected", async () => {
  const store = memoryStore({
    authHash: AUTH_HASH,
    ciphertext: ENCRYPTED.ciphertext,
    nonce: ENCRYPTED.nonce,
    updatedAt: UPDATED_AT,
  });
  const handle = createCodeProgressHandler({ store });

  const malformed = await handle({ ...request(), headers: { authorization: "Bearer bad" } });
  const mismatch = await handle(request("GET", OTHER_AUTH_TOKEN));

  assert.equal(malformed.status, 401);
  assert.equal(mismatch.status, 401);
  assert.deepEqual(responseJson(mismatch), { error: "invalid_sync_code" });
});

test("PUT stores only the token hash and opaque encrypted fields", async () => {
  const store = memoryStore();
  const handle = createCodeProgressHandler({
    store,
    now: () => new Date(UPDATED_AT),
  });

  const response = await handle(request("PUT", AUTH_TOKEN, JSON.stringify(ENCRYPTED)));

  assert.equal(response.status, 200);
  assert.deepEqual(responseJson(response), { updated_at: UPDATED_AT });
  assert.deepEqual(store.value(), {
    spaceId: SPACE_ID,
    authHash: AUTH_HASH,
    ciphertext: ENCRYPTED.ciphertext,
    nonce: ENCRYPTED.nonce,
    updatedAt: UPDATED_AT,
  });
  assert.doesNotMatch(JSON.stringify(store.value()), new RegExp(AUTH_TOKEN));
});

test("PUT cannot overwrite a space claimed by another credential", async () => {
  const original = {
    authHash: AUTH_HASH,
    ciphertext: ENCRYPTED.ciphertext,
    nonce: ENCRYPTED.nonce,
    updatedAt: UPDATED_AT,
  };
  const store = memoryStore(original);
  const handle = createCodeProgressHandler({ store });

  const response = await handle(request("PUT", OTHER_AUTH_TOKEN, JSON.stringify(ENCRYPTED)));

  assert.equal(response.status, 401);
  assert.deepEqual(store.value(), original);
});

test("encrypted payload validation matches the browser API limits", async () => {
  assert.deepEqual(validateEncryptedPayload(ENCRYPTED), {
    ciphertext: ENCRYPTED.ciphertext,
    nonce: ENCRYPTED.nonce,
  });
  assert.throws(
    () => validateEncryptedPayload({ ...ENCRYPTED, ciphertext: "A".repeat(MAX_CIPHERTEXT_CHARS + 1) }),
    /invalid ciphertext/,
  );
  assert.throws(() => validateEncryptedPayload({ ...ENCRYPTED, nonce: "not-base64url!!!" }), /invalid nonce/);

  const handle = createCodeProgressHandler({ store: memoryStore() });
  const response = await handle(request("PUT", AUTH_TOKEN, "not json"));
  assert.equal(response.status, 400);
  assert.deepEqual(responseJson(response), { error: "invalid progress" });
});

test("storage failures return a generic retryable server error", async () => {
  const failures = [];
  const handle = createCodeProgressHandler({
    store: {
      async get() {
        throw new Error("CloudBase signed storage URL must not leak");
      },
      async upsert() {
        throw new Error("unreachable");
      },
    },
    onError: (error) => failures.push(error),
  });

  const response = await handle(request());

  assert.equal(response.status, 500);
  assert.deepEqual(responseJson(response), { error: "sync_service_unavailable" });
  assert.equal(failures.length, 1);
  assert.doesNotMatch(response.body, /signed|storage|url/i);
});

test("unsupported methods are rejected before touching storage", async () => {
  let touched = false;
  const handle = createCodeProgressHandler({
    store: {
      async get() {
        touched = true;
      },
      async upsert() {
        touched = true;
      },
    },
  });
  const response = await handle(request("POST"));
  assert.equal(response.status, 405);
  assert.equal(response.headers.allow, "GET, PUT");
  assert.equal(touched, false);
});

test("CloudBase storage treats a missing object as an empty sync space", async () => {
  const backend = cloudStorage();
  const store = createCloudBaseStorageStore(backend.client);

  assert.equal(await store.get(SPACE_ID), null);
  assert.equal(backend.uploads.length, 0);
});

test("CloudBase storage persists only opaque encrypted fields", async () => {
  const backend = cloudStorage();
  const store = createCloudBaseStorageStore(backend.client);

  const saved = await store.upsert({
    spaceId: SPACE_ID,
    authHash: AUTH_HASH,
    ciphertext: ENCRYPTED.ciphertext,
    nonce: ENCRYPTED.nonce,
    updatedAt: UPDATED_AT,
  });
  assert.equal(saved, true);
  assert.equal(backend.uploads.length, 1);
  assert.deepEqual(backend.value(), {
    authHash: AUTH_HASH,
    ciphertext: ENCRYPTED.ciphertext,
    nonce: ENCRYPTED.nonce,
    updatedAt: UPDATED_AT,
  });
  assert.deepEqual(await store.get(SPACE_ID), backend.value());
  assert.deepEqual(Object.keys(backend.value()).sort(), ["authHash", "ciphertext", "nonce", "updatedAt"]);
  assert.doesNotMatch(JSON.stringify(backend.value()), new RegExp(AUTH_TOKEN));
  assert.doesNotMatch(JSON.stringify(backend.value()), /stars|lists|settings/);
});

test("CloudBase storage refuses to overwrite an existing object with another auth hash", async () => {
  const backend = cloudStorage({
    authHash: AUTH_HASH,
    ciphertext: ENCRYPTED.ciphertext,
    nonce: ENCRYPTED.nonce,
    updatedAt: UPDATED_AT,
  });
  const store = createCloudBaseStorageStore(backend.client);
  const saved = await store.upsert({
    spaceId: SPACE_ID,
    authHash: createHash("sha256").update(OTHER_AUTH_TOKEN).digest("hex"),
    ciphertext: ENCRYPTED.ciphertext,
    nonce: ENCRYPTED.nonce,
    updatedAt: UPDATED_AT,
  });

  assert.equal(saved, false);
  assert.equal(backend.uploads.length, 0);
  assert.equal(backend.value().authHash, AUTH_HASH);
});

test("CloudBase gateway CORS preflight allows the static website and auth header", async () => {
  let routed = false;
  const handle = createCloudBaseApiHandler({
    codeProgressHandler: async () => {
      routed = true;
    },
    translateHandler: async () => {
      routed = true;
    },
  });
  const response = await handle({
    method: "OPTIONS",
    url: "https://gateway.test/api/code-progress",
    headers: {
      origin: DEFAULT_ALLOWED_ORIGIN,
      "access-control-request-method": "PUT",
      "access-control-request-headers": "authorization,content-type",
    },
  });
  assert.equal(response.status, 204);
  assert.equal(response.headers["access-control-allow-origin"], DEFAULT_ALLOWED_ORIGIN);
  assert.match(response.headers["access-control-allow-methods"], /GET, PUT, POST, OPTIONS/);
  assert.match(response.headers["access-control-allow-headers"], /Authorization/);
  assert.equal(routed, false);
});

test("CloudBase gateway CORS accepts a comma-separated same-origin gateway allowlist", async () => {
  const handle = createCloudBaseApiHandler({
    codeProgressHandler: async () => assert.fail("must not route preflight"),
    translateHandler: async () => assert.fail("must not route preflight"),
    allowedOrigin: `${DEFAULT_ALLOWED_ORIGIN}, ${DEFAULT_GATEWAY_ORIGIN}`,
  });
  const response = await handle({
    method: "OPTIONS",
    url: `${DEFAULT_GATEWAY_ORIGIN}/api/code-progress`,
    headers: { origin: DEFAULT_GATEWAY_ORIGIN },
  });
  assert.equal(response.status, 204);
  assert.equal(response.headers["access-control-allow-origin"], DEFAULT_GATEWAY_ORIGIN);
});

test("CloudBase gateway rejects untrusted browser origins", async () => {
  const handle = createCloudBaseApiHandler({
    codeProgressHandler: async () => assert.fail("must not route"),
    translateHandler: async () => assert.fail("must not route"),
  });
  const response = await handle({
    method: "GET",
    url: "https://gateway.test/api/code-progress",
    headers: { origin: "https://attacker.example" },
  });
  assert.equal(response.status, 403);
  assert.equal(response.headers["access-control-allow-origin"], undefined);
});

test("translation endpoint preserves the webpage response contract", async () => {
  const requests = [];
  const handleTranslate = createTranslateHandler({
    fetchImpl: async (url, init) => {
      requests.push({ url: String(url), init });
      return new Response(JSON.stringify({
        responseStatus: 200,
        responseData: { translatedText: "审慎&amp;克制" },
      }), { status: 200, headers: { "content-type": "application/json" } });
    },
  });
  const handle = createCloudBaseApiHandler({
    codeProgressHandler: async () => assert.fail("wrong route"),
    translateHandler: handleTranslate,
  });
  const response = await handle({
    method: "POST",
    url: "https://gateway.test/api/translate",
    headers: { origin: DEFAULT_ALLOWED_ORIGIN, "x-forwarded-for": "203.0.113.8" },
    body: JSON.stringify({ text: "  prudent   and restrained  " }),
  });
  assert.equal(response.status, 200);
  assert.deepEqual(responseJson(response), { translation: "审慎&克制" });
  assert.equal(response.headers["access-control-allow-origin"], DEFAULT_ALLOWED_ORIGIN);
  assert.match(requests[0].url, /langpair=en%7Czh-CN/);
  assert.match(requests[0].url, /q=prudent\+and\+restrained/);
  assert.equal(decodeEntities("&quot;word&quot; &#x26; &#38;"), '"word" & &');
});
