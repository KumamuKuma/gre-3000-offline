import assert from 'node:assert/strict';
import test from 'node:test';
import { adjustMarkCount, normalizeMarks, sortByMarks } from '../app/word-marks.ts';
import { createSyncCode, encryptProgress, decryptProgress } from '../app/sync-code.ts';

test('mark counts add and subtract without numeric precision or fixed length limits', () => {
  assert.deepEqual(adjustMarkCount({}, 'WORD', -1), {});
  assert.deepEqual(adjustMarkCount({}, 'WORD', 1), { word: '1' });
  assert.deepEqual(adjustMarkCount({word:'1'}, 'Word', -1), {});
  assert.equal(adjustMarkCount({word:'9007199254740992'}, 'word', 1).word, '9007199254740993');
  const huge = '9'.repeat(5000);
  const next = adjustMarkCount({word:huge}, 'word', 1).word;
  assert.equal(next, '1' + '0'.repeat(5000));
  assert.equal(adjustMarkCount({word:next}, 'word', -1).word, huge);
});

test('numeric descending ordering keeps source order for ties and does not mutate the queue', () => {
  const words = ['a','b','c','d','e'].map((word,index) => ({word,order:index+1}));
  const marks = {b:'9', c:'10', d:'10', e:'9999999999999999999999999999999'};
  assert.deepEqual(sortByMarks(words,marks).map(x=>x.word), ['e','c','d','b','a']);
  assert.deepEqual(words.map(x=>x.word), ['a','b','c','d','e']);
});

test('bad or lossy count imports are rejected before use', () => {
  for (const value of [null, [], {word:1}, {Word:'1'}, {word:'01'}, {word:'-1'}, {word:'1\n'}, {word:'1\r'}, {word:'1.5'}]) assert.throws(()=>normalizeMarks(value));
});

test('encrypted progress keeps arbitrary precision mark counts and zero deletions', async () => {
  const code = createSyncCode();
  const marks = {word:'900719925474099312345678901234567890'};
  const progress = {schema:'gre-vocab-progress', version:1, marks, settings:{study_sort:'marks_desc'}};
  const encrypted = await encryptProgress(code,progress);
  assert.ok(!encrypted.ciphertext.includes(marks.word));
  assert.deepEqual(await decryptProgress(code,encrypted),progress);
});

test('dictionary words with Object prototype names start from zero', () => {
  assert.equal(adjustMarkCount({}, 'constructor', 1).constructor, '1');
  assert.equal(adjustMarkCount({}, '__proto__', 1)['__proto__'], '1');
});

import { rememberMarkedWord, normalizeRecentMarks } from '../app/word-marks.ts';

test('recent thirty tracks addition order, deduplicates and ignores counter magnitude', () => {
  let ids = [];
  for (let id=1; id<=35; id++) ids = rememberMarkedWord(ids,id);
  assert.deepEqual(ids, Array.from({length:30},(_,i)=>35-i));
  ids = rememberMarkedWord(ids,10);
  assert.equal(ids[0],10);
  assert.equal(ids.length,30);
  assert.equal(new Set(ids).size,30);
  assert.deepEqual(normalizeRecentMarks(ids,new Set(Array.from({length:40},(_,i)=>i+1))),ids);
});

test('invalid recent histories cannot be imported', () => {
  const valid = new Set([1,2,3]);
  for (const value of [null,[1,1],[999],[true],Array.from({length:31},(_,i)=>i+1)]) assert.throws(()=>normalizeRecentMarks(value,valid));
});
