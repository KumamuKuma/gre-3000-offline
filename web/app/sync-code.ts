const CODE_PREFIX = "GRE1-";
const SPACE_CONTEXT = "gre-sync-space-v1:";
const AUTH_CONTEXT = "gre-sync-auth-v1:";
const KEY_CONTEXT = "gre-sync-encryption-v1:";

export type EncryptedProgress = {
  version: 1;
  algorithm: "AES-256-GCM";
  ciphertext: string;
  nonce: string;
};

function toBase64Url(bytes: Uint8Array): string {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replaceAll("+", "-").replaceAll("/", "_").replace(/=+$/, "");
}

function fromBase64Url(value: string): Uint8Array {
  const normalized = value.replaceAll("-", "+").replaceAll("_", "/");
  const padded = normalized + "=".repeat((4 - (normalized.length % 4)) % 4);
  const binary = atob(padded);
  return Uint8Array.from(binary, (character) => character.charCodeAt(0));
}

function normalizeCode(value: string): string {
  return value.trim().replace(/\s+/g, "");
}

function secretFromCode(code: string): Uint8Array {
  const normalized = normalizeCode(code);
  if (!normalized.startsWith(CODE_PREFIX)) throw new Error("同步码格式不正确");
  const secret = fromBase64Url(normalized.slice(CODE_PREFIX.length));
  if (secret.length !== 32) throw new Error("同步码格式不正确");
  return secret;
}

async function digest(context: string, secret: Uint8Array): Promise<Uint8Array> {
  const prefix = new TextEncoder().encode(context);
  const input = new Uint8Array(prefix.length + secret.length);
  input.set(prefix);
  input.set(secret, prefix.length);
  return new Uint8Array(await crypto.subtle.digest("SHA-256", input));
}

export function createSyncCode(): string {
  const secret = crypto.getRandomValues(new Uint8Array(32));
  return `${CODE_PREFIX}${toBase64Url(secret)}`;
}

export function validateSyncCode(code: string): string {
  secretFromCode(code);
  return normalizeCode(code);
}

export async function deriveSyncCredentials(code: string) {
  const secret = secretFromCode(code);
  const [spaceBytes, authBytes, keyBytes] = await Promise.all([
    digest(SPACE_CONTEXT, secret),
    digest(AUTH_CONTEXT, secret),
    digest(KEY_CONTEXT, secret),
  ]);
  return {
    spaceId: Array.from(spaceBytes, (byte) => byte.toString(16).padStart(2, "0")).join(""),
    authToken: `gsa_${toBase64Url(authBytes)}`,
    keyBytes,
  };
}

export async function encryptProgress(code: string, progress: unknown): Promise<EncryptedProgress> {
  const { keyBytes } = await deriveSyncCredentials(code);
  const key = await crypto.subtle.importKey("raw", keyBytes, "AES-GCM", false, ["encrypt"]);
  const nonce = crypto.getRandomValues(new Uint8Array(12));
  const plaintext = new TextEncoder().encode(JSON.stringify(progress));
  const ciphertext = await crypto.subtle.encrypt({ name: "AES-GCM", iv: nonce }, key, plaintext);
  return {
    version: 1,
    algorithm: "AES-256-GCM",
    ciphertext: toBase64Url(new Uint8Array(ciphertext)),
    nonce: toBase64Url(nonce),
  };
}

export async function decryptProgress(code: string, payload: EncryptedProgress): Promise<unknown> {
  if (payload.version !== 1 || payload.algorithm !== "AES-256-GCM") throw new Error("云端数据版本不受支持");
  const { keyBytes } = await deriveSyncCredentials(code);
  const key = await crypto.subtle.importKey("raw", keyBytes, "AES-GCM", false, ["decrypt"]);
  try {
    const plaintext = await crypto.subtle.decrypt(
      { name: "AES-GCM", iv: fromBase64Url(payload.nonce) },
      key,
      fromBase64Url(payload.ciphertext),
    );
    return JSON.parse(new TextDecoder().decode(plaintext));
  } catch {
    throw new Error("同步码不匹配或云端数据已损坏");
  }
}
