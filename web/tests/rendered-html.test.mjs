import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  dictionaryEntryForDisplay,
  dictionarySensesForDisplay,
} from "../app/dictionary-senses.ts";

const root = new URL("../", import.meta.url);

test("shows repeated Chinese sense text once while retaining every English sense and example", () => {
  const repeatedTranslation = "使服从, 压制, 减弱, 抑制, 克制";
  const senses = [
    {
      part_of_speech: "v.",
      translation: repeatedTranslation,
      definition: "put down by force",
      examples: [{ text: "The army subdued the rebellion.", source: "WordNet" }],
    },
    {
      part_of_speech: "v.",
      translation: repeatedTranslation,
      definition: "make less intense",
      examples: [{ text: "The lights subdued the room.", source: "WordNet" }],
    },
    {
      part_of_speech: "v.",
      translation: "约束",
      definition: "hold within limits",
      examples: [{ text: "She subdued her anger.", source: "WordNet" }],
    },
    {
      part_of_speech: "v.",
      translation: "",
      definition: "bring under cultivation",
      examples: [{ text: "They subdued the wild land.", source: "WordNet" }],
    },
  ];

  const displayed = dictionarySensesForDisplay(senses);

  assert.deepEqual(
    displayed.map(({ displayTranslation }) => displayTranslation),
    [repeatedTranslation, "同译见义项 1", "约束", ""],
  );
  assert.deepEqual(
    displayed.map(({ sense }) => sense.definition),
    senses.map(({ definition }) => definition),
  );
  assert.deepEqual(
    displayed.flatMap(({ sense }) => sense.examples),
    senses.flatMap(({ examples }) => examples),
  );
});

test("references overlapping Chinese lemmas once without dropping English senses", () => {
  const displayed = dictionaryEntryForDisplay(
    [
      { part_of_speech: "v.", translation: "中断；中止", definition: "interrupt", examples: [] },
      { part_of_speech: "v.", translation: "中断；暂停", definition: "pause", examples: [] },
      { part_of_speech: "v.", translation: "中止", definition: "end", examples: [] },
    ],
    "v. 中断, 中断, 中止, 暂停, 终止",
  );

  assert.deepEqual(
    displayed.senses.map(({ displayTranslation }) => displayTranslation),
    ["中断；中止", "暂停\n同译见义项 1", "同译见义项 1"],
  );
  assert.equal(displayed.summaryTranslation, "v. 终止");
  assert.deepEqual(
    displayed.senses.map(({ sense }) => sense.definition),
    ["interrupt", "pause", "end"],
  );
});

test("keeps a same-text summary meaning when its POS differs from the precise sense", () => {
  const displayed = dictionaryEntryForDisplay(
    [
      {
        part_of_speech: "adj.",
        translation: "荒诞",
        definition: "inconsistent with reason",
        examples: [{ text: "an absurd claim", source: "WordNet" }],
      },
    ],
    "a. 荒诞\nn. 荒诞",
  );

  assert.equal(displayed.summaryTranslation, "n. 荒诞");
  assert.equal(displayed.senses[0].displayTranslation, "荒诞");
  assert.equal(displayed.senses[0].sense.definition, "inconsistent with reason");
  assert.deepEqual(displayed.senses[0].sense.examples, [
    { text: "an absurd claim", source: "WordNet" },
  ]);
});

test("splits translation lines without treating a question mark as a separator", () => {
  const displayed = dictionarySensesForDisplay([
    { translation: "询问", definition: "ask", examples: [] },
    {
      translation: "疑问?号\r\n询问",
      definition: "question mark",
      examples: [{ text: "The sentence ends with a question mark.", source: "WordNet" }],
    },
  ]);

  assert.equal(displayed[1].displayTranslation, "疑问?号\n同译见义项 1");
  assert.equal(displayed[1].sense.definition, "question mark");
  assert.deepEqual(displayed[1].sense.examples, [
    { text: "The sentence ends with a question mark.", source: "WordNet" },
  ]);
});

test("deduplicates summary meanings only when their parts of speech agree", () => {
  const typed = dictionaryEntryForDisplay(
    [{ part_of_speech: "adj.", translation: "荒诞", definition: "absurd", examples: [] }],
    "a. 荒诞\nn. 荒诞\n荒诞",
  );
  assert.equal(typed.summaryTranslation, "n. 荒诞");

  const untyped = dictionaryEntryForDisplay(
    [{ part_of_speech: "", translation: "荒诞", definition: "absurd", examples: [] }],
    "n. 荒诞\n荒诞",
  );
  assert.equal(untyped.summaryTranslation, "n. 荒诞");

  const repeatedVerb = dictionaryEntryForDisplay(
    [],
    "vt. 投降, 退出\nvi. 投降, 离开",
  );
  assert.equal(repeatedVerb.summaryTranslation, "vt. 投降，退出\nvi. 离开");
});

test("keeps a distinct per-sense translation even when the broad summary overlaps", () => {
  const { senses: [displayed], summaryTranslation } = dictionaryEntryForDisplay(
    [{ part_of_speech: "v.", translation: "压制, 缓和, 新义项", definition: "", examples: [] }],
    "vt. 压制, 缓和",
  );

  assert.equal(displayed.displayTranslation, "压制, 缓和, 新义项");
  assert.equal(summaryTranslation, "");
});

test("keeps unmatched entry-level meanings after moving precise meanings to senses", () => {
  const displayed = dictionaryEntryForDisplay(
    [{ part_of_speech: "v.", translation: "压制", definition: "put down by force", examples: [] }],
    "vt. 压制, 减弱",
  );

  assert.equal(displayed.senses[0].displayTranslation, "压制");
  assert.equal(displayed.summaryTranslation, "vt. 减弱");
});

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
  assert.match(worker, /gre-3000-pwa-v21/);
  assert.match(worker, /data\/words\.json/);
  assert.match(worker, /data\/click_dictionary\.json/);
  assert.match(worker, /pathname\.startsWith\("\/api\/"\)/);
  assert.equal(clickDictionary.schema, "gre-click-dictionary");
  assert.ok(worker.includes("WORDNET-LICENSE.txt"));
  assert.ok(worker.includes("COW-LICENSE.txt"));
  assert.equal(clickDictionary.version, 2);
  assert.equal(clickDictionary.entry_count, 12_060);
  assert.equal(clickDictionary.target_count, 12_350);
  assert.deepEqual(clickDictionary.sources.map(({ name }) => name), [
    "ECDICT",
    "Princeton WordNet 3.0",
    "Chinese Open Wordnet 0.9",
    "项目内 COW 已审核修正",
  ]);
  const dictionarySenses = Object.values(clickDictionary.entries).flatMap((entry) => entry.senses);
  assert.equal(dictionarySenses.length, 33_291);
  assert.equal(dictionarySenses.filter((sense) => sense.translation && sense.definition).length, 14_167);
  assert.match(page, /click_dictionary\.json\?v=5/);
  assert.match(page, /click_dictionary\.json\?v=5", \{ cache: "no-store" \}/);
  assert.match(page, /addEventListener\("controllerchange", reloadForWorkerUpdate\)/);
  assert.match(page, /registration\.update\(\)/);
  assert.match(page, /window\.location\.reload\(\)/);
  assert.match(worker, /click_dictionary\.json\?v=5/);
  assert.match(worker, /url\.pathname === "\/data\/click_dictionary\.json"/);
  assert.match(worker, /fetch\(event\.request\)[\s\S]*caches\.match\(event\.request\)/);
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
  assert.match(page, /GRE 3000 \+ ECDICT\/COW\/WordNet 离线词典/);
  assert.match(page, /ECDICT 中文总览 \+ COW 逐义项中文 \+ WordNet 英文义项\/例句/);
  assert.match(page, /Chinese Open Wordnet 0\.9 许可/);
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
  assert.match(translateRoute, /GRE3000Offline-Web\/0\.9\.0/);
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

test("long sentence reader reuses offline lookup and supports safe keyboard and swipe paging", async () => {
  const [page, styles, worker] = await Promise.all([
    readFile(new URL("app/page.tsx", root), "utf8"),
    readFile(new URL("app/globals.css", root), "utf8"),
    readFile(new URL("public/sw.js", root), "utf8"),
  ]);

  assert.match(page, /"sentences"/);
  assert.match(page, /fetch\("\/data\/long_sentences\.json"\)/);
  assert.match(page, /payload\.schema !== "gre-long-sentences"/);
  assert.match(page, /setLongSentencesStatus\("error"\)/);
  assert.match(page, /长难句内容载入失败，请刷新后重试/);
  assert.match(page, /杨鹏 GRE 长难句/);
  assert.match(page, /一页一句 · 每词可查/);
  assert.match(page, /<LookupText text=\{activeLongSentence\.text\} onLookup=\{openLookup\} \/>/);
  assert.match(page, /原书第 \{activeLongSentence\.source_number\} 句/);
  assert.match(page, /startSentenceSwipe/);
  assert.match(page, /finishSentenceSwipe/);
  assert.match(page, /event\.key !== "ArrowLeft" && event\.key !== "ArrowRight"/);
  assert.match(page, /window\.scrollTo\(\{ top: 0, behavior: "auto" \}\)/);
  assert.match(page, /disabled=\{longSentenceIndex === 0\}/);
  assert.match(page, /disabled=\{longSentenceIndex === longSentences\.sentences\.length - 1\}/);
  assert.match(page, /左右滑动切换句子/);
  assert.match(styles, /\.sentence-entry/);
  assert.match(styles, /\.sentence-card \{[^}]*touch-action:\s*pan-y/);
  assert.match(styles, /\.sentence-actions/);
  assert.match(worker, /"\/data\/long_sentences\.json"/);
  assert.match(worker, /url\.pathname === "\/data\/long_sentences\.json"/);
  assert.equal(worker.match(/\/data\/long_sentences\.json/g)?.length, 2);
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
