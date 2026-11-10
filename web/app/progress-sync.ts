import type { WordNotes } from "./word-notes";
import type { WordMarks } from "./word-marks";

export type ListProgress = { completed_count: number; current_word_id: number | null };
export type Progress = {
  schema: "gre-vocab-progress";
  version: 1;
  exported_at?: string;
  stars: Record<string, number>;
  notes: WordNotes;
  marks: WordMarks;
  recent_marks: number[];
  lists: Record<string, ListProgress>;
  settings: Record<string, string>;
};

export type SyncBase = { nonce: string; signature: string };

export function progressSignature(progress: Progress) {
  const content = { ...progress };
  delete content.exported_at;
  return JSON.stringify(content, (_key, value) => {
    if (!value || typeof value !== "object" || Array.isArray(value)) return value;
    return Object.fromEntries(Object.keys(value).sort().map((key) => [key, value[key]]));
  });
}

function hasLearningProgress(progress: Progress) {
  return Object.keys(progress.stars).length > 0
    || Object.keys(progress.notes).length > 0
    || Object.keys(progress.marks).length > 0
    || progress.recent_marks.length > 0
    || Object.values(progress.lists).some(({ completed_count, current_word_id }) =>
      completed_count > 0 || current_word_id !== null,
    )
    || ["study_star_current_word_id", "study_machine7_current_word_id", "study_marks_current_word_id"]
      .some((key) => progress.settings[key] !== undefined);
}

export function planProgressSync(
  local: Progress,
  remote: { progress: Progress; nonce: string } | null,
  base: SyncBase | null,
) {
  if (!remote) {
    if (base) return "conflict";
    return hasLearningProgress(local) ? "upload" : "wait";
  }
  const localSignature = progressSignature(local);
  if (localSignature === progressSignature(remote.progress)) return "match";
  if (base?.nonce === remote.nonce) return base.signature === localSignature ? "match" : "upload";
  if (base?.signature === localSignature || (!base && !hasLearningProgress(local))) return "download";
  return "conflict";
}
