import { headerValue, jsonResponse } from "./api.js";

const ENDPOINT = "https://api.mymemory.translated.net/get";
export const MAX_TRANSLATE_BODY_BYTES = 2_048;
const MAX_TRANSLATE_CHARS = 500;
const RATE_LIMIT = 30;
const RATE_WINDOW_MS = 60_000;

export function decodeEntities(value) {
  const named = {
    amp: "&",
    apos: "'",
    gt: ">",
    lt: "<",
    quot: "\"",
  };
  return value.replace(/&(#x[0-9a-f]+|#\d+|amp|apos|gt|lt|quot);/gi, (match, entity) => {
    if (entity.toLowerCase().startsWith("#x")) {
      return String.fromCodePoint(Number.parseInt(entity.slice(2), 16));
    }
    if (entity.startsWith("#")) return String.fromCodePoint(Number.parseInt(entity.slice(1), 10));
    return named[entity.toLowerCase()] ?? match;
  });
}

function clientAddress(headers) {
  const forwarded = headerValue(headers, "x-forwarded-for").split(",")[0]?.trim();
  return forwarded
    || headerValue(headers, "x-real-ip").trim()
    || headerValue(headers, "x-client-ip").trim()
    || "unknown";
}

function parseText(body) {
  if (typeof body !== "string" || !body) throw new Error("请求内容为空");
  if (Buffer.byteLength(body, "utf8") > MAX_TRANSLATE_BODY_BYTES) throw new Error("请求内容过大");
  let payload;
  try {
    payload = JSON.parse(body);
  } catch {
    throw new Error("请求格式不正确");
  }
  const text = typeof payload?.text === "string" ? payload.text.replace(/\s+/g, " ").trim() : "";
  if (!text) throw new Error("没有可翻译的文字");
  if (text.length > MAX_TRANSLATE_CHARS) {
    throw new Error(`选中文字不能超过 ${MAX_TRANSLATE_CHARS} 个字符`);
  }
  return text;
}

export function createTranslateHandler({
  fetchImpl = fetch,
  clock = () => Date.now(),
  rateBuckets = new Map(),
  onError = console.error,
} = {}) {
  return async function handleTranslate(request) {
    if (String(request.method ?? "GET").toUpperCase() !== "POST") {
      return jsonResponse(405, { error: "method_not_allowed" }, { allow: "POST" });
    }

    const key = clientAddress(request.headers);
    const currentTime = clock();
    const current = rateBuckets.get(key);
    if (!current || current.resetAt <= currentTime) {
      rateBuckets.set(key, { count: 1, resetAt: currentTime + RATE_WINDOW_MS });
    } else {
      current.count += 1;
      if (current.count > RATE_LIMIT) {
        return jsonResponse(429, { error: "翻译请求过于频繁，请一分钟后再试" }, { "retry-after": "60" });
      }
    }
    if (rateBuckets.size > 5_000) {
      for (const [bucketKey, value] of rateBuckets) {
        if (value.resetAt <= currentTime) rateBuckets.delete(bucketKey);
      }
    }

    let text;
    try {
      text = parseText(request.body);
    } catch (error) {
      return jsonResponse(400, { error: error instanceof Error ? error.message : "请求格式不正确" });
    }

    try {
      const url = new URL(ENDPOINT);
      url.searchParams.set("q", text);
      url.searchParams.set("langpair", "en|zh-CN");
      const upstream = await fetchImpl(url, {
        headers: { "user-agent": "GRE3000Offline-Web/0.8.1" },
        signal: AbortSignal.timeout(12_000),
      });
      if (!upstream.ok) throw new Error(`翻译服务返回 HTTP ${upstream.status}`);
      const payload = await upstream.json();
      if (payload.responseStatus !== undefined && Number(payload.responseStatus) !== 200) {
        throw new Error(payload.responseDetails || "翻译服务返回错误");
      }
      const translation = typeof payload.responseData?.translatedText === "string"
        ? decodeEntities(payload.responseData.translatedText.trim())
        : "";
      if (!translation) throw new Error("翻译服务没有返回结果");
      return jsonResponse(200, { translation }, { "cache-control": "private, no-store" });
    } catch (error) {
      onError(error);
      return jsonResponse(
        502,
        { error: error instanceof Error ? error.message : "联网翻译暂时不可用" },
        { "cache-control": "private, no-store" },
      );
    }
  };
}
