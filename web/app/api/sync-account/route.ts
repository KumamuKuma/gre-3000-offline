import { createHash, timingSafeEqual } from "node:crypto";
import { eq } from "drizzle-orm";
import { getDb } from "../../../db";
import { syncAccounts } from "../../../db/schema";
import { isSyncUsername } from "../../sync-account-name";

export const dynamic = "force-dynamic";

function reply(body: object, status = 200) {
  return Response.json(body, { status, headers: { "Cache-Control": "no-store" } });
}

function usernameFrom(request: Request) {
  const username = new URL(request.url).searchParams.get("username") ?? "";
  return isSyncUsername(username) ? username : null;
}

function authHashFrom(request: Request) {
  const authorization = request.headers.get("Authorization") ?? "";
  if (!/^Bearer gua_[A-Za-z0-9_-]{43}$/.test(authorization)) return null;
  return createHash("sha256").update(authorization.slice(7)).digest("hex");
}

export async function GET(request: Request) {
  const username = usernameFrom(request);
  if (!username) return reply({ error: "invalid_username" }, 400);
  const [account] = await getDb().select({ salt: syncAccounts.salt }).from(syncAccounts)
    .where(eq(syncAccounts.username, username));
  return account ? reply(account) : reply({ error: "invalid_login" }, 401);
}

export async function POST(request: Request) {
  const username = usernameFrom(request);
  const authHash = authHashFrom(request);
  if (!username || !authHash) return reply({ error: "invalid_login" }, 401);
  const [account] = await getDb().select().from(syncAccounts).where(eq(syncAccounts.username, username));
  if (!account || !timingSafeEqual(Buffer.from(account.authHash, "hex"), Buffer.from(authHash, "hex"))) {
    return reply({ error: "invalid_login" }, 401);
  }
  return reply({ wrappedCode: account.wrappedCode, nonce: account.nonce });
}

export async function PUT(request: Request) {
  const username = usernameFrom(request);
  const authHash = authHashFrom(request);
  if (!username || !authHash) return reply({ error: "invalid_registration" }, 400);
  const reader = request.body?.getReader();
  if (!reader) return reply({ error: "invalid_registration" }, 400);
  const decoder = new TextDecoder();
  let text = "";
  let size = 0;
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    size += value.length;
    if (size > 1024) {
      await reader.cancel();
      return reply({ error: "invalid_registration" }, 400);
    }
    text += decoder.decode(value, { stream: true });
  }
  let payload;
  try {
    payload = JSON.parse(text + decoder.decode());
  } catch {
    return reply({ error: "invalid_registration" }, 400);
  }
  const { salt, wrappedCode, nonce } = payload ?? {};
  if (typeof salt !== "string" || !/^[A-Za-z0-9_-]{22}$/.test(salt)
    || typeof wrappedCode !== "string" || !/^[A-Za-z0-9_-]{86}$/.test(wrappedCode)
    || typeof nonce !== "string" || !/^[A-Za-z0-9_-]{16}$/.test(nonce)) {
    return reply({ error: "invalid_registration" }, 400);
  }
  const inserted = await getDb().insert(syncAccounts).values({ username, salt, authHash, wrappedCode, nonce })
    .onConflictDoNothing().returning({ username: syncAccounts.username });
  return inserted.length ? reply({ username }, 201) : reply({ error: "username_taken" }, 409);
}
