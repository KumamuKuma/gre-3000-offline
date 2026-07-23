"use client";

import { ChangeEvent, useEffect, useMemo, useRef, useState } from "react";
import {
  createSyncCode,
  decryptProgress,
  deriveSyncCredentials,
  encryptProgress,
  validateSyncCode,
} from "./sync-code";

type StudyMode = "reading" | "brief" | "recall" | "quiz";
type Screen = "home" | "study" | "words" | "settings";

type SourceList = {
  key: string;
  label: string;
  count: number;
  first: number;
  last: number;
};

type RootFamily = { root: string; words: number[] };

type WordEntry = {
  id: number;
  order: number;
  list: string;
  word: string;
  phonetic: string;
  definition_en: string;
  definition_zh: string;
  synonyms: string;
  example_en: string;
  example_zh: string;
  machine7: boolean;
  equivalents: number[];
  roots: RootFamily[];
  lookalikes: number[];
};

type ContentPayload = {
  schema: "gre-vocab-content";
  version: 1;
  record_count: number;
  lists: SourceList[];
  words: WordEntry[];
};

type ListProgress = { completed_count: number; current_word_id: number | null };
type Progress = {
  schema: "gre-vocab-progress";
  version: 1;
  exported_at?: string;
  stars: Record<string, number>;
  lists: Record<string, ListProgress>;
  settings: Record<string, string>;
};

type CloudState = {
  status: "disconnected" | "checking" | "ready" | "error";
  updatedAt?: string | null;
  message?: string;
};

const STORAGE_KEY = "gre-vocab-progress-v1";
const SYNC_CODE_STORAGE_KEY = "gre-vocab-sync-code-v1";
const SYNC_TIMEOUT_MS = 12_000;
const MODES: { key: StudyMode; label: string; hint: string }[] = [
  { key: "reading", label: "阅读", hint: "完整释义" },
  { key: "brief", label: "简义", hint: "快速过词" },
  { key: "recall", label: "回忆", hint: "主动揭晓" },
  { key: "quiz", label: "四选一", hint: "选择词义" },
];

function defaultProgress(data: ContentPayload): Progress {
  return {
    schema: "gre-vocab-progress",
    version: 1,
    stars: {},
    lists: Object.fromEntries(
      data.lists.map((item) => [
        item.key,
        { completed_count: 0, current_word_id: null },
      ]),
    ),
    settings: {
      study_list: data.lists[0]?.key ?? "list1",
      study_filter: "all",
      study_mode: "reading",
      auto_speak: "0",
      quiz_wrong_star_up: "0",
      quiz_correct_star_down: "0",
    },
  };
}

function normalizeProgress(value: unknown, data: ContentPayload): Progress {
  if (!value || typeof value !== "object") throw new Error("进度文件不是对象");
  const raw = value as Partial<Progress>;
  if (raw.schema !== "gre-vocab-progress" || raw.version !== 1) {
    throw new Error("进度文件格式或版本不受支持");
  }
  const validIds = new Set(data.words.map((word) => word.id));
  const validLists = new Map(data.lists.map((item) => [item.key, item]));
  const wordsByList = new Map<string, Set<number>>();
  data.lists.forEach((item) => wordsByList.set(item.key, new Set()));
  data.words.forEach((word) => wordsByList.get(word.list)?.add(word.id));

  const stars: Record<string, number> = {};
  if (!raw.stars || typeof raw.stars !== "object") throw new Error("星级数据缺失");
  for (const [key, value] of Object.entries(raw.stars)) {
    const id = Number(key);
    if (!Number.isInteger(id) || !validIds.has(id) || !Number.isInteger(value) || value < 1 || value > 3) {
      throw new Error("进度文件包含无效星级");
    }
    stars[String(id)] = value;
  }

  const lists: Record<string, ListProgress> = {};
  const rawLists = raw.lists && typeof raw.lists === "object" ? raw.lists : {};
  for (const item of data.lists) {
    const state = rawLists[item.key] as ListProgress | undefined;
    const completed = state?.completed_count ?? 0;
    const current = state?.current_word_id ?? null;
    if (!Number.isInteger(completed) || completed < 0) throw new Error("List 次数无效");
    if (current !== null && (!Number.isInteger(current) || !wordsByList.get(item.key)?.has(current))) {
      throw new Error(`${item.label} 的当前位置无效`);
    }
    lists[item.key] = { completed_count: completed, current_word_id: current };
  }

  const settings = raw.settings && typeof raw.settings === "object" ? raw.settings : {};
  const list = validLists.has(settings.study_list) ? settings.study_list : data.lists[0]?.key ?? "list1";
  const filter = /^(all|star:[0-3])$/.test(settings.study_filter ?? "") ? settings.study_filter : "all";
  const mode = MODES.some((item) => item.key === settings.study_mode) ? settings.study_mode : "reading";
  return {
    schema: "gre-vocab-progress",
    version: 1,
    stars,
    lists,
    settings: {
      study_list: list,
      study_filter: filter,
      study_mode: mode,
      auto_speak: settings.auto_speak === "1" ? "1" : "0",
      quiz_wrong_star_up: settings.quiz_wrong_star_up === "1" ? "1" : "0",
      quiz_correct_star_down: settings.quiz_correct_star_down === "1" ? "1" : "0",
    },
  };
}

function starText(rating: number) {
  return rating ? "★".repeat(rating) : "☆";
}

function speak(word: string) {
  if (!("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(word);
  utterance.lang = "en-US";
  utterance.rate = 0.86;
  window.speechSynthesis.speak(utterance);
}

async function readCodeProgress(code: string) {
  const { spaceId, authToken } = await deriveSyncCredentials(code);
  const response = await fetchWithTimeout(
    `/api/code-progress?space=${encodeURIComponent(spaceId)}`,
    {
      cache: "no-store",
      headers: { authorization: `Bearer ${authToken}` },
    },
    "读取云端进度超时，请检查网络后重试。",
  );
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json() as Promise<{ progress: Parameters<typeof decryptProgress>[1] | null; updated_at: string | null }>;
}

async function writeCodeProgress(code: string, progress: Progress) {
  const [{ spaceId, authToken }, encrypted] = await Promise.all([
    deriveSyncCredentials(code),
    encryptProgress(code, progress),
  ]);
  const response = await fetchWithTimeout(
    `/api/code-progress?space=${encodeURIComponent(spaceId)}`,
    {
      method: "PUT",
      headers: {
        authorization: `Bearer ${authToken}`,
        "content-type": "application/json",
      },
      body: JSON.stringify(encrypted),
    },
    "上传云端进度超时，本机进度已保留。",
  );
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json() as Promise<{ updated_at: string }>;
}

async function fetchWithTimeout(url: string, init: RequestInit, timeoutMessage: string) {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), SYNC_TIMEOUT_MS);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw new Error(timeoutMessage);
    throw error;
  } finally {
    window.clearTimeout(timer);
  }
}

function errorMessage(error: unknown, fallback: string) {
  return error instanceof Error && error.message ? error.message : fallback;
}

export default function Home() {
  const [data, setData] = useState<ContentPayload | null>(null);
  const [progress, setProgress] = useState<Progress | null>(null);
  const [hydrated, setHydrated] = useState(false);
  const [screen, setScreen] = useState<Screen>("home");
  const [activeWordId, setActiveWordId] = useState<number | null>(null);
  const [answerVisible, setAnswerVisible] = useState(false);
  const [quizSelected, setQuizSelected] = useState<number | null>(null);
  const [query, setQuery] = useState("");
  const [notice, setNotice] = useState("");
  const [cloud, setCloud] = useState<CloudState>({ status: "disconnected" });
  const [syncCode, setSyncCode] = useState("");
  const [syncCodeInput, setSyncCodeInput] = useState("");
  const [syncRetry, setSyncRetry] = useState(0);
  const importRef = useRef<HTMLInputElement>(null);
  const loadedSyncCode = useRef("");
  const firstCloudUploadNoticeShown = useRef(false);

  useEffect(() => {
    fetch("/data/words.json")
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      })
      .then((payload: ContentPayload) => {
        if (payload.schema !== "gre-vocab-content" || payload.version !== 1 || payload.record_count !== payload.words.length) {
          throw new Error("词库校验失败");
        }
        setData(payload);
        const base = defaultProgress(payload);
        try {
          const stored = localStorage.getItem(STORAGE_KEY);
          setProgress(stored ? normalizeProgress(JSON.parse(stored), payload) : base);
        } catch {
          setProgress(base);
          setNotice("本机旧进度无法读取，已使用新的本地进度。");
        }
        const storedSyncCode = localStorage.getItem(SYNC_CODE_STORAGE_KEY);
        if (storedSyncCode) {
          try {
            const normalized = validateSyncCode(storedSyncCode);
            setSyncCode(normalized);
            setSyncCodeInput(normalized);
          } catch {
            localStorage.removeItem(SYNC_CODE_STORAGE_KEY);
          }
        }
        setHydrated(true);
      })
      .catch((error) => setNotice(`词库加载失败：${error.message}`));
    if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => undefined);
  }, []);

  useEffect(() => {
    if (hydrated && progress) localStorage.setItem(STORAGE_KEY, JSON.stringify(progress));
  }, [hydrated, progress]);

  useEffect(() => {
    if (!hydrated || !data) return;
    if (!syncCode) return;
    if (loadedSyncCode.current === syncCode) return;
    loadedSyncCode.current = syncCode;
    firstCloudUploadNoticeShown.current = false;
    let cancelled = false;
    setCloud({ status: "checking" });
    readCodeProgress(syncCode)
      .then(async (result) => {
        if (cancelled) return;
        const hasCloudProgress = Boolean(result.progress);
        if (result.progress) {
          const decoded = await decryptProgress(syncCode, result.progress);
          if (cancelled) return;
          const imported = normalizeProgress(decoded, data);
          setProgress((local) => {
            const localTime = Date.parse(local?.exported_at ?? "1970-01-01");
            const cloudTime = Date.parse(result.updated_at ?? "1970-01-01");
            return cloudTime >= localTime
              ? { ...imported, exported_at: result.updated_at }
              : local;
          });
        }
        setCloud({ status: "ready", updatedAt: result.updated_at });
        if (hasCloudProgress) {
          firstCloudUploadNoticeShown.current = true;
          setNotice("云端进度读取完成，已开启自动同步。");
        } else {
          setNotice("同步码已连接，云端暂无旧进度，正在保存本机进度。");
        }
      })
      .catch((error) => {
        if (cancelled) return;
        const message = errorMessage(error, "暂时无法读取云端进度。");
        setCloud({ status: "error", message });
        setNotice(`云同步读取失败：${message}`);
      });
    return () => {
      cancelled = true;
    };
  }, [hydrated, data, syncCode, syncRetry]);

  useEffect(() => {
    if (!hydrated || !progress || !syncCode || cloud.status !== "ready") return;
    const timer = window.setTimeout(() => {
      writeCodeProgress(syncCode, progress)
        .then((result) => {
          setCloud((current) => ({ ...current, updatedAt: result.updated_at }));
          if (!firstCloudUploadNoticeShown.current) {
            firstCloudUploadNoticeShown.current = true;
            setNotice("云同步已开启，进度已保存。");
          }
        })
        .catch((error) => {
          const message = errorMessage(error, "暂时无法上传云端进度。");
          setCloud((current) => ({ ...current, status: "error", message }));
          setNotice(`云同步上传失败：${message}`);
        });
    }, 1200);
    return () => window.clearTimeout(timer);
  }, [hydrated, progress, syncCode, cloud.status]);

  const wordMap = useMemo(() => new Map(data?.words.map((word) => [word.id, word]) ?? []), [data]);
  const selectedList = progress?.settings.study_list ?? data?.lists[0]?.key ?? "list1";
  const starFilter = progress?.settings.study_filter ?? "all";
  const mode = (progress?.settings.study_mode ?? "reading") as StudyMode;
  const selectedListMeta = data?.lists.find((item) => item.key === selectedList);
  const listWords = useMemo(() => data?.words.filter((word) => word.list === selectedList) ?? [], [data, selectedList]);
  const studyQueue = useMemo(() => {
    if (!progress) return [];
    if (starFilter === "all") return listWords;
    const rating = Number(starFilter.slice(-1));
    return listWords.filter((word) => (progress.stars[String(word.id)] ?? 0) === rating);
  }, [listWords, progress, starFilter]);
  const activeWord = activeWordId ? wordMap.get(activeWordId) ?? null : null;
  const activeQueueIndex = activeWord ? studyQueue.findIndex((word) => word.id === activeWord.id) : -1;

  const starCounts = useMemo(() => {
    const counts = [0, 0, 0, 0];
    for (const word of listWords) counts[progress?.stars[String(word.id)] ?? 0] += 1;
    return counts;
  }, [listWords, progress]);

  const quiz = useMemo(() => {
    if (!data || !activeWord) return { choices: [] as string[], correct: -1 };
    const choices = [activeWord.definition_zh || activeWord.definition_en];
    let cursor = (activeWord.id * 97) % data.words.length;
    while (choices.length < 4) {
      const candidate = data.words[cursor % data.words.length];
      const meaning = candidate.definition_zh || candidate.definition_en;
      if (candidate.id !== activeWord.id && meaning && !choices.includes(meaning)) choices.push(meaning);
      cursor += 173;
    }
    const shift = activeWord.id % 4;
    const rotated = choices.slice(shift).concat(choices.slice(0, shift));
    return { choices: rotated, correct: rotated.indexOf(choices[0]) };
  }, [activeWord, data]);

  function updateProgress(mutator: (current: Progress) => Progress) {
    setProgress((current) =>
      current
        ? { ...mutator(current), exported_at: new Date().toISOString() }
        : current,
    );
  }

  function setSetting(key: string, value: string) {
    updateProgress((current) => ({ ...current, settings: { ...current.settings, [key]: value } }));
  }

  function startStudy() {
    if (!progress || !studyQueue.length) {
      setNotice("这个 List 中没有符合当前星级的单词。");
      return;
    }
    const saved = progress.lists[selectedList]?.current_word_id;
    const candidate = studyQueue.find((word) => word.id === saved) ?? studyQueue[0];
    setActiveWordId(candidate.id);
    setAnswerVisible(mode === "reading" || mode === "brief");
    setQuizSelected(null);
    setScreen("study");
  }

  function openWord(word: WordEntry) {
    setActiveWordId(word.id);
    setSetting("study_list", word.list);
    setAnswerVisible(mode === "reading" || mode === "brief");
    setQuizSelected(null);
    setScreen("study");
  }

  function jumpToQueueIndex(targetIndex: number) {
    if (!activeWord || !studyQueue.length) return;
    const index = Math.max(0, Math.min(studyQueue.length - 1, targetIndex));
    const next = studyQueue[index];
    setActiveWordId(next.id);
    setAnswerVisible(mode === "reading" || mode === "brief");
    setQuizSelected(null);
    updateProgress((current) => ({
      ...current,
      lists: {
        ...current.lists,
        [selectedList]: { ...current.lists[selectedList], current_word_id: next.id },
      },
    }));
    if (next.id !== activeWord.id && progress?.settings.auto_speak === "1") speak(next.word);
  }

  function move(delta: number) {
    if (!activeWord || !studyQueue.length) return;
    let index = activeQueueIndex;
    if (index < 0) {
      index = studyQueue.findIndex((word) => word.order > activeWord.order);
      if (index < 0) index = studyQueue.length - 1;
    } else {
      index += delta;
    }
    jumpToQueueIndex(index);
  }

  function cycleStar(word: WordEntry) {
    updateProgress((current) => {
      const stars = { ...current.stars };
      const next = ((stars[String(word.id)] ?? 0) + 1) % 4;
      if (next) stars[String(word.id)] = next;
      else delete stars[String(word.id)];
      return { ...current, stars };
    });
  }

  function answerQuiz(choiceIndex: number) {
    if (!activeWord || quizSelected !== null) return;
    const isCorrect = choiceIndex === quiz.correct;
    setQuizSelected(choiceIndex);
    const shouldAdjust = isCorrect
      ? progress.settings.quiz_correct_star_down === "1"
      : progress.settings.quiz_wrong_star_up === "1";
    if (!shouldAdjust) return;
    const previous = progress.stars[String(activeWord.id)] ?? 0;
    const next = isCorrect ? Math.max(0, previous - 1) : Math.min(3, previous + 1);
    updateProgress((current) => {
      const stars = { ...current.stars };
      if (next) stars[String(activeWord.id)] = next;
      else delete stars[String(activeWord.id)];
      return { ...current, stars };
    });
    if (next === previous) {
      setNotice(isCorrect ? "回答正确，当前已是最低 0 星。" : "回答错误，当前已是最高 3 星。");
    } else {
      setNotice(isCorrect ? `回答正确，已自动减为 ${next} 星。` : `回答错误，已自动加为 ${next} 星。`);
    }
  }

  function completeRound() {
    updateProgress((current) => ({
      ...current,
      lists: {
        ...current.lists,
        [selectedList]: {
          ...current.lists[selectedList],
          completed_count: (current.lists[selectedList]?.completed_count ?? 0) + 1,
        },
      },
    }));
    setNotice(`${selectedListMeta?.label ?? "本 List"} 已完成一轮。`);
    setScreen("home");
  }

  function exportFile() {
    if (!progress) return;
    const payload = { ...progress, exported_at: new Date().toISOString() };
    const blob = new Blob([JSON.stringify(payload, null, 2) + "\n"], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "GRE-3000-学习进度.json";
    anchor.click();
    URL.revokeObjectURL(url);
    setNotice("进度文件已导出，可在 Windows 版中导入。");
  }

  function importFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file || !data) return;
    file.text()
      .then((text) => normalizeProgress(JSON.parse(text), data))
      .then((imported) => {
        setProgress(imported);
        setNotice("学习进度导入成功。");
        setScreen("home");
      })
      .catch((error) => setNotice(`导入失败：${error.message}`))
      .finally(() => {
        event.target.value = "";
      });
  }

  function activateSyncCode(rawCode: string) {
    try {
      const normalized = validateSyncCode(rawCode);
      localStorage.setItem(SYNC_CODE_STORAGE_KEY, normalized);
      loadedSyncCode.current = "";
      firstCloudUploadNoticeShown.current = false;
      setSyncCode(normalized);
      setSyncCodeInput(normalized);
      setCloud({ status: "checking" });
      setSyncRetry((current) => current + 1);
      setNotice("同步码已连接，正在读取云端进度。");
    } catch (error) {
      setNotice(`无法连接：${error instanceof Error ? error.message : "同步码无效"}`);
    }
  }

  function makeSyncCode() {
    const code = createSyncCode();
    activateSyncCode(code);
    navigator.clipboard?.writeText(code).catch(() => undefined);
    setNotice("新同步码已创建并复制。请保存好，并粘贴到 Windows 版中。");
  }

  function disconnectSyncCode() {
    localStorage.removeItem(SYNC_CODE_STORAGE_KEY);
    loadedSyncCode.current = "";
    firstCloudUploadNoticeShown.current = false;
    setSyncCode("");
    setSyncCodeInput("");
    setCloud({ status: "disconnected" });
    setNotice("已断开云同步，本机进度仍完整保留。");
  }

  if (!data || !progress) {
    return (
      <main className="loading-shell">
        <div className="brand-mark">G</div>
        <p>{notice || "正在载入 3,292 个词…"}</p>
      </main>
    );
  }

  const relationVisible = mode === "reading" || mode === "brief" || answerVisible || quizSelected !== null;
  const showAnswer = mode === "reading" || mode === "brief" || (mode === "recall" && answerVisible);
  const filteredWords = query.trim()
    ? data.words.filter((word) => word.word.toLowerCase().includes(query.trim().toLowerCase())).slice(0, 80)
    : data.words.slice(0, 80);

  return (
    <main className="app-shell">
      <header className="topbar">
        <button className="brand" onClick={() => setScreen("home")} aria-label="返回首页">
          <span className="brand-mark">G</span>
          <span><strong>GRE 3000</strong><small>原书词序 · 离线学习</small></span>
        </button>
        <span className="offline-pill">可离线</span>
      </header>

      {notice && <button className="notice" onClick={() => setNotice("")}>{notice}<span>×</span></button>}

      {screen === "home" && (
        <section className="page home-page">
          <div className="hero-copy">
            <p className="eyebrow">CONTINUE YOUR ROUTE</p>
            <h1>按自己的节奏，<br />把难词变成熟词。</h1>
            <p>保持原书 List 顺序，标注真正需要反复见面的词。</p>
          </div>

          <div className="metric-row">
            <div className="metric"><strong>{data.record_count.toLocaleString()}</strong><span>词条</span></div>
            <div className="metric"><strong>{Object.keys(progress.stars).length}</strong><span>已标星</span></div>
            <div className="metric"><strong>{Object.values(progress.lists).reduce((sum, item) => sum + item.completed_count, 0)}</strong><span>完成轮次</span></div>
          </div>

          <section className="study-card">
            <div className="section-heading"><div><span>本次学习</span><h2>{selectedListMeta?.label}</h2></div><em>{selectedListMeta?.count} 词</em></div>
            <label className="field-label" htmlFor="list-select">选择 List</label>
            <select id="list-select" value={selectedList} onChange={(event) => setSetting("study_list", event.target.value)}>
              {data.lists.map((item) => <option value={item.key} key={item.key}>{item.label} · {item.count} 词</option>)}
            </select>

            <span className="field-label">学习模式</span>
            <div className="mode-grid">
              {MODES.map((item) => (
                <button className={mode === item.key ? "mode active" : "mode"} key={item.key} onClick={() => setSetting("study_mode", item.key)}>
                  <strong>{item.label}</strong><small>{item.hint}</small>
                </button>
              ))}
            </div>

            <span className="field-label">星级筛选</span>
            <div className="filter-row">
              <button className={starFilter === "all" ? "filter active" : "filter"} onClick={() => setSetting("study_filter", "all")}>全部 <small>{listWords.length}</small></button>
              {[0, 1, 2, 3].map((rating) => (
                <button className={starFilter === `star:${rating}` ? "filter active" : "filter"} onClick={() => setSetting("study_filter", `star:${rating}`)} key={rating}>
                  {rating ? "★".repeat(rating) : "0 星"} <small>{starCounts[rating]}</small>
                </button>
              ))}
            </div>
            <button className="primary" onClick={startStudy}>开始学习 <span>→</span></button>
            <p className="resume-note">已背 {progress.lists[selectedList]?.completed_count ?? 0} 次 · 自动记住当前位置</p>
          </section>

          <section className="install-card">
            <span className="install-icon">＋</span>
            <div><strong>像 App 一样使用</strong><p>在 Safari 点“分享”→“添加到主屏幕”，首次打开后可离线学习。</p></div>
          </section>
        </section>
      )}

      {screen === "study" && activeWord && (
        <section className="page study-page">
          <div className="study-meta">
            <button onClick={() => setScreen("home")}>← 退出</button>
            <span>{selectedListMeta?.label} · {Math.max(activeQueueIndex + 1, 1)} / {studyQueue.length}</span>
          </div>
          <div className="progress-track"><span style={{ width: `${Math.max(3, ((activeQueueIndex + 1) / Math.max(studyQueue.length, 1)) * 100)}%` }} /></div>

          <article className="word-card">
            <div className="word-flags">
              <span>#{activeWord.order}</span>
              {activeWord.machine7 && <em>机经 7.0 重点</em>}
              <button className="star-button" onClick={() => cycleStar(activeWord)} aria-label="修改星级">{starText(progress.stars[String(activeWord.id)] ?? 0)}</button>
            </div>
            <div className="word-title-row"><div><h1>{activeWord.word}</h1><p>{activeWord.phonetic}</p></div><button className="speak" onClick={() => speak(activeWord.word)} aria-label="朗读单词">▶</button></div>

            {mode === "recall" && !answerVisible && <button className="reveal" onClick={() => setAnswerVisible(true)}>想一想，然后点击揭晓</button>}

            {mode === "quiz" && (
              <>
                <div className="quiz-star-controls" aria-label="四选一自动调星">
                  <span>自动调星</span>
                  <label><input type="checkbox" checked={progress.settings.quiz_wrong_star_up === "1"} onChange={(event) => setSetting("quiz_wrong_star_up", event.target.checked ? "1" : "0")} />答错 +1 星</label>
                  <label><input type="checkbox" checked={progress.settings.quiz_correct_star_down === "1"} onChange={(event) => setSetting("quiz_correct_star_down", event.target.checked ? "1" : "0")} />答对 −1 星</label>
                </div>
                <div className="quiz-grid">
                  {quiz.choices.map((choice, index) => {
                    const answered = quizSelected !== null;
                    const className = answered && index === quiz.correct ? "quiz-option correct" : answered && index === quizSelected ? "quiz-option wrong" : "quiz-option";
                    return <button className={className} key={choice} onClick={() => answerQuiz(index)}><span>{String.fromCharCode(65 + index)}</span>{choice}</button>;
                  })}
                </div>
              </>
            )}

            {showAnswer && (
              <div className="answer-block">
                <p className="definition-en">{activeWord.definition_en}</p>
                <p className="definition-zh">{activeWord.definition_zh}</p>
                {mode === "reading" && activeWord.synonyms && <div className="detail-line"><span>近义词</span><p>{activeWord.synonyms}</p></div>}
                {mode === "reading" && activeWord.example_en && <div className="example"><span>例句</span><p>{activeWord.example_en}</p><small>{activeWord.example_zh}</small></div>}
              </div>
            )}

            {relationVisible && (
              <div className="relations">
                {activeWord.equivalents.length > 0 && <Relation title="真经等价词" ids={activeWord.equivalents} wordMap={wordMap} onOpen={(id) => openWord(wordMap.get(id)!)} />}
                {activeWord.roots.map((family) => <Relation key={family.root} title={`词根 ${family.root}`} ids={family.words} wordMap={wordMap} onOpen={(id) => openWord(wordMap.get(id)!)} />)}
                {activeWord.lookalikes.length > 0 && <Relation title="近形异义词" ids={activeWord.lookalikes} wordMap={wordMap} onOpen={(id) => openWord(wordMap.get(id)!)} />}
              </div>
            )}
          </article>

          <div className="study-jumps">
            <button onClick={() => jumpToQueueIndex(0)} disabled={activeQueueIndex === 0}>⇤ 到 List 开头</button>
            <button onClick={() => jumpToQueueIndex(studyQueue.length - 1)} disabled={activeQueueIndex >= studyQueue.length - 1}>到 List 结尾 ⇥</button>
          </div>
          <div className="study-actions">
            <button onClick={() => move(-1)} disabled={activeQueueIndex === 0}>← 上一词</button>
            {activeQueueIndex >= studyQueue.length - 1 ? <button className="finish" onClick={completeRound}>完成本轮</button> : <button className="next" onClick={() => move(1)}>下一词 →</button>}
          </div>
        </section>
      )}

      {screen === "words" && (
        <section className="page words-page">
          <div className="page-title"><p className="eyebrow">WORD INDEX</p><h1>完整词表</h1><span>共 {data.record_count.toLocaleString()} 词，按原书词序</span></div>
          <input className="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索单词，例如 proselytize" autoCapitalize="none" />
          <div className="word-list">
            {filteredWords.map((word) => (
              <button key={word.id} onClick={() => openWord(word)}>
                <span className="word-order">{word.order}</span>
                <span className="word-main"><strong>{word.word}</strong><small>{word.definition_zh || word.definition_en}</small></span>
                {word.machine7 && <em>重点</em>}
                <span className="word-star">{starText(progress.stars[String(word.id)] ?? 0)}</span>
              </button>
            ))}
          </div>
          {!query && <p className="list-hint">输入关键词可检索全部 3,292 个词。</p>}
        </section>
      )}

      {screen === "settings" && (
        <section className="page settings-page">
          <div className="page-title"><p className="eyebrow">YOUR DATA</p><h1>设置与同步</h1><span>进度默认只保存在当前设备</span></div>
          <div className="settings-card">
            <label className="toggle-row"><span><strong>切换到下一词时自动朗读</strong><small>使用 iPhone 系统英文语音</small></span><input type="checkbox" checked={progress.settings.auto_speak === "1"} onChange={(event) => setSetting("auto_speak", event.target.checked ? "1" : "0")} /></label>
            <label className="toggle-row"><span><strong>答错时自动加 1 星</strong><small>仅在四选一模式首次作答时生效</small></span><input type="checkbox" checked={progress.settings.quiz_wrong_star_up === "1"} onChange={(event) => setSetting("quiz_wrong_star_up", event.target.checked ? "1" : "0")} /></label>
            <label className="toggle-row"><span><strong>答对时自动减 1 星</strong><small>星级最低为 0 星，不会继续减少</small></span><input type="checkbox" checked={progress.settings.quiz_correct_star_down === "1"} onChange={(event) => setSetting("quiz_correct_star_down", event.target.checked ? "1" : "0")} /></label>
          </div>
          <div className="settings-card transfer-card">
            <span className="transfer-badge">SYNC</span>
            <h2>Windows ↔ iPhone</h2>
            <p>导出一份小型 JSON 进度文件，通过 iCloud、微信文件或隔空投送传到另一台设备，再点击导入即可同步。词库不会重复导出。</p>
            <button className="primary" onClick={exportFile}>导出当前进度</button>
            <button className="secondary" onClick={() => importRef.current?.click()}>导入进度文件</button>
            <input ref={importRef} type="file" accept="application/json,.json" hidden onChange={importFile} />
          </div>
          <div className="settings-card transfer-card cloud-card">
            <span className="transfer-badge">NO ACCOUNT</span>
            <h2>免账号同步码</h2>
            {cloud.status === "checking" && <p>正在安全连接并读取加密进度…</p>}
            {cloud.status === "disconnected" && <>
              <p>无需登录。新建一组同步码，或粘贴其他设备上的同步码，就能自动同步学习进度。</p>
              <button className="primary" onClick={makeSyncCode}>创建新同步码</button>
              <div className="sync-code-connect">
                <input aria-label="已有同步码" value={syncCodeInput} onChange={(event) => setSyncCodeInput(event.target.value)} placeholder="粘贴 GRE1- 开头的同步码" />
                <button className="secondary" onClick={() => activateSyncCode(syncCodeInput)}>连接已有同步码</button>
              </div>
            </>}
            {cloud.status === "ready" && <>
              <p>此设备的更改会自动加密后同步。把下面这组码粘贴到 Windows 或另一台 iPhone 即可连接。</p>
              <div className="cloud-status">
                <span>● 免账号自动同步已开启</span>
                <small>{cloud.updatedAt ? `最近同步 ${new Date(cloud.updatedAt).toLocaleString("zh-CN")}` : "等待首次同步"}</small>
              </div>
              <div className="token-box"><code>{syncCode}</code><button onClick={() => { navigator.clipboard?.writeText(syncCode); setNotice("同步码已复制。"); }}>复制</button></div>
              <button className="signout" onClick={disconnectSyncCode}>断开这组同步码</button>
            </>}
            {cloud.status === "error" && <>
              <p>暂时无法读取云端加密进度，本地学习不受影响。请检查网络或重新输入同步码。</p>
              {cloud.message && <p className="sync-error-detail">{cloud.message}</p>}
              <button className="secondary" onClick={() => { loadedSyncCode.current = ""; setCloud({ status: "checking" }); setSyncRetry((current) => current + 1); }}>重新连接</button>
              <button className="signout" onClick={disconnectSyncCode}>改用其他同步码</button>
            </>}
          </div>
          <div className="privacy-note"><strong>隐私说明</strong><p>同步内容会在本机使用 AES-256-GCM 加密后再上传，服务器不保存明文，也不需要 GPT 或其他账号。同步码就是解密钥匙：请勿公开，遗失后无法找回。清除 Safari 网站数据前仍建议导出备份。</p></div>
        </section>
      )}

      <nav className="bottom-nav" aria-label="主导航">
        <button className={screen === "home" || screen === "study" ? "active" : ""} onClick={() => setScreen("home")}><span>⌂</span>学习</button>
        <button className={screen === "words" ? "active" : ""} onClick={() => setScreen("words")}><span>≡</span>词表</button>
        <button className={screen === "settings" ? "active" : ""} onClick={() => setScreen("settings")}><span>⚙</span>设置</button>
      </nav>
    </main>
  );
}

function Relation({ title, ids, wordMap, onOpen }: { title: string; ids: number[]; wordMap: Map<number, WordEntry>; onOpen: (id: number) => void }) {
  const unique = [...new Set(ids)].filter((id) => wordMap.has(id));
  if (!unique.length) return null;
  return (
    <div className="relation-block"><span>{title}</span><div>{unique.map((id) => { const word = wordMap.get(id)!; return <button key={id} onClick={() => onOpen(id)}><strong>{word.word}</strong><small>{word.definition_zh || word.definition_en}</small></button>; })}</div></div>
  );
}
