export const dynamic = "force-dynamic";

const ENDPOINT = "https://api.mymemory.translated.net/get";
const MAX_CHARS = 500;
const MAX_BODY_BYTES = 2_048;
const RATE_LIMIT = 30;
const RATE_WINDOW_MS = 60_000;
const rateBuckets = new Map<string, { count: number; resetAt: number }>();

function rateLimited(request: Request) {
  const key = request.headers.get("cf-connecting-ip") || "unknown";
  const now = Date.now();
  const current = rateBuckets.get(key);
  if (!current || current.resetAt <= now) {
    rateBuckets.set(key, { count: 1, resetAt: now + RATE_WINDOW_MS });
    return false;
  }
  current.count += 1;
  if (rateBuckets.size > 5_000) {
    for (const [bucketKey, value] of rateBuckets) {
      if (value.resetAt <= now) rateBuckets.delete(bucketKey);
    }
  }
  return current.count > RATE_LIMIT;
}

async function readLimitedJson(request: Request) {
  if (!request.body) throw new Error("请求内容为空");
  const reader = request.body.getReader();
  const chunks: Uint8Array[] = [];
  let length = 0;
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    length += value.byteLength;
    if (length > MAX_BODY_BYTES) {
      await reader.cancel();
      throw new Error("请求内容过大");
    }
    chunks.push(value);
  }
  const joined = new Uint8Array(length);
  let offset = 0;
  for (const chunk of chunks) {
    joined.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return JSON.parse(new TextDecoder().decode(joined)) as { text?: unknown };
}

function decodeEntities(value: string) {
  const named: Record<string, string> = {
    amp: "&",
    apos: "'",
    gt: ">",
    lt: "<",
    quot: "\"",
  };
  return value.replace(/&(#x[0-9a-f]+|#\d+|amp|apos|gt|lt|quot);/gi, (_match, entity: string) => {
    if (entity.startsWith("#x")) return String.fromCodePoint(Number.parseInt(entity.slice(2), 16));
    if (entity.startsWith("#")) return String.fromCodePoint(Number.parseInt(entity.slice(1), 10));
    return named[entity.toLowerCase()] ?? _match;
  });
}

export async function POST(request: Request) {
  try {
    if (rateLimited(request)) {
      return Response.json(
        { error: "翻译请求过于频繁，请一分钟后再试" },
        { status: 429, headers: { "retry-after": "60" } },
      );
    }
    const body = await readLimitedJson(request);
    const text = typeof body.text === "string"
      ? body.text.replace(/\s+/g, " ").trim()
      : "";
    if (!text) return Response.json({ error: "没有可翻译的文字" }, { status: 400 });
    if (text.length > MAX_CHARS) {
      return Response.json(
        { error: `选中文字不能超过 ${MAX_CHARS} 个字符` },
        { status: 400 },
      );
    }
    const url = new URL(ENDPOINT);
    url.searchParams.set("q", text);
    url.searchParams.set("langpair", "en|zh-CN");
    const upstream = await fetch(url, {
      headers: { "user-agent": "GRE3000Offline-Web/0.6" },
      signal: AbortSignal.timeout(12_000),
    });
    if (!upstream.ok) throw new Error(`翻译服务返回 HTTP ${upstream.status}`);
    const payload = await upstream.json() as {
      responseStatus?: number | string;
      responseDetails?: string;
      responseData?: { translatedText?: unknown };
    };
    if (payload.responseStatus !== undefined && Number(payload.responseStatus) !== 200) {
      throw new Error(payload.responseDetails || "翻译服务返回错误");
    }
    const translation = typeof payload.responseData?.translatedText === "string"
      ? decodeEntities(payload.responseData.translatedText.trim())
      : "";
    if (!translation) throw new Error("翻译服务没有返回结果");
    return Response.json(
      { translation },
      {
        headers: {
          "cache-control": "private, no-store",
          "x-content-type-options": "nosniff",
        },
      },
    );
  } catch (error) {
    return Response.json(
      { error: error instanceof Error ? error.message : "联网翻译暂时不可用" },
      {
        status: 502,
        headers: { "cache-control": "private, no-store" },
      },
    );
  }
}
