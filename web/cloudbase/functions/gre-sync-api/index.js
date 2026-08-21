import { createServer } from "node:http";
import cloudbase from "@cloudbase/node-sdk";
import { createCodeProgressHandler, MAX_REQUEST_BYTES } from "./api.js";
import { createCloudBaseStorageStore } from "./cloudbase-storage-store.js";
import { createCloudBaseApiHandler } from "./service.js";
import { createTranslateHandler, MAX_TRANSLATE_BODY_BYTES } from "./translate.js";

class RequestTooLargeError extends Error {}

async function readBody(request, maxBytes) {
  const declaredLength = Number(request.headers["content-length"] ?? 0);
  if (Number.isFinite(declaredLength) && declaredLength > maxBytes) {
    request.resume();
    throw new RequestTooLargeError("progress is too large");
  }

  const chunks = [];
  let size = 0;
  let tooLarge = false;
  for await (const value of request) {
    const chunk = Buffer.isBuffer(value) ? value : Buffer.from(value);
    size += chunk.length;
    if (size > maxBytes) {
      tooLarge = true;
      continue;
    }
    chunks.push(chunk);
  }
  if (tooLarge) throw new RequestTooLargeError("progress is too large");
  return Buffer.concat(chunks).toString("utf8");
}

function send(response, result) {
  response.writeHead(result.status, result.headers);
  response.end(result.body);
}

const cloud = cloudbase.init({});
const handleCodeProgress = createCodeProgressHandler({
  store: createCloudBaseStorageStore(cloud),
  onError: (error) => console.error("code-progress request failed", error),
});
const handleApi = createCloudBaseApiHandler({
  codeProgressHandler: handleCodeProgress,
  translateHandler: createTranslateHandler({
    onError: (error) => console.error("translation request failed", error),
  }),
});

const server = createServer(async (request, response) => {
  const method = String(request.method ?? "GET").toUpperCase();
  let body = "";
  try {
    if (method === "PUT" || method === "POST") {
      const pathname = new URL(request.url ?? "/", "http://cloudbase.local").pathname;
      const maxBytes = pathname.replace(/\/$/, "") === "/api/translate"
        ? MAX_TRANSLATE_BODY_BYTES
        : MAX_REQUEST_BYTES;
      body = await readBody(request, maxBytes);
    }
  } catch (error) {
    if (error instanceof RequestTooLargeError) {
      send(response, {
        status: 413,
        headers: {
          "cache-control": "no-store",
          "content-type": "application/json; charset=utf-8",
          "x-content-type-options": "nosniff",
        },
        body: JSON.stringify({ error: "progress is too large" }),
      });
      return;
    }
    console.error("Unable to read request body", error);
    send(response, {
      status: 400,
      headers: {
        "cache-control": "no-store",
        "content-type": "application/json; charset=utf-8",
        "x-content-type-options": "nosniff",
      },
      body: JSON.stringify({ error: "invalid progress" }),
    });
    return;
  }

  const result = await handleApi({
    method,
    url: `http://cloudbase.local${request.url?.startsWith("/") ? request.url : "/"}`,
    headers: request.headers,
    body,
  });
  send(response, result);
});

server.on("clientError", (_error, socket) => {
  socket.end("HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\n");
});

const port = Number(process.env.PORT || 9000);
server.listen(port, "0.0.0.0", () => {
  console.log(`GRE encrypted sync API listening on port ${port}`);
});
