import { createHash } from "node:crypto";
import { eq } from "drizzle-orm";
import { getDb } from "../../../db";
import { deviceTokens, progress } from "../../../db/schema";

export const dynamic = "force-dynamic";

async function ownerFromRequest(request: Request): Promise<string | null> {
  const authorization = request.headers.get("authorization") ?? "";
  if (!authorization.startsWith("Bearer gre_")) return null;
  const hash = createHash("sha256").update(authorization.slice(7)).digest("hex");
  const rows = await getDb().select({ ownerEmail: deviceTokens.ownerEmail }).from(deviceTokens).where(eq(deviceTokens.tokenHash, hash)).limit(1);
  return rows[0]?.ownerEmail ?? null;
}

function validatePayload(value: unknown): string {
  if (!value || typeof value !== "object") throw new Error("progress must be an object");
  const payload = value as { schema?: unknown; version?: unknown };
  if (payload.schema !== "gre-vocab-progress" || payload.version !== 1) throw new Error("unsupported progress format");
  const encoded = JSON.stringify(value);
  if (encoded.length > 512_000) throw new Error("progress is too large");
  return encoded;
}

export async function GET(request: Request) {
  const ownerEmail = await ownerFromRequest(request);
  if (!ownerEmail) return Response.json({ error: "invalid_device_token" }, { status: 401 });
  const rows = await getDb().select().from(progress).where(eq(progress.ownerEmail, ownerEmail)).limit(1);
  const row = rows[0];
  return Response.json({ progress: row ? JSON.parse(row.payload) : null, updated_at: row?.updatedAt ?? null });
}

export async function PUT(request: Request) {
  const ownerEmail = await ownerFromRequest(request);
  if (!ownerEmail) return Response.json({ error: "invalid_device_token" }, { status: 401 });
  try {
    const encoded = validatePayload(await request.json());
    const updatedAt = new Date().toISOString();
    await getDb().insert(progress).values({ ownerEmail, payload: encoded, updatedAt }).onConflictDoUpdate({
      target: progress.ownerEmail,
      set: { payload: encoded, updatedAt },
    });
    return Response.json({ updated_at: updatedAt });
  } catch (error) {
    return Response.json({ error: error instanceof Error ? error.message : "invalid progress" }, { status: 400 });
  }
}
