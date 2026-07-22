import { createHash, randomBytes } from "node:crypto";
import { getDb } from "../../../db";
import { deviceTokens } from "../../../db/schema";
import { getChatGPTUser } from "../../chatgpt-auth";

export const dynamic = "force-dynamic";

export async function POST() {
  const user = await getChatGPTUser();
  if (!user) return Response.json({ error: "sign_in_required" }, { status: 401 });
  const token = `gre_${randomBytes(32).toString("base64url")}`;
  const tokenHash = createHash("sha256").update(token).digest("hex");
  await getDb().insert(deviceTokens).values({
    tokenHash,
    ownerEmail: user.email,
    label: "Windows desktop",
    createdAt: new Date().toISOString(),
  });
  return Response.json({ token });
}
