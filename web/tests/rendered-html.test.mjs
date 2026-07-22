import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const root = new URL("../", import.meta.url);

test("ships the GRE product metadata and install manifest", async () => {
  const [layout, manifest] = await Promise.all([
    readFile(new URL("app/layout.tsx", root), "utf8"),
    readFile(new URL("public/manifest.webmanifest", root), "utf8"),
  ]);
  const parsed = JSON.parse(manifest);
  assert.match(layout, /GRE 3000/);
  assert.match(layout, /appleWebApp/);
  assert.match(layout, /og\.png/);
  assert.equal(parsed.display, "standalone");
  assert.equal(parsed.icons.length, 2);
});

test("contains all study modes, offline support, and progress transfer", async () => {
  const [page, worker, content] = await Promise.all([
    readFile(new URL("app/page.tsx", root), "utf8"),
    readFile(new URL("public/sw.js", root), "utf8"),
    readFile(new URL("public/data/words.json", root), "utf8"),
  ]);
  const words = JSON.parse(content);
  assert.equal(words.record_count, 3292);
  assert.match(page, /reading/);
  assert.match(page, /brief/);
  assert.match(page, /recall/);
  assert.match(page, /quiz/);
  assert.match(page, /GRE-3000-学习进度\.json/);
  assert.match(page, /自动云同步/);
  assert.match(worker, /data\/words\.json/);
});
