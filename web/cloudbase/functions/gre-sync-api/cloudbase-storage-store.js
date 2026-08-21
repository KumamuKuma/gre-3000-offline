import { authorized, validateEncryptedPayload } from "./api.js";

export const DEFAULT_STORAGE_PREFIX = "gre-sync";

const SPACE_ID_PATTERN = /^[a-f0-9]{64}$/;
const AUTH_HASH_PATTERN = /^[a-f0-9]{64}$/;

function storagePath(spaceId, prefix) {
  if (!SPACE_ID_PATTERN.test(spaceId)) throw new Error("invalid storage space id");
  const normalized = String(prefix ?? "").replace(/^\/+|\/+$/g, "");
  if (!normalized || normalized.includes("..") || !/^[A-Za-z0-9/_-]+$/.test(normalized)) {
    throw new Error("invalid storage prefix");
  }
  return `${normalized}/${spaceId}.json`;
}

function timestamp(value) {
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.valueOf())) throw new Error("stored progress has an invalid timestamp");
  return date.toISOString();
}

function parseStoredRecord(fileContent) {
  const text = Buffer.isBuffer(fileContent)
    ? fileContent.toString("utf8")
    : typeof fileContent === "string"
      ? fileContent
      : "";
  if (!text) throw new Error("stored progress is empty");

  let value;
  try {
    value = JSON.parse(text);
  } catch {
    throw new Error("stored progress is invalid JSON");
  }
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("stored progress has an invalid format");
  }
  if (typeof value.authHash !== "string" || !AUTH_HASH_PATTERN.test(value.authHash)) {
    throw new Error("stored progress has an invalid auth hash");
  }
  const encrypted = validateEncryptedPayload({
    version: 1,
    algorithm: "AES-256-GCM",
    ciphertext: value.ciphertext,
    nonce: value.nonce,
  });
  return {
    authHash: value.authHash,
    ciphertext: encrypted.ciphertext,
    nonce: encrypted.nonce,
    updatedAt: timestamp(value.updatedAt),
  };
}

function isMissingFile(value) {
  const code = String(value?.code ?? value?.errorCode ?? "");
  const message = String(value?.message ?? "");
  return code === "STORAGE_FILE_NONEXIST"
    || code === "FILE_NOT_FOUND"
    || code === "NoSuchKey"
    || /(?:Status:404|\b404\b.*(?:not found|不存在)|文件不存在)/i.test(message);
}

function storageError(operation, result) {
  const code = String(result?.code ?? "unknown");
  return new Error(`CloudBase storage ${operation} failed (${code})`);
}

function createKeyedLock() {
  const tails = new Map();
  return async (key, task) => {
    const previous = tails.get(key) ?? Promise.resolve();
    let release;
    const current = new Promise((resolve) => {
      release = resolve;
    });
    tails.set(key, current);
    await previous;
    try {
      return await task();
    } finally {
      release();
      if (tails.get(key) === current) tails.delete(key);
    }
  };
}

export function createCloudBaseStorageStore(
  cloud,
  { prefix = process.env.SYNC_STORAGE_PREFIX || DEFAULT_STORAGE_PREFIX } = {},
) {
  if (
    !cloud
    || typeof cloud.getUploadMetadata !== "function"
    || typeof cloud.downloadFile !== "function"
    || typeof cloud.uploadFile !== "function"
  ) {
    throw new TypeError("a CloudBase storage client is required");
  }

  const withLock = createKeyedLock();

  async function fileIdForPath(cloudPath) {
    const metadata = await cloud.getUploadMetadata({ cloudPath });
    const fileId = metadata?.data?.fileId;
    if (typeof fileId !== "string" || !fileId) throw storageError("metadata lookup", metadata);
    return fileId;
  }

  async function read(spaceId) {
    const cloudPath = storagePath(spaceId, prefix);
    const fileID = await fileIdForPath(cloudPath);
    let result;
    try {
      result = await cloud.downloadFile({ fileID });
    } catch (error) {
      if (isMissingFile(error)) return null;
      throw error;
    }
    if (isMissingFile(result)) return null;
    if (result?.code && result.code !== "SUCCESS") throw storageError("download", result);
    return parseStoredRecord(result?.fileContent);
  }

  return {
    get: read,

    async upsert({ spaceId, authHash, ciphertext, nonce, updatedAt }) {
      return withLock(spaceId, async () => {
        const existing = await read(spaceId);
        if (existing && !authorized(existing.authHash, authHash)) return false;
        if (!AUTH_HASH_PATTERN.test(authHash)) throw new Error("invalid storage auth hash");

        const encrypted = validateEncryptedPayload({
          version: 1,
          algorithm: "AES-256-GCM",
          ciphertext,
          nonce,
        });
        const record = {
          authHash,
          ciphertext: encrypted.ciphertext,
          nonce: encrypted.nonce,
          updatedAt: timestamp(updatedAt),
        };
        const cloudPath = storagePath(spaceId, prefix);
        const result = await cloud.uploadFile({
          cloudPath,
          fileContent: Buffer.from(JSON.stringify(record), "utf8"),
        });
        if (result?.code && result.code !== "SUCCESS") throw storageError("upload", result);
        if (typeof result?.fileID !== "string" || !result.fileID) {
          throw storageError("upload", result);
        }
        return true;
      });
    },
  };
}
