import { noteKey } from "./word-notes.ts";

export type WordMarks = Record<string, string>;

export function normalizeRecentMarks(value: unknown, validIds: Set<number>): number[] {
  if (!Array.isArray(value) || value.length > 30 || value.some(id => !Number.isInteger(id) || !validIds.has(id)) || new Set(value).size !== value.length) {
    throw new Error("最近标记包含无效、重复或过多的单词编号");
  }
  return [...value];
}

export function rememberMarkedWord(ids: number[], wordId: number): number[] {
  return [wordId, ...ids.filter(id => id !== wordId)].slice(0, 30);
}

export function getMarkCount(marks: WordMarks, word: string): string {
  const key = noteKey(word);
  return Object.hasOwn(marks, key) ? marks[key] : "0";
}

export function normalizeMarks(value: unknown): WordMarks {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("累计标记必须是对象");
  const marks: WordMarks = Object.create(null);
  for (const [key, count] of Object.entries(value)) {
    if (!key || [...key].length > 500 || noteKey(key) !== key || typeof count !== "string" || count.trim() !== count || !/^(0|[1-9][0-9]*)$/.test(count)) {
      throw new Error("累计标记必须使用非负十进制整数字符串");
    }
    if (count !== "0") marks[key] = count;
  }
  return marks;
}

export function adjustMarkCount(marks: WordMarks, word: string, delta: number): WordMarks {
  if (delta !== -1 && delta !== 1) throw new Error("标记每次只能增加或减少一次");
  const key = noteKey(word);
  const count = getMarkCount(marks, word);
  normalizeMarks({ [key]: count });
  if (delta === -1 && count === "0") return marks;
  const digits = count.split("");
  let index = digits.length - 1;
  for (; index >= 0; index--) {
    const digit = Number(digits[index]) + delta;
    if (digit >= 0 && digit <= 9) { digits[index] = String(digit); break; }
    digits[index] = delta === 1 ? "0" : "9";
  }
  if (index < 0 && delta === 1) digits.unshift("1");
  const updated = { ...marks };
  const next = digits.join("").replace(/^0+/, "") || "0";
  if (next === "0") delete updated[key];
  else Object.defineProperty(updated, key, { value: next, enumerable: true, writable: true, configurable: true });
  return updated;
}

export function sortByMarks<T extends { word: string; order: number }>(words: T[], marks: WordMarks): T[] {
  return [...words].sort((left, right) => {
    const a = getMarkCount(marks, left.word);
    const b = getMarkCount(marks, right.word);
    return b.length - a.length || (a === b ? left.order - right.order : a > b ? -1 : 1);
  });
}
