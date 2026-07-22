import { eq } from "drizzle-orm";
import { getDb } from "../../../db";
import { getChatGPTUser } from "../../chatgpt-auth";
import { progress } from "../../../db/schema";

export const dynamic = "force-dynamic";

function validatePayload(value: unknown): string {
  if (!value || typeof value !== "object") throw new Error("progress must be an object");
  const payload = value as { schema?: unknown; version?: unknown };
  if (payload.schema !== "gre-vocab-progress" || payload.version !== 1) {
    throw new Error("unsupported progress format");
  }
  const encoded = JSON.stringify(value);
  if (encoded.length > 512_000) throw new Error("progress is too large");
  return encoded;
}

export async function GET() {
  const user = await getChatGPTUser();
  if (!user) return Response.json({ error: "sign_in_required" }, { status: 401 });
  const rows = await getDb().select().from(progress).where(eq(progress.ownerEmail, user.email)).limit(1);
  const row = rows[0];
  return Response.json({
    user: { email: user.email, display_name: user.displayName },
    progress: row ? JSON.parse(row.payload) : null,
    updated_at: row?.updatedAt ?? null,
  });
}

export async function PUT(request: Request) {
  const user = await getChatGPTUser();
  if (!user) return Response.json({ error: "sign_in_required" }, { status: 401 });
  try {
    const payload = await request.json();
    const encoded = validatePayload(payload);
    const updatedAt = new Date().toISOString();
    await getDb().insert(progress).values({ ownerEmail: user.email, payload: encoded, updatedAt }).onConflictDoUpdate({
      target: progress.ownerEmail,
      set: { payload: encoded, updatedAt },
    });
    return Response.json({ updated_at: updatedAt });
  } catch (error) {
    return Response.json({ error: error instanceof Error ? error.message : "invalid progress" }, { status: 400 });
  }
}
