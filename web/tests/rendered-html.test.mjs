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
  const numbered = words.words.filter((word) => /^(?:\(1\)|①)/.test(word.definition_en));
  assert.equal(numbered.length, 428);
  assert.ok(numbered.every((word) => word.definition_en.includes("\n") && word.definition_zh.includes("\n")));
  const contagious = words.words.find((word) => word.word === "contagious");
  assert.equal(contagious.definition_zh, "(1) 接触传染的\n(2) 有感染力的");
  assert.match(page, /reading/);
  assert.match(page, /brief/);
  assert.match(page, /recall/);
  assert.match(page, /quiz/);
  assert.match(page, /GRE-3000-学习进度\.json/);
  assert.match(page, /免账号同步码/);
  assert.match(page, /AES-256-GCM/);
  assert.match(page, /到 List 开头/);
  assert.match(page, /到 List 结尾/);
  assert.match(worker, /data\/words\.json/);
  assert.match(worker, /pathname\.startsWith\("\/api\/"\)/);
});
