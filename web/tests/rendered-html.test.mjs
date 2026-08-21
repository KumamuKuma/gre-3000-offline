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
  const [page, styles, worker, content, dictionary, translateRoute] = await Promise.all([
    readFile(new URL("app/page.tsx", root), "utf8"),
    readFile(new URL("app/globals.css", root), "utf8"),
    readFile(new URL("public/sw.js", root), "utf8"),
    readFile(new URL("public/data/words.json", root), "utf8"),
    readFile(new URL("public/data/click_dictionary.json", root), "utf8"),
    readFile(new URL("app/api/translate/route.ts", root), "utf8"),
  ]);
  const words = JSON.parse(content);
  const clickDictionary = JSON.parse(dictionary);
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
  assert.match(page, /学习 List（可多选）/);
  assert.match(page, /星级筛选（可多选）/);
  assert.match(page, /选择全部 List/);
  assert.match(page, /study_lists/);
  assert.match(page, /study_star_lists/);
  assert.match(page, /study_star_current_word_id/);
  assert.match(page, /stars:/);
  assert.match(page, /到\{isFullListStudy \? " List" : "筛选"\}开头/);
  assert.match(page, /到\{isFullListStudy \? " List" : "筛选"\}结尾/);
  assert.match(page, /showCorrectQuizReview/);
  assert.match(page, /meaningWithPartsOfSpeech/);
  assert.match(page, /▶ 音源 1/);
  assert.doesNotMatch(page, /▶ 朗读例句/);
  assert.doesNotMatch(page, /<span>词性<\/span>/);
  assert.match(page, /答错 \+1 星/);
  assert.match(page, /答对 −1 星/);
  assert.match(page, /quiz_wrong_star_up/);
  assert.match(page, /quiz_correct_star_down/);
  assert.match(page, /quizAttemptCount/);
  assert.match(page, /retryQuiz/);
  assert.match(page, /重新作答/);
  assert.match(styles, /\.quiz-retry/);
  assert.match(page, /className="study-mode-switcher"/);
  assert.match(page, /aria-label="学习模式"/);
  assert.match(styles, /\.study-mode-switcher/);
  const studyScreen = page.slice(
    page.indexOf('{screen === "study"'),
    page.indexOf('{screen === "words"'),
  );
  assert.match(studyScreen, /onClick=\{\(\) => selectMode\(item\.key\)\}/);
  assert.ok(studyScreen.indexOf('className="study-mode-switcher"') < studyScreen.indexOf('className="word-card"'));
  assert.ok(studyScreen.indexOf('className="study-actions"') < studyScreen.indexOf('className="word-card"'));
  assert.ok(studyScreen.indexOf('className="quiz-retry study-retry"') < studyScreen.indexOf('className="word-card"'));
  assert.ok(studyScreen.indexOf('className="study-jumps"') > studyScreen.indexOf('className="word-card"'));
  assert.match(worker, /gre-3000-pwa-v18/);
  assert.match(worker, /data\/words\.json/);
  assert.match(worker, /data\/click_dictionary\.json/);
  assert.match(worker, /pathname\.startsWith\("\/api\/"\)/);
  assert.equal(clickDictionary.schema, "gre-click-dictionary");
  assert.ok(worker.includes("WORDNET-LICENSE.txt"));
  assert.equal(clickDictionary.version, 2);
  assert.ok(clickDictionary.entry_count > 11_000);
  const dictionarySenses = Object.values(clickDictionary.entries).flatMap((entry) => entry.senses);
  assert.equal(dictionarySenses.length, 37_343);
  assert.match(page, /click_dictionary\.json\?v=2/);
  assert.match(worker, /click_dictionary\.json\?v=2/);
  assert.match(page, /payload\.version !== 2/);
  assert.ok(dictionarySenses.every((sense) => (
    Array.isArray(sense.examples)
    && sense.examples.length > 0
    && sense.examples.every((example) => example.text && example.source)
  )));
  assert.ok(dictionarySenses.some((sense) => sense.examples.some((example) => example.source === "Princeton WordNet 3.0")));
  assert.ok(dictionarySenses.some((sense) => sense.examples.some((example) => example.source === "释义语境（非语料例句）")));
  assert.match(page, /LookupText/);
  assert.match(page, /function LookupQuery/);
  assert.match(page, /<LookupQuery text=\{activeWord\.word\} onLookup=\{openLookup\} \/>/);
  assert.match(page, /GRE 3000 \+ ECDICT 双词典/);
  assert.match(page, /ECDICT 离线词典 · 全部义项/);
  assert.match(page, /offlineSenses/);
  assert.match(page, /lookup\.greTranslation/);
  assert.match(page, /lookup\.offlineTranslation/);
  assert.match(page, /function phraseDictionarySenses/);
  assert.match(page, /if \(!local && normalized\.includes\(" "\)\)/);
  assert.match(page, /greWord && \(local \|\| phrase\)/);
  assert.match(page, /offlineSenses: local\?\.senses \?\? phraseDictionarySenses\(phrase\)/);
  assert.match(styles, /\.lookup-senses/);
  assert.match(styles, /\.lookup-sense-example/);
  assert.match(page, /selection-translate/);
  assert.match(page, /联网翻译/);
  assert.match(page, /api\.mymemory\.translated\.net\/get/);
  assert.match(page, /translateViaMyMemoryDirect/);
  assert.match(page, /startStudySwipe/);
  assert.match(page, /finishStudySwipe/);
  assert.match(page, /左右滑动切换单词/);
  assert.match(page, /朗读完整英文例句/);
  const completeRoundSource = page.slice(
    page.indexOf("function completeRound"),
    page.indexOf("function exportFile"),
  );
  assert.match(completeRoundSource, /current_word_id: firstWordIdByList\.get\(key\)/);
  assert.match(completeRoundSource, /study_star_current_word_id: String\(firstScopeWordId\)/);
  assert.match(styles, /touch-action:\s*pan-y/);
  assert.match(translateRoute, /MAX_CHARS = 500/);
  assert.match(translateRoute, /GRE3000Offline-Web\/0\.8\.1/);
  assert.match(translateRoute, /cache-control": "private, no-store/);
});

test("quiz choices keep their GRE word identity and open a non-answering preview", async () => {
  const [page, styles] = await Promise.all([
    readFile(new URL("app/page.tsx", root), "utf8"),
    readFile(new URL("app/globals.css", root), "utf8"),
  ]);
  const quizSource = page.slice(
    page.indexOf("const quiz = useMemo"),
    page.indexOf("function updateProgress"),
  );
  assert.match(quizSource, /wordId: activeWord\.id/);
  assert.match(quizSource, /wordId: candidate\.id/);
  assert.match(quizSource, /findIndex\(\(choice\) => choice\.wordId === activeWord\.id\)/);
  assert.match(page, /choice\.wordId/);
  assert.match(page, /查看 GRE 词条/);
  assert.match(page, /setGrePreviewWordId\(choice\.wordId\)/);
  assert.match(page, /查看选项 \$\{String\.fromCharCode\(65 \+ index\)\} 对应的 GRE 词条/);
  assert.match(page, /function GreWordPreview/);
  assert.match(page, /closeLabel=\{screen === "study" && mode === "quiz" \? "返回原题" : "关闭词条"\}/);
  assert.match(page, /返回原题/);
  assert.match(page, /onClick=\{\(\) => answerQuiz\(index\)\}/);
  assert.match(styles, /\.quiz-choice-row/);
  assert.match(styles, /\.quiz-entry/);
  assert.match(styles, /\.gre-preview/);
});

test("combines the persisted machine 7 filter with List and star scopes", async () => {
  const [page, styles, content] = await Promise.all([
    readFile(new URL("app/page.tsx", root), "utf8"),
    readFile(new URL("app/globals.css", root), "utf8"),
    readFile(new URL("public/data/words.json", root), "utf8"),
  ]);
  const words = JSON.parse(content);
  const machineWords = words.words.filter((word) => word.machine7);
  assert.equal(machineWords.length, 1410);
  assert.ok(machineWords.every((word, index) => index === 0 || machineWords[index - 1].order < word.order));
  assert.equal(machineWords.filter((word) => word.list === "list1").length, 45);
  assert.equal(machineWords.filter((word) => word.list === "supplement-1").length, 0);
  assert.equal(machineWords.filter((word) => word.list === "supplement-2").length, 0);

  assert.match(page, /study_machine7_only: "0"/);
  assert.match(page, /word_list_machine7_only: "0"/);
  assert.match(page, /study_machine7_only: settings\.study_machine7_only === "1" \? "1" : "0"/);
  assert.match(page, /word_list_machine7_only: settings\.word_list_machine7_only === "1" \? "1" : "0"/);
  assert.match(page, /study_machine7_current_word_id/);
  assert.match(page, /machine7Ids\.has\(rawMachine7WordId\)/);
  assert.match(page, /const saved = machine7Only\s*\? Number\(progress\.settings\.study_machine7_current_word_id\)/);
  assert.match(page, /\[machine7Only \? "study_machine7_current_word_id" : "study_star_current_word_id"\]/);
  assert.match(page, /machine7Only \? scopeWords\.filter\(\(word\) => word\.machine7\) : scopeWords/);
  assert.match(page, /studyBaseWords\.filter\(\(word\) => selectedStarRatings\.includes/);
  assert.match(page, /const isFullListStudy = allStarsSelected && !machine7Only/);
  assert.match(page, /仅机经 7\.0 重点词/);
  assert.match(page, /aria-label="机经 7\.0 重点词筛选"/);
  assert.match(page, /当前组合下没有单词/);
  assert.match(page, /className="word-list-empty" role="status"/);
  assert.match(page, /wordListMachine7Only\s*\? data\.words\.filter\(\(word\) => word\.machine7\)\s*: data\.words/);
  assert.match(page, /WORD_LIST_BATCH_SIZE = 80/);
  assert.match(page, /wordListMatches\.slice\(0, wordListLimit\)/);
  assert.match(page, /加载更多/);
  assert.match(page, /已显示 \{filteredWords\.length\.toLocaleString\(\)\} \/ \{wordListMatches\.length\.toLocaleString\(\)\}/);
  assert.doesNotMatch(page, /wordListCandidates\.slice\(0, 80\)/);
  assert.match(styles, /\.priority-filter/);
  assert.match(styles, /\.empty-filter-note/);
  assert.match(styles, /\.index-priority-filter/);
  assert.match(styles, /\.word-list-empty/);
  assert.match(styles, /\.word-list-more/);

  const selectedLists = new Set(["list1", "list2"]);
  const selectedRatings = new Set([1, 2]);
  const combined = words.words.filter((word) => (
    selectedLists.has(word.list)
    && word.machine7
    && selectedRatings.has(word.id % 4)
  ));
  assert.ok(combined.length > 0);
  assert.ok(combined.every((word, index) => index === 0 || combined[index - 1].order < word.order));
});
