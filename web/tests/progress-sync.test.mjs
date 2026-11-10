import assert from "node:assert/strict";
import test from "node:test";
import { planProgressSync, progressSignature } from "../app/progress-sync.ts";

const empty = {
  schema: "gre-vocab-progress",
  version: 1,
  stars: {},
  notes: {},
  marks: {},
  recent_marks: [],
  lists: { list1: { completed_count: 0, current_word_id: null } },
  settings: {},
};
const phone = {
  ...empty,
  stars: { 3: 2 },
  notes: { abate: "记忆笔记" },
  lists: { list1: { completed_count: 2, current_word_id: 3 } },
};
const remote = (progress, nonce = "phone") => ({ progress, nonce });
const base = { nonce: "phone", signature: progressSignature(phone) };

test("a fresh iPad downloads phone progress even if it has a newer settings timestamp", () => {
  const ipad = { ...empty, exported_at: "2099-01-01", settings: { study_mode: "recall" } };
  assert.equal(planProgressSync(ipad, remote(phone), null), "download");
  assert.equal(planProgressSync(ipad, null, null), "wait");
  assert.equal(planProgressSync(phone, null, null), "upload");
});

test("unchanged downloads and export timestamps never cause an upload", () => {
  assert.equal(planProgressSync(phone, remote({ ...phone, exported_at: "2099-01-01" }), null), "match");
  const newer = remote({ ...phone, notes: { abate: "新笔记" } }, "newer");
  assert.equal(planProgressSync(phone, newer, base), "download");
});

test("local edits are uploaded only if the acknowledged cloud version still matches", () => {
  const local = { ...phone, notes: {} };
  const newer = remote({ ...phone, stars: { 3: 3 } }, "newer");
  assert.equal(planProgressSync(local, remote(phone), base), "upload");
  assert.equal(planProgressSync(local, newer, base), "conflict");
  assert.equal(planProgressSync(local, null, base), "conflict");
});

test("an unknown nonempty local snapshot survives a conflicting first connection", () => {
  assert.equal(planProgressSync(phone, remote(empty), null), "conflict");
  const noteOnly = { ...empty, notes: phone.notes };
  assert.equal(planProgressSync(noteOnly, remote(phone), null), "conflict");
});
