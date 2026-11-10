import { createSyncCode, fromBase64Url, toBase64Url, validateSyncCode } from "./sync-code";
import { isSyncUsername } from "./sync-account-name";

export type SyncAccount = { username: string; code: string };

async function accountKeys(password: string, salt: Uint8Array<ArrayBuffer>) {
  const passwordKey = await crypto.subtle.importKey("raw", new TextEncoder().encode(password), "PBKDF2", false, ["deriveBits"]);
  const bits = new Uint8Array(await crypto.subtle.deriveBits({ name: "PBKDF2", salt, iterations: 600_000, hash: "SHA-256" }, passwordKey, 512));
  const key = await crypto.subtle.importKey("raw", bits.slice(32), "AES-GCM", false, ["encrypt", "decrypt"]);
  return { token: `gua_${toBase64Url(bits.slice(0, 32))}`, key };
}

export async function connectSyncAccount(
  request: (path: string, init: RequestInit) => Promise<Response>,
  mode: "login" | "register",
  rawUsername: string,
  password: string,
  existingCode: string,
): Promise<SyncAccount> {
  const username = rawUsername.trim().toLowerCase();
  if (!isSyncUsername(username)) throw new Error("用户名为 3–32 位字母、数字、下划线或短横线，以字母或数字开头。");
  if (!password) throw new Error("请输入密码。");
  if ([...password].length > 128) throw new Error("密码最多 128 个字符。");
  const path = `/api/sync-account?username=${encodeURIComponent(username)}`;
  const associatedData = new TextEncoder().encode(`gre-account-v1:${username}`);

  async function call(method: string, token?: string, body?: object) {
    const headers = new Headers();
    if (token) headers.set("Authorization", `Bearer ${token}`);
    if (body) headers.set("Content-Type", "application/json");
    const response = await request(path, { method, headers, body: body && JSON.stringify(body), cache: "no-store" });
    if (response.status === 401) throw new Error("用户名或密码不正确。");
    if (response.status === 409) throw new Error("用户名已被使用。请登录或换一个名字。");
    if (response.status === 429) throw new Error("尝试太频繁，请稍后再试。");
    if (!response.ok) throw new Error("暂时无法连接账号同步服务。");
    return response.json();
  }

  if (mode === "register") {
    const code = existingCode.trim() ? validateSyncCode(existingCode) : createSyncCode();
    const salt = crypto.getRandomValues(new Uint8Array(16));
    const nonce = crypto.getRandomValues(new Uint8Array(12));
    const { token, key } = await accountKeys(password, salt);
    const wrapped = await crypto.subtle.encrypt({ name: "AES-GCM", iv: nonce, additionalData: associatedData }, key, new TextEncoder().encode(code));
    await call("PUT", token, { salt: toBase64Url(salt), nonce: toBase64Url(nonce), wrappedCode: toBase64Url(new Uint8Array(wrapped)) });
    return { username, code };
  }

  const { salt } = await call("GET");
  if (typeof salt !== "string" || !/^[A-Za-z0-9_-]{22}$/.test(salt)) throw new Error("账号同步数据无效。");
  const { token, key } = await accountKeys(password, fromBase64Url(salt));
  const { wrappedCode, nonce } = await call("POST", token);
  try {
    const bytes = await crypto.subtle.decrypt({ name: "AES-GCM", iv: fromBase64Url(nonce), additionalData: associatedData }, key, fromBase64Url(wrappedCode));
    return { username, code: validateSyncCode(new TextDecoder().decode(bytes)) };
  } catch {
    throw new Error("无法解密账号中的同步码。");
  }
}
