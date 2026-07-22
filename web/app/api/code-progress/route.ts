import { createHash, timingSafeEqual } from "node:crypto";
import { eq } from "drizzle-orm";
import { getDb } from "../../../db";
import { syncSpaces } from "../../../db/schema";

export const dynamic = "force-dynamic";

type Credentials = { spaceId: string; authHash: string };

function credentialsFromRequest(request: Request): Credentials | null {
  const spaceId = new URL(request.url).searchParams.get("space") ?? "";
  const authorization = request.headers.get("authorization") ?? "";
  if (!/^[a-f0-9]{64}$/.test(spaceId) || !authorization.startsWith("Bearer gsa_")) return null;
  const token = authorization.slice(7);
  if (!/^gsa_[A-Za-z0-9_-]{43}$/.test(token)) return null;
  return { spaceId, authHash: createHash("sha256").update(token).digest("hex") };
}

function authorized(expected: string, actual: string): boolean {
  const left = Buffer.from(expected, "hex");
  const right = Buffer.from(actual, "hex");
  return left.length === right.length && timingSafeEqual(left, right);
}

function validateEncryptedPayload(value: unknown) {
  if (!value || typeof value !== "object") throw new Error("encrypted progress must be an object");
  const payload = value as Record<string, unknown>;
  if (payload.version !== 1 || payload.algorithm !== "AES-256-GCM") throw new Error("unsupported encrypted format");
  if (typeof payload.nonce !== "string" || !/^[A-Za-z0-9_-]{16}$/.test(payload.nonce)) throw new Error("invalid nonce");
  if (typeof payload.ciphertext !== "string" || payload.ciphertext.length < 20 || payload.ciphertext.length > 700_000 || !/^[A-Za-z0-9_-]+$/.test(payload.ciphertext)) {
    throw new Error("invalid ciphertext");
  }
  return { ciphertext: payload.ciphertext, nonce: payload.nonce };
}

export async function GET(request: Request) {
  const credentials = credentialsFromRequest(request);
  if (!credentials) return Response.json({ error: "invalid_sync_code" }, { status: 401 });
  const rows = await getDb().select().from(syncSpaces).where(eq(syncSpaces.spaceId, credentials.spaceId)).limit(1);
  const row = rows[0];
  if (!row) return Response.json({ progress: null, updated_at: null });
  if (!authorized(row.authHash, credentials.authHash)) return Response.json({ error: "invalid_sync_code" }, { status: 401 });
  return Response.json({
    progress: { version: 1, algorithm: "AES-256-GCM", ciphertext: row.ciphertext, nonce: row.nonce },
    updated_at: row.updatedAt,
  });
}

export async function PUT(request: Request) {
  const credentials = credentialsFromRequest(request);
  if (!credentials) return Response.json({ error: "invalid_sync_code" }, { status: 401 });
  try {
    const encrypted = validateEncryptedPayload(await request.json());
    const db = getDb();
    const existing = await db.select({ authHash: syncSpaces.authHash }).from(syncSpaces).where(eq(syncSpaces.spaceId, credentials.spaceId)).limit(1);
    if (existing[0] && !authorized(existing[0].authHash, credentials.authHash)) {
      return Response.json({ error: "invalid_sync_code" }, { status: 401 });
    }
    const updatedAt = new Date().toISOString();
    await db.insert(syncSpaces).values({
      spaceId: credentials.spaceId,
      authHash: credentials.authHash,
      ciphertext: encrypted.ciphertext,
      nonce: encrypted.nonce,
      updatedAt,
    }).onConflictDoUpdate({
      target: syncSpaces.spaceId,
      set: { ciphertext: encrypted.ciphertext, nonce: encrypted.nonce, updatedAt },
    });
    return Response.json({ updated_at: updatedAt });
  } catch (error) {
    return Response.json({ error: error instanceof Error ? error.message : "invalid progress" }, { status: 400 });
  }
}
