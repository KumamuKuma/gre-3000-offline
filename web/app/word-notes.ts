export const MAX_NOTE_LENGTH = 4000;
export type WordNotes = Record<string, string>;

export function noteKey(word: string) {
  return word.normalize("NFKC").replaceAll("’", "'").replace(/\s+/g, " ").trim().toLowerCase();
}

export function normalizeNotes(value: unknown): WordNotes {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("备注必须是对象");
  const notes: WordNotes = Object.create(null);
  for (const [key, text] of Object.entries(value)) {
    if (!key || [...key].length > 500 || noteKey(key) !== key || typeof text !== "string" || [...text].length > MAX_NOTE_LENGTH) {
      throw new Error("备注包含无效的单词或内容（每词最多 4000 字）");
    }
    if (text) notes[key] = text;
  }
  return notes;
}

export function setWordNote(notes: WordNotes, word: string, text: string): WordNotes {
  const key = noteKey(word);
  normalizeNotes({ [key]: text });
  const updated = { ...notes };
  if (text) updated[key] = text;
  else delete updated[key];
  return updated;
}
