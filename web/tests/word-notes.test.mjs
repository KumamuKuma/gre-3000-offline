import assert from "node:assert/strict";
import test from "node:test";
import { noteKey, normalizeNotes, setWordNote } from "../app/word-notes.ts";
import { createSyncCode, encryptProgress, decryptProgress } from "../app/sync-code.ts";

test("word notes share normalized keys and survive encrypted progress round trips", async () => {
  const text = "联想\n词根 <b>原样文字</b> 🐻";
  const notes = setWordNote({}, "  INEVITABLE  ", text);
  assert.equal(noteKey(" It’s  inevitable "), "it's inevitable");
  assert.equal(notes.inevitable, text);
  assert.equal(normalizeNotes(JSON.parse(JSON.stringify(notes))).inevitable, text);
  const code = createSyncCode();
  const encrypted = await encryptProgress(code, { schema: "gre-vocab-progress", version: 1, notes });
  assert.ok(!JSON.stringify(encrypted).includes("联想"));
  assert.deepEqual(await decryptProgress(code, encrypted), { schema: "gre-vocab-progress", version: 1, notes });
  assert.deepEqual(setWordNote(notes, "Inevitable", ""), {});
});

test("malformed note imports are rejected", () => {
  for (const value of [null, [], { Word: "text" }, { word: 7 }, { word: "字".repeat(4001) }, { "": "text" }]) {
    assert.throws(() => normalizeNotes(value));
  }
});
