"use client";

import { ChangeEvent, PointerEvent, useEffect, useMemo, useRef, useState } from "react";
import {
  createSyncCode,
  decryptProgress,
  deriveSyncCredentials,
  encryptProgress,
  validateSyncCode,
} from "./sync-code";
import { dictionaryEntryForDisplay } from "./dictionary-senses";

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

type DictionaryEntry = {
  word: string;
  phonetic: string;
  translation: string;
  definition: string;
  exchange: string;
  phrases: [string, string][];
  senses?: DictionarySense[];
};

type DictionaryExample = {
  text: string;
  source?: string;
};

type DictionarySense = {
  part_of_speech: string;
  translation: string;
  definition: string;
  examples: DictionaryExample[];
};

type DictionaryPayload = {
  schema: "gre-click-dictionary";
  version: 1 | 2;
  entries: Record<string, DictionaryEntry>;
};

type LookupView = {
  query: string;
  normalized: string;
  source: string;
  headword: string;
  phonetic: string;
  greTranslation: string;
  greDefinition: string;
  greExampleEn: string;
  greExampleZh: string;
  offlineTranslation: string;
  offlineDefinition: string;
  offlineSenses: DictionarySense[];
  exchange: string;
  phrases: [string, string][];
  greWordId?: number;
  onlineStatus: "idle" | "loading" | "ready" | "error";
  onlineTranslation?: string;
  onlineError?: string;
};

const STORAGE_KEY = "gre-vocab-progress-v1";
const SYNC_CODE_STORAGE_KEY = "gre-vocab-sync-code-v1";
const SYNC_TIMEOUT_MS = 12_000;
const WORD_LIST_BATCH_SIZE = 80;
const MODES: { key: StudyMode; label: string; hint: string }[] = [
  { key: "reading", label: "阅读", hint: "完整释义" },
  { key: "brief", label: "简义", hint: "快速过词" },
  { key: "recall", label: "回忆", hint: "主动揭晓" },
  { key: "quiz", label: "四选一", hint: "选择词义" },
];
const LOOKUP_TOKEN = /[A-Za-z]+(?:['’-][A-Za-z]+)*/g;
let lookupClickTimer: ReturnType<typeof setTimeout> | null = null;

function normalizeLookupQuery(value: string) {
  const text = value.normalize("NFKC").replaceAll("’", "'").replace(/\s+/g, " ").trim();
  if (!text) return "";
  if (text.includes(" ")) {
    return text.replace(/^[\s.,;:!?"“”‘’()[\]{}]+|[\s.,;:!?"“”‘’()[\]{}]+$/g, "").toLowerCase();
  }
  return text.match(/[A-Za-z]+(?:['-][A-Za-z]+)*/)?.[0]?.toLowerCase() ?? "";
}

function phraseDictionarySenses(phrase: [string, string] | undefined): DictionarySense[] {
  if (!phrase) return [];
  return [{
    part_of_speech: "",
    translation: phrase[1],
    definition: "",
    examples: [{
      text: `The phrase "${phrase[0]}" is used here with the meaning shown above.`,
      source: "释义语境（非语料例句）",
    }],
  }];
}

function LookupText({ text, className, onLookup }: { text: string; className?: string; onLookup: (word: string) => void }) {
  const parts: Array<string | { token: string; offset: number }> = [];
  let cursor = 0;
  for (const match of text.matchAll(LOOKUP_TOKEN)) {
    const offset = match.index ?? 0;
    if (offset > cursor) parts.push(text.slice(cursor, offset));
    parts.push({ token: match[0], offset });
    cursor = offset + match[0].length;
  }
  if (cursor < text.length) parts.push(text.slice(cursor));
  return (
    <span className={className} data-lookup-scope>
      {parts.map((part, index) => typeof part === "string"
        ? part
        : <span
            className="lookup-token"
            key={`${part.offset}-${part.token}-${index}`}
            onClick={(event) => {
              event.stopPropagation();
              if (window.getSelection()?.toString().trim()) return;
              if (lookupClickTimer) window.clearTimeout(lookupClickTimer);
              lookupClickTimer = window.setTimeout(() => {
                lookupClickTimer = null;
                onLookup(part.token);
              }, 180);
            }}
            onDoubleClick={(event) => {
              event.stopPropagation();
              if (lookupClickTimer) {
                window.clearTimeout(lookupClickTimer);
                lookupClickTimer = null;
              }
              const range = document.createRange();
              range.selectNodeContents(event.currentTarget);
              const selection = window.getSelection();
              selection?.removeAllRanges();
              selection?.addRange(range);
            }}
          >{part.token}</span>)}
    </span>
  );
}

function normalizeStarListScope(value: string | undefined, data: ContentPayload) {
  const allKeys = data.lists.map((item) => item.key);
  if (!value || value === "all") return "all";
  const requested = new Set(value.split(",").map((key) => key.trim()).filter(Boolean));
  const selected = allKeys.filter((key) => requested.has(key));
  if (!selected.length || selected.length === allKeys.length) return "all";
  return selected.join(",");
}

function starListKeys(value: string | undefined, data: ContentPayload) {
  const allKeys = data.lists.map((item) => item.key);
  const normalized = normalizeStarListScope(value, data);
  return normalized === "all" ? allKeys : normalized.split(",");
}

function starRatings(value: string | undefined) {
  if (!value || value === "all") return [0, 1, 2, 3];
  const raw = value.startsWith("stars:")
    ? value.slice("stars:".length).split(",")
    : value.startsWith("star:")
      ? [value.slice("star:".length)]
      : [];
  const selected = [...new Set(raw.map(Number).filter((rating) => Number.isInteger(rating) && rating >= 0 && rating <= 3))].sort();
  return selected.length ? selected : [0, 1, 2, 3];
}

function starFilterSetting(ratings: number[]) {
  const selected = [...new Set(ratings)].sort();
  if (selected.length === 4) return "all";
  if (selected.length === 1) return `star:${selected[0]}`;
  return `stars:${selected.join(",")}`;
}

function partOfSpeech(definition: string) {
  const matches = [...definition.matchAll(/(?:^|[\s(/,])(?:\d+\))?(adj|adv|prep|conj|pron|interj|aux|det|num|vt|vi|n|v)\./gi)];
  const labels = [...new Set(matches.map((match) => `${match[1].toLowerCase()}.`))];
  return labels.join("/") || "未标明";
}

const circledSenseNumbers: Record<string, string> = Object.fromEntries(
  [..."①②③④⑤⑥⑦⑧⑨⑩"].map((marker, index) => [marker, String(index + 1)]),
);
const sensePrefix = /^\s*(\((\d+)\)|([①②③④⑤⑥⑦⑧⑨⑩]))\s*/;

function meaningWithPartsOfSpeech(meaning: string, definition: string) {
  const senseLabels = new Map<string, string>();
  for (const line of definition.split("\n")) {
    const match = line.match(sensePrefix);
    if (!match) continue;
    const senseNumber = match[2] || circledSenseNumbers[match[3]];
    const label = partOfSpeech(line.slice(match[0].length));
    if (senseNumber && label !== "未标明") senseLabels.set(senseNumber, label);
  }

  const fallbackLabel = partOfSpeech(definition);
  const lines = meaning.split("\n");
  const nonblankCount = lines.filter((line) => line.trim()).length;
  let nextUnnumberedSense = 1;

  return lines.map((line) => {
    if (!line.trim()) return line;
    const match = line.match(sensePrefix);
    if (match) {
      const senseNumber = match[2] || circledSenseNumbers[match[3]];
      const label = senseLabels.get(senseNumber) || (senseLabels.size ? "" : fallbackLabel);
      return label && label !== "未标明"
        ? `${match[1]}${label}${line.slice(match[0].length).trimStart()}`
        : line;
    }

    let label = "";
    if (senseLabels.size && nonblankCount > 1) {
      label = senseLabels.get(String(nextUnnumberedSense)) || "";
      nextUnnumberedSense += 1;
    } else if (fallbackLabel !== "未标明") {
      label = fallbackLabel;
    }
    return label ? `${label}${line.trimStart()}` : line;
  }).join("\n");
}

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
      study_lists: "all",
      study_star_lists: "all",
      study_filter: "all",
      study_machine7_only: "0",
      word_list_machine7_only: "0",
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
  const machine7Ids = new Set(data.words.filter((word) => word.machine7).map((word) => word.id));
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
  const parsedRatings = starRatings(settings.study_filter);
  const filter = starFilterSetting(parsedRatings);
  const mode = MODES.some((item) => item.key === settings.study_mode) ? settings.study_mode : "reading";
  const legacyScope = filter === "all"
    ? settings.study_list ?? settings.study_star_lists
    : settings.study_star_lists ?? settings.study_list;
  const starScope = normalizeStarListScope(settings.study_lists ?? legacyScope, data);
  const rawStarWordId = Number(settings.study_star_current_word_id);
  const starWordSetting = (
    Number.isInteger(rawStarWordId) && validIds.has(rawStarWordId)
      ? { study_star_current_word_id: String(rawStarWordId) }
      : {}
  );
  const rawMachine7WordId = Number(settings.study_machine7_current_word_id);
  const machine7WordSetting = (
    Number.isInteger(rawMachine7WordId) && machine7Ids.has(rawMachine7WordId)
      ? { study_machine7_current_word_id: String(rawMachine7WordId) }
      : {}
  );
  return {
    schema: "gre-vocab-progress",
    version: 1,
    stars,
    lists,
    settings: {
      study_list: list,
      study_lists: starScope,
      study_star_lists: starScope,
      ...starWordSetting,
      ...machine7WordSetting,
      study_filter: filter,
      study_machine7_only: settings.study_machine7_only === "1" ? "1" : "0",
      word_list_machine7_only: settings.word_list_machine7_only === "1" ? "1" : "0",
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

function apiUrl(path: string) {
  if (typeof document === "undefined") return path;
  const origin = document
    .querySelector<HTMLMetaElement>('meta[name="gre-api-origin"]')
    ?.content.trim()
    .replace(/\/$/, "");
  return origin ? `${origin}${path}` : path;
}

async function readCodeProgress(code: string) {
  const { spaceId, authToken } = await deriveSyncCredentials(code);
  const response = await fetchWithTimeout(
    apiUrl(`/api/code-progress?space=${encodeURIComponent(spaceId)}`),
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
    apiUrl(`/api/code-progress?space=${encodeURIComponent(spaceId)}`),
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

async function translateViaMyMemoryDirect(text: string) {
  const params = new URLSearchParams({ q: text, langpair: "en|zh-CN" });
  const response = await fetchWithTimeout(
    `https://api.mymemory.translated.net/get?${params.toString()}`,
    { cache: "no-store" },
    "翻译请求超时，请检查网络后重试。",
  );
  const payload = await response.json() as {
    responseStatus?: number | string;
    responseDetails?: string;
    responseData?: { translatedText?: string };
  };
  const serviceStatus = Number(payload.responseStatus ?? response.status);
  const translation = payload.responseData?.translatedText?.trim() ?? "";
  if (!response.ok || serviceStatus >= 400 || !translation) {
    throw new Error(payload.responseDetails || `HTTP ${serviceStatus}`);
  }
  const decoder = document.createElement("textarea");
  decoder.innerHTML = translation;
  return decoder.value;
}

export default function Home() {
  const [data, setData] = useState<ContentPayload | null>(null);
  const [progress, setProgress] = useState<Progress | null>(null);
  const [hydrated, setHydrated] = useState(false);
  const [screen, setScreen] = useState<Screen>("home");
  const [activeWordId, setActiveWordId] = useState<number | null>(null);
  const [studySessionWordIds, setStudySessionWordIds] = useState<number[]>([]);
  const [answerVisible, setAnswerVisible] = useState(false);
  const [quizSelected, setQuizSelected] = useState<number | null>(null);
  const [quizAttemptCount, setQuizAttemptCount] = useState(0);
  const [query, setQuery] = useState("");
  const [notice, setNotice] = useState("");
  const [cloud, setCloud] = useState<CloudState>({ status: "disconnected" });
  const [syncCode, setSyncCode] = useState("");
  const [syncCodeInput, setSyncCodeInput] = useState("");
  const [syncRetry, setSyncRetry] = useState(0);
  const [dictionary, setDictionary] = useState<DictionaryPayload | null>(null);
  const [dictionaryStatus, setDictionaryStatus] = useState<"loading" | "ready" | "error">("loading");
  const [lookup, setLookup] = useState<LookupView | null>(null);
  const [grePreviewWordId, setGrePreviewWordId] = useState<number | null>(null);
  const [selectionText, setSelectionText] = useState("");
  const [wordListWindow, setWordListWindow] = useState({ key: "", limit: WORD_LIST_BATCH_SIZE });
  const importRef = useRef<HTMLInputElement>(null);
  const loadedSyncCode = useRef("");
  const firstCloudUploadNoticeShown = useRef(false);
  const translationCache = useRef(new Map<string, string>());
  const studySwipeStart = useRef<{
    pointerId: number;
    x: number;
    y: number;
    startedAt: number;
  } | null>(null);

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
    let reloadingForWorkerUpdate = false;
    const reloadForWorkerUpdate = () => {
      if (reloadingForWorkerUpdate) return;
      reloadingForWorkerUpdate = true;
      window.location.reload();
    };
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.addEventListener("controllerchange", reloadForWorkerUpdate);
      navigator.serviceWorker.register("/sw.js")
        .then((registration) => registration.update())
        .catch(() => undefined);
    }
    fetch("/data/click_dictionary.json?v=4", { cache: "no-store" })
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      })
      .then((payload: DictionaryPayload) => {
        if (payload.schema !== "gre-click-dictionary" || payload.version !== 2) throw new Error("词典校验失败");
        setDictionary(payload);
        setDictionaryStatus("ready");
      })
      .catch(() => setDictionaryStatus("error"));
    return () => {
      if ("serviceWorker" in navigator) {
        navigator.serviceWorker.removeEventListener("controllerchange", reloadForWorkerUpdate);
      }
    };
  }, []);

  useEffect(() => {
    if (!dictionary) return;
    setLookup((current) => {
      if (!current) return current;
      const local = dictionary.entries[current.normalized];
      let phrase: [string, string] | undefined;
      if (!local && current.normalized.includes(" ")) {
        phrase = dictionary.entries[current.normalized.split(" ")[0]]?.phrases.find(
          ([value]) => normalizeLookupQuery(value) === current.normalized,
        );
      }
      if (!local && !phrase) return current;
      return {
        ...current,
        source: current.greWordId
          ? "GRE 3000 + ECDICT/COW/WordNet 离线词典"
          : "ECDICT/COW/WordNet 离线词典",
        headword: current.greWordId ? current.headword : local?.word ?? phrase?.[0] ?? current.headword,
        phonetic: current.phonetic || local?.phonetic || "",
        offlineTranslation: local?.translation ?? phrase?.[1] ?? "",
        offlineDefinition: local?.definition ?? "",
        offlineSenses: local?.senses ?? phraseDictionarySenses(phrase),
        exchange: local?.exchange ?? "",
        phrases: local?.phrases ?? [],
      };
    });
  }, [dictionary]);

  useEffect(() => {
    if (dictionaryStatus !== "error") return;
    setLookup((current) => current?.source === "内置词典载入中"
      ? { ...current, source: "内置词典载入失败" }
      : current);
  }, [dictionaryStatus]);

  useEffect(() => {
    let timer = 0;
    const readSelection = () => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => {
        const selection = window.getSelection();
        const text = selection?.toString().replace(/\s+/g, " ").trim() ?? "";
        if (!selection || selection.rangeCount === 0 || !text || text.length > 500) {
          setSelectionText("");
          return;
        }
        const ancestor = selection.getRangeAt(0).commonAncestorContainer;
        const element = ancestor.nodeType === Node.ELEMENT_NODE ? ancestor as Element : ancestor.parentElement;
        if (!element?.closest("[data-lookup-scope]")) {
          setSelectionText("");
          return;
        }
        setSelectionText(text);
      }, 140);
    };
    document.addEventListener("selectionchange", readSelection);
    document.addEventListener("touchend", readSelection);
    return () => {
      window.clearTimeout(timer);
      document.removeEventListener("selectionchange", readSelection);
      document.removeEventListener("touchend", readSelection);
    };
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
  const wordByHeadword = useMemo(
    () => new Map(data?.words.map((word) => [normalizeLookupQuery(word.word), word]) ?? []),
    [data],
  );
  const starFilter = progress?.settings.study_filter ?? "all";
  const selectedStarRatings = useMemo(() => starRatings(starFilter), [starFilter]);
  const allStarsSelected = selectedStarRatings.length === 4;
  const machine7Only = progress?.settings.study_machine7_only === "1";
  const wordListMachine7Only = progress?.settings.word_list_machine7_only === "1";
  const mode = (progress?.settings.study_mode ?? "reading") as StudyMode;
  const selectedListKeys = useMemo(
    () => data ? starListKeys(progress?.settings.study_lists ?? progress?.settings.study_star_lists ?? progress?.settings.study_list, data) : [],
    [data, progress?.settings.study_list, progress?.settings.study_lists, progress?.settings.study_star_lists],
  );
  const selectedListSet = useMemo(() => new Set(selectedListKeys), [selectedListKeys]);
  const scopeWords = useMemo(
    () => data?.words.filter((word) => selectedListSet.has(word.list)) ?? [],
    [data, selectedListSet],
  );
  const machine7Count = useMemo(
    () => scopeWords.filter((word) => word.machine7).length,
    [scopeWords],
  );
  const totalMachine7Count = useMemo(
    () => data?.words.filter((word) => word.machine7).length ?? 0,
    [data],
  );
  const studyBaseWords = useMemo(
    () => machine7Only ? scopeWords.filter((word) => word.machine7) : scopeWords,
    [machine7Only, scopeWords],
  );
  const eligibleStudyQueue = useMemo(() => {
    if (!progress) return [];
    if (allStarsSelected) return studyBaseWords;
    return studyBaseWords.filter((word) => selectedStarRatings.includes(progress.stars[String(word.id)] ?? 0));
  }, [allStarsSelected, progress, selectedStarRatings, studyBaseWords]);
  const studyQueue = useMemo(() => {
    if (screen !== "study" || !studySessionWordIds.length) return eligibleStudyQueue;
    return studySessionWordIds
      .map((wordId) => wordMap.get(wordId))
      .filter((word): word is WordEntry => Boolean(word));
  }, [eligibleStudyQueue, screen, studySessionWordIds, wordMap]);
  const isFullListStudy = allStarsSelected && !machine7Only;
  const activeWord = activeWordId ? wordMap.get(activeWordId) ?? null : null;
  const grePreviewWord = grePreviewWordId ? wordMap.get(grePreviewWordId) ?? null : null;
  const activeQueueIndex = activeWord ? studyQueue.findIndex((word) => word.id === activeWord.id) : -1;

  const starCounts = useMemo(() => {
    const counts = [0, 0, 0, 0];
    for (const word of studyBaseWords) counts[progress?.stars[String(word.id)] ?? 0] += 1;
    return counts;
  }, [progress, studyBaseWords]);
  const listMachine7Counts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const word of data?.words ?? []) {
      if (word.machine7) counts.set(word.list, (counts.get(word.list) ?? 0) + 1);
    }
    return counts;
  }, [data]);
  const firstWordIdByList = useMemo(() => {
    const firstIds = new Map<string, number>();
    for (const word of data?.words ?? []) {
      if (!firstIds.has(word.list)) firstIds.set(word.list, word.id);
    }
    return firstIds;
  }, [data]);
  const studyScopeLabel = useMemo(() => {
    if (!data) return "所选 List";
    if (selectedListKeys.length === data.lists.length) return "全部 List";
    if (selectedListKeys.length === 1) {
      return data.lists.find((item) => item.key === selectedListKeys[0])?.label ?? "1 个 List";
    }
    return `已选 ${selectedListKeys.length} 个 List`;
  }, [data, selectedListKeys]);
  const studySelectionLabel = machine7Only
    ? `${studyScopeLabel} · 机经 7.0 重点`
    : studyScopeLabel;

  const quiz = useMemo(() => {
    if (!data || !activeWord) return { choices: [] as { wordId: number; text: string }[], correct: -1 };
    const correctChoice = { wordId: activeWord.id, text: activeWord.definition_zh || activeWord.definition_en };
    const choices = [correctChoice];
    let cursor = (activeWord.id * 97) % data.words.length;
    while (choices.length < 4) {
      const candidate = data.words[cursor % data.words.length];
      const meaning = candidate.definition_zh || candidate.definition_en;
      if (candidate.id !== activeWord.id && meaning && !choices.some((choice) => choice.text === meaning)) {
        choices.push({ wordId: candidate.id, text: meaning });
      }
      cursor += 173;
    }
    const shift = activeWord.id % 4;
    const rotated = choices.slice(shift).concat(choices.slice(0, shift));
    return { choices: rotated, correct: rotated.findIndex((choice) => choice.wordId === activeWord.id) };
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

  function selectMode(nextMode: StudyMode) {
    setSetting("study_mode", nextMode);
    setAnswerVisible(nextMode === "reading" || nextMode === "brief");
    setQuizSelected(null);
    setQuizAttemptCount(0);
  }

  function setListScope(keys: string[]) {
    if (!data || !keys.length) return;
    const selected = data.lists.map((item) => item.key).filter((key) => keys.includes(key));
    if (!selected.length) return;
    const value = selected.length === data.lists.length ? "all" : selected.join(",");
    updateProgress((current) => ({
      ...current,
      settings: {
        ...current.settings,
        study_lists: value,
        study_star_lists: value,
        ...(selected.length === 1 ? { study_list: selected[0] } : {}),
      },
    }));
  }

  function toggleList(key: string) {
    const selected = new Set(selectedListKeys);
    if (selected.has(key)) {
      if (selected.size === 1) {
        setNotice("学习范围至少保留一个 List。");
        return;
      }
      selected.delete(key);
    } else {
      selected.add(key);
    }
    setListScope([...selected]);
  }

  function toggleStarRating(rating: number) {
    if (allStarsSelected) {
      setSetting("study_filter", `star:${rating}`);
      return;
    }
    const selected = new Set(selectedStarRatings);
    if (selected.has(rating)) {
      if (selected.size === 1) {
        setNotice("星级筛选至少保留一个星级。");
        return;
      }
      selected.delete(rating);
    } else {
      selected.add(rating);
    }
    setSetting("study_filter", starFilterSetting([...selected]));
  }

  function startStudy() {
    if (!progress || !eligibleStudyQueue.length) {
      setNotice("所选 List、机经重点和星级条件下没有可学习的单词。");
      return;
    }
    const singleList = selectedListKeys.length === 1 ? selectedListKeys[0] : null;
    const saved = machine7Only
      ? Number(progress.settings.study_machine7_current_word_id)
      : isFullListStudy && singleList
        ? progress.lists[singleList]?.current_word_id
        : Number(progress.settings.study_star_current_word_id);
    const candidate = eligibleStudyQueue.find((word) => word.id === saved) ?? eligibleStudyQueue[0];
    setStudySessionWordIds(eligibleStudyQueue.map((word) => word.id));
    setActiveWordId(candidate.id);
    if (machine7Only) {
      setSetting("study_machine7_current_word_id", String(candidate.id));
    } else if (!isFullListStudy || !singleList) {
      setSetting("study_star_current_word_id", String(candidate.id));
    }
    setAnswerVisible(mode === "reading" || mode === "brief");
    setQuizSelected(null);
    setQuizAttemptCount(0);
    setScreen("study");
  }

  function openWord(word: WordEntry) {
    setStudySessionWordIds(
      (data?.words ?? []).filter((candidate) => candidate.list === word.list).map((candidate) => candidate.id),
    );
    setActiveWordId(word.id);
    setListScope([word.list]);
    setAnswerVisible(mode === "reading" || mode === "brief");
    setQuizSelected(null);
    setQuizAttemptCount(0);
    setScreen("study");
  }

  function jumpToQueueIndex(targetIndex: number) {
    if (!activeWord || !studyQueue.length) return;
    const index = Math.max(0, Math.min(studyQueue.length - 1, targetIndex));
    const next = studyQueue[index];
    setActiveWordId(next.id);
    setAnswerVisible(mode === "reading" || mode === "brief");
    setQuizSelected(null);
    setQuizAttemptCount(0);
    updateProgress((current) => ({
      ...current,
      ...(isFullListStudy && selectedListKeys.length === 1
        ? {
            lists: {
              ...current.lists,
              [selectedListKeys[0]]: { ...current.lists[selectedListKeys[0]], current_word_id: next.id },
            },
          }
        : {
            settings: {
              ...current.settings,
              [machine7Only ? "study_machine7_current_word_id" : "study_star_current_word_id"]: String(next.id),
            },
          }),
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

  function startStudySwipe(event: PointerEvent<HTMLElement>) {
    const target = event.target instanceof Element ? event.target : null;
    if (
      event.pointerType === "mouse"
      || target?.closest("button, a, input, select, textarea, label, .lookup-token")
    ) {
      studySwipeStart.current = null;
      return;
    }
    studySwipeStart.current = {
      pointerId: event.pointerId,
      x: event.clientX,
      y: event.clientY,
      startedAt: Date.now(),
    };
  }

  function finishStudySwipe(event: PointerEvent<HTMLElement>) {
    captureSelection(event);
    const start = studySwipeStart.current;
    studySwipeStart.current = null;
    if (!start || start.pointerId !== event.pointerId) return;
    if (window.getSelection()?.toString().trim()) return;
    const deltaX = event.clientX - start.x;
    const deltaY = event.clientY - start.y;
    const elapsed = Date.now() - start.startedAt;
    if (
      elapsed > 800
      || Math.abs(deltaX) < 72
      || Math.abs(deltaX) < Math.abs(deltaY) * 1.35
    ) return;
    move(deltaX < 0 ? 1 : -1);
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
    const firstAttempt = quizAttemptCount === 0;
    setQuizSelected(choiceIndex);
    setQuizAttemptCount((current) => current + 1);
    if (!firstAttempt) {
      setNotice(isCorrect ? "重新作答正确。" : "仍未答对，可以再次重新作答。");
      return;
    }
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

  function retryQuiz() {
    if (quizSelected === null || quizSelected === quiz.correct) return;
    setQuizSelected(null);
    setNotice("请重新选择答案。");
  }

  function openLookup(queryText: string) {
    const normalized = normalizeLookupQuery(queryText);
    if (!normalized) return;
    const greWord = wordByHeadword.get(normalized);
    const local = dictionary?.entries[normalized];
    let phrase: [string, string] | undefined;
    if (!local && normalized.includes(" ")) {
      const first = dictionary?.entries[normalized.split(" ")[0]];
      phrase = first?.phrases.find(([value]) => normalizeLookupQuery(value) === normalized);
    }
    setLookup({
      query: queryText.trim(),
      normalized,
      source: greWord && (local || phrase)
        ? "GRE 3000 + ECDICT/COW/WordNet 离线词典"
        : greWord
          ? "GRE 3000 已审核词库"
        : local || phrase
          ? "ECDICT/COW/WordNet 离线词典"
          : dictionaryStatus === "loading"
            ? "内置词典载入中"
            : dictionaryStatus === "error"
              ? "内置词典载入失败"
              : "本地词典",
      headword: greWord?.word ?? local?.word ?? phrase?.[0] ?? queryText.trim(),
      phonetic: greWord?.phonetic ?? local?.phonetic ?? "",
      greTranslation: greWord?.definition_zh ?? "",
      greDefinition: greWord?.definition_en ?? "",
      greExampleEn: greWord?.example_en ?? "",
      greExampleZh: greWord?.example_zh ?? "",
      offlineTranslation: local?.translation ?? phrase?.[1] ?? "",
      offlineDefinition: local?.definition ?? "",
      offlineSenses: local?.senses ?? phraseDictionarySenses(phrase),
      exchange: local?.exchange ?? "",
      phrases: local?.phrases ?? [],
      greWordId: greWord?.id,
      onlineStatus: "idle",
    });
    setSelectionText("");
    window.getSelection()?.removeAllRanges();
  }

  function captureSelection(event: PointerEvent<HTMLElement>) {
    const scope = event.currentTarget;
    window.requestAnimationFrame(() => {
      const selection = window.getSelection();
      const text = selection?.toString().replace(/\s+/g, " ").trim() ?? "";
      if (!selection || selection.rangeCount === 0 || !text || text.length > 500) {
        setSelectionText("");
        return;
      }
      const ancestor = selection.getRangeAt(0).commonAncestorContainer;
      const element = ancestor.nodeType === Node.ELEMENT_NODE ? ancestor as Element : ancestor.parentElement;
      if (!element || !scope.contains(element) || !element.closest("[data-lookup-scope]")) {
        setSelectionText("");
        return;
      }
      setSelectionText(text);
    });
  }

  async function translateLookup(queryText: string) {
    const cacheKey = queryText.trim().toLowerCase();
    const cached = translationCache.current.get(cacheKey);
    if (cached) {
      setLookup((current) => current && current.query === queryText ? { ...current, onlineStatus: "ready", onlineTranslation: cached, onlineError: undefined } : current);
      return;
    }
    setLookup((current) => current && current.query === queryText ? { ...current, onlineStatus: "loading", onlineError: undefined } : current);
    try {
      let translation = "";
      try {
        const response = await fetchWithTimeout(
          apiUrl("/api/translate"),
          {
            method: "POST",
            headers: { "content-type": "application/json" },
            body: JSON.stringify({ text: queryText }),
          },
          "翻译请求超时，请检查网络后重试。",
        );
        const payload = await response.json() as { translation?: string; error?: string };
        if (!response.ok || !payload.translation) throw new Error(payload.error || `HTTP ${response.status}`);
        translation = payload.translation;
      } catch {
        translation = await translateViaMyMemoryDirect(queryText);
      }
      translationCache.current.set(cacheKey, translation);
      setLookup((current) => current && current.query === queryText ? { ...current, onlineStatus: "ready", onlineTranslation: translation, onlineError: undefined } : current);
    } catch (error) {
      setLookup((current) => current && current.query === queryText ? { ...current, onlineStatus: "error", onlineError: errorMessage(error, "联网翻译暂时不可用。") } : current);
    }
  }

  function translateSelection() {
    const text = selectionText;
    if (!text) return;
    openLookup(text);
    void translateLookup(text);
  }

  function completeRound() {
    const firstScopeWordId = studyQueue[0]?.id;
    updateProgress((current) => ({
      ...current,
      lists: Object.fromEntries(
        Object.entries(current.lists).map(([key, value]) => [
          key,
          selectedListSet.has(key)
            ? {
                ...value,
                completed_count: value.completed_count + 1,
                current_word_id: firstWordIdByList.get(key) ?? value.current_word_id,
              }
            : value,
        ]),
      ),
      settings: firstScopeWordId === undefined
        ? current.settings
        : {
            ...current.settings,
            study_star_current_word_id: String(firstScopeWordId),
          },
    }));
    setNotice(`${studyScopeLabel} 已完成一轮，所选 List 次数均已增加。`);
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
  const showCorrectQuizReview = mode === "quiz" && quizSelected === quiz.correct;
  const wordListCandidates = wordListMachine7Only
    ? data.words.filter((word) => word.machine7)
    : data.words;
  const normalizedWordQuery = query.trim().toLowerCase();
  const wordListMatches = normalizedWordQuery
    ? wordListCandidates.filter((word) => word.word.toLowerCase().includes(normalizedWordQuery))
    : wordListCandidates;
  const wordListViewKey = `${wordListMachine7Only ? "machine7" : "all"}:${normalizedWordQuery}`;
  const wordListLimit = wordListWindow.key === wordListViewKey
    ? wordListWindow.limit
    : WORD_LIST_BATCH_SIZE;
  const filteredWords = wordListMatches.slice(0, wordListLimit);
  const canLoadMoreWords = filteredWords.length < wordListMatches.length;
  const displayedLookup = lookup
    ? dictionaryEntryForDisplay(lookup.offlineSenses, lookup.offlineTranslation)
    : { senses: [], summaryTranslation: "" };
  const displayedLookupSenses = displayedLookup.senses;

  return (
    <main className="app-shell">
      <header className="topbar">
        <button className="brand" onClick={() => setScreen("home")} aria-label="返回首页">
          <span className="brand-mark">G</span>
          <span><strong>GRE 3000 Vocabulary Trainer</strong><small>原书词序 · 离线可用</small></span>
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
            <div className="section-heading"><div><span>本次学习</span><h2>{studySelectionLabel}</h2></div><em>{studyQueue.length} 词</em></div>
            <span className="field-label">学习 List（可多选）</span>
            <details className="list-scope-picker">
              <summary><span>List 范围</span><strong>{studyScopeLabel}</strong></summary>
              <div className="scope-toolbar">
                <button type="button" onClick={() => setListScope(data.lists.map((item) => item.key))}>选择全部 List</button>
                <span>已选 {selectedListKeys.length} / {data.lists.length}</span>
              </div>
              <div className="scope-list-grid">
                {data.lists.map((item) => (
                  <label className={selectedListSet.has(item.key) ? "scope-list active" : "scope-list"} key={item.key}>
                    <input type="checkbox" checked={selectedListSet.has(item.key)} onChange={() => toggleList(item.key)} />
                    <span><strong>{item.label}</strong><small>{machine7Only ? `${listMachine7Counts.get(item.key) ?? 0} 个重点词` : `${item.count} 词`}</small></span>
                  </label>
                ))}
              </div>
            </details>

            <span className="field-label">词库范围</span>
            <div className="filter-row priority-filter" role="group" aria-label="机经 7.0 重点词筛选">
              <button className={!machine7Only ? "filter active" : "filter"} aria-pressed={!machine7Only} onClick={() => setSetting("study_machine7_only", "0")}>全部单词 <small>{scopeWords.length}</small></button>
              <button className={machine7Only ? "filter active" : "filter"} aria-pressed={machine7Only} onClick={() => setSetting("study_machine7_only", "1")}>仅机经 7.0 重点词 <small>{machine7Count}</small></button>
            </div>

            <span className="field-label">学习模式</span>
            <div className="mode-grid">
              {MODES.map((item) => (
                <button className={mode === item.key ? "mode active" : "mode"} key={item.key} onClick={() => selectMode(item.key)}>
                  <strong>{item.label}</strong><small>{item.hint}</small>
                </button>
              ))}
            </div>

            <span className="field-label">星级筛选（可多选）</span>
            <div className="filter-row">
              <button className={allStarsSelected ? "filter active" : "filter"} onClick={() => setSetting("study_filter", "all")}>全部 <small>{studyBaseWords.length}</small></button>
              {[0, 1, 2, 3].map((rating) => (
                <button className={selectedStarRatings.includes(rating) && !allStarsSelected ? "filter active" : "filter"} onClick={() => toggleStarRating(rating)} key={rating}>
                  {rating ? "★".repeat(rating) : "0 星"} <small>{starCounts[rating]}</small>
                </button>
              ))}
            </div>
            <button className="primary" onClick={startStudy} disabled={!studyQueue.length}>开始学习 <span>→</span></button>
            {!studyQueue.length && <p className="empty-filter-note" role="status">当前组合下没有单词，请更换 List、关闭“仅机经 7.0 重点词”或调整星级。</p>}
            <p className="resume-note">
              {isFullListStudy && selectedListKeys.length === 1
                ? `已背 ${progress.lists[selectedListKeys[0]]?.completed_count ?? 0} 次 · 自动记住当前位置`
                : `${studySelectionLabel} · ${studyQueue.length} 个符合条件的单词`}
            </p>
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
            <span>{studySelectionLabel} · {Math.max(activeQueueIndex + 1, 1)} / {studyQueue.length}</span>
          </div>
          <div className="progress-track"><span style={{ width: `${Math.max(3, ((activeQueueIndex + 1) / Math.max(studyQueue.length, 1)) * 100)}%` }} /></div>
          <p className="swipe-hint">← 左右滑动切换单词 →</p>

          <div className="study-mode-switcher">
            <span>切换模式</span>
            <div role="group" aria-label="学习模式">
              {MODES.map((item) => (
                <button
                  className={mode === item.key ? "active" : ""}
                  key={item.key}
                  onClick={() => selectMode(item.key)}
                  aria-pressed={mode === item.key}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>

          <div className="study-actions">
            <button onClick={() => move(-1)} disabled={activeQueueIndex === 0}>← 上一词</button>
            {activeQueueIndex >= studyQueue.length - 1
              ? isFullListStudy
                ? <button className="finish" onClick={completeRound}>完成本轮</button>
                : <button className="finish" onClick={() => { setNotice(`${studySelectionLabel} 的筛选学习已完成。`); setScreen("home"); }}>完成筛选学习</button>
              : <button className="next" onClick={() => move(1)}>下一词 →</button>}
          </div>
          {mode === "quiz" && quizSelected !== null && quizSelected !== quiz.correct && (
            <button className="quiz-retry study-retry" onClick={retryQuiz}>重新作答</button>
          )}

          <article
            className="word-card"
            onPointerDown={startStudySwipe}
            onPointerUp={finishStudySwipe}
            onPointerCancel={() => { studySwipeStart.current = null; }}
          >
            <div className="word-flags">
              <span>#{activeWord.order}</span>
              {activeWord.machine7 && <em>机经 7.0 重点</em>}
              <button className="star-button" onClick={() => cycleStar(activeWord)} aria-label="修改星级">{starText(progress.stars[String(activeWord.id)] ?? 0)}</button>
            </div>
            <div className="word-title-row"><div><h1><LookupQuery text={activeWord.word} onLookup={openLookup} /></h1><p>{activeWord.phonetic}</p></div><button className="speak" onClick={() => speak(activeWord.word)} aria-label="朗读单词">▶</button></div>

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
                        const choiceWord = wordMap.get(choice.wordId);
                        const displayedChoice = answered && index === quiz.correct
                          ? meaningWithPartsOfSpeech(choice.text, choiceWord?.definition_en ?? "")
                          : choice.text;
                        return (
                          <div className="quiz-choice-row" key={choice.wordId}>
                            <button className={className} disabled={answered} onClick={() => answerQuiz(index)}>
                              <span>{String.fromCharCode(65 + index)}</span>
                              <b>{displayedChoice}</b>
                            </button>
                            <button
                              className="quiz-entry"
                              onClick={() => setGrePreviewWordId(choice.wordId)}
                              aria-label={`查看选项 ${String.fromCharCode(65 + index)} 对应的 GRE 词条`}
                            >
                              查看 GRE 词条
                            </button>
                          </div>
                        );
                      })}
                </div>
              </>
            )}

            {showCorrectQuizReview && (
              <div className="answer-block quiz-review">
                {activeWord.example_en && <div className="example"><div className="example-heading"><span>例句</span><button onClick={() => speak(activeWord.example_en)} aria-label="朗读完整英文例句">▶ 音源 1</button></div><p><LookupText text={activeWord.example_en} onLookup={openLookup} /></p><small>{activeWord.example_zh}</small></div>}
              </div>
            )}

            {showAnswer && (
              <div className="answer-block">
                <p className="definition-en"><LookupText text={activeWord.definition_en} onLookup={openLookup} /></p>
                <p className="definition-zh">{activeWord.definition_zh}</p>
                {mode === "reading" && activeWord.synonyms && <div className="detail-line"><span>近义词</span><p><LookupText text={activeWord.synonyms} onLookup={openLookup} /></p></div>}
                {mode === "reading" && activeWord.example_en && <div className="example"><div className="example-heading"><span>例句</span><button onClick={() => speak(activeWord.example_en)} aria-label="朗读完整英文例句">▶ 音源 1</button></div><p><LookupText text={activeWord.example_en} onLookup={openLookup} /></p><small>{activeWord.example_zh}</small></div>}
              </div>
            )}

            {relationVisible && (
              <div className="relations">
                {activeWord.equivalents.length > 0 && <Relation title="真经等价词" ids={activeWord.equivalents} wordMap={wordMap} onOpen={setGrePreviewWordId} onLookup={openLookup} />}
                {activeWord.roots.map((family) => <Relation key={family.root} title={`词根 ${family.root}`} ids={family.words} wordMap={wordMap} onOpen={setGrePreviewWordId} onLookup={openLookup} />)}
                {activeWord.lookalikes.length > 0 && <Relation title="近形异义词" ids={activeWord.lookalikes} wordMap={wordMap} onOpen={setGrePreviewWordId} onLookup={openLookup} />}
              </div>
            )}
          </article>

          <div className="study-jumps">
            <button onClick={() => jumpToQueueIndex(0)} disabled={activeQueueIndex === 0}>⇤ 到{isFullListStudy ? " List" : "筛选"}开头</button>
            <button onClick={() => jumpToQueueIndex(studyQueue.length - 1)} disabled={activeQueueIndex >= studyQueue.length - 1}>到{isFullListStudy ? " List" : "筛选"}结尾 ⇥</button>
          </div>
        </section>
      )}

      {screen === "words" && (
        <section className="page words-page">
          <div className="page-title"><p className="eyebrow">WORD INDEX</p><h1>完整词表</h1><span>共 {data.record_count.toLocaleString()} 词，按原书词序</span></div>
          <input className="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索单词，例如 proselytize" autoCapitalize="none" />
          <button
            className={wordListMachine7Only ? "index-priority-filter active" : "index-priority-filter"}
            aria-pressed={wordListMachine7Only}
            onClick={() => setSetting("word_list_machine7_only", wordListMachine7Only ? "0" : "1")}
          >
            <span>仅显示机经 7.0 重点词</span><small>{wordListMachine7Only ? "已开启" : `共 ${totalMachine7Count.toLocaleString()} 词`}</small>
          </button>
          <div className="word-list" onPointerUp={captureSelection}>
            {filteredWords.map((word) => (
              <button key={word.id} onClick={() => {
                if (!window.getSelection()?.toString().trim()) openWord(word);
              }}>
                <span className="word-order">{word.order}</span>
                <span className="word-main"><strong><LookupQuery text={word.word} onLookup={openLookup} /></strong><small>{word.definition_zh || <LookupText text={word.definition_en} onLookup={openLookup} />}</small></span>
                {word.machine7 && <em>重点</em>}
                <span className="word-star">{starText(progress.stars[String(word.id)] ?? 0)}</span>
              </button>
            ))}
          </div>
          {!filteredWords.length && <p className="word-list-empty" role="status">没有符合当前搜索和重点词条件的单词。</p>}
          {canLoadMoreWords && (
            <button
              className="word-list-more"
              onClick={() => setWordListWindow({ key: wordListViewKey, limit: wordListLimit + WORD_LIST_BATCH_SIZE })}
            >
              加载更多 <small>已显示 {filteredWords.length.toLocaleString()} / {wordListMatches.length.toLocaleString()}</small>
            </button>
          )}
          {!!wordListMatches.length && (
            <p className="list-hint">
              已显示 {filteredWords.length.toLocaleString()} / {wordListMatches.length.toLocaleString()} 词
              {wordListMachine7Only ? " · 仅机经 7.0 重点词，按原书词序" : !query ? " · 输入关键词可检索全部词库" : ""}
            </p>
          )}
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

      {selectionText && !lookup && (
        <button className="selection-translate" onClick={translateSelection}>
          翻译“{selectionText.length > 28 ? `${selectionText.slice(0, 28)}…` : selectionText}”
        </button>
      )}

      {lookup && (
        <div className="lookup-backdrop" onClick={() => setLookup(null)}>
          <section className="lookup-sheet" role="dialog" aria-modal="true" aria-label={`${lookup.headword} 的释义`} onClick={(event) => event.stopPropagation()}>
            <div className="lookup-handle" />
            <header>
              <div><h2>{lookup.headword}</h2>{lookup.phonetic && <p>{lookup.phonetic}</p>}</div>
              <button onClick={() => setLookup(null)} aria-label="关闭词典">×</button>
            </header>
            <span className="lookup-source">{lookup.source}</span>
            {lookup.greTranslation && (
              <section className="lookup-dictionary-section lookup-gre">
                <h3>GRE 3000 已审核释义</h3>
                <div className="lookup-meaning">{lookup.greTranslation}</div>
                {lookup.greDefinition && <div className="lookup-definition"><LookupText text={lookup.greDefinition} onLookup={openLookup} /></div>}
                {lookup.greExampleEn && (
                  <div className="lookup-sense-example">
                    <span>原书例句</span>
                    <p><LookupText text={lookup.greExampleEn} onLookup={openLookup} /></p>
                    {lookup.greExampleZh && <small>{lookup.greExampleZh}</small>}
                  </div>
                )}
              </section>
            )}
            {(lookup.offlineTranslation || lookup.offlineSenses.length > 0) && (
              <section className="lookup-dictionary-section lookup-offline">
                <h3>离线词典 · ECDICT 中文总览 + COW 逐义项中文 + WordNet 英文义项/例句</h3>
                {displayedLookup.summaryTranslation && <div className="lookup-meaning">{displayedLookup.summaryTranslation}</div>}
                {lookup.offlineSenses.length > 0 && (
                  <div className="lookup-senses">
                    {displayedLookupSenses.map(({ sense, displayTranslation }, senseIndex) => (
                      <article key={`${sense.part_of_speech}-${senseIndex}`}>
                        <div className="lookup-sense-title">
                          <span>义项 {senseIndex + 1}</span>
                          {sense.part_of_speech && <em>{sense.part_of_speech}</em>}
                        </div>
                        {displayTranslation && <strong>{displayTranslation}</strong>}
                        {sense.definition && <p className="lookup-sense-definition"><LookupText text={sense.definition} onLookup={openLookup} /></p>}
                        {sense.examples.map((example, exampleIndex) => {
                          const contextOnly = example.source.startsWith("释义语境");
                          return (
                            <div className="lookup-sense-example" key={`${example.text}-${exampleIndex}`}>
                              <span>{contextOnly ? "释义语境提示" : `例句 ${exampleIndex + 1}`} · {example.source}</span>
                              <p><LookupText text={example.text} onLookup={openLookup} /></p>
                            </div>
                          );
                        })}
                      </article>
                    ))}
                  </div>
                )}
                {lookup.offlineDefinition && !lookup.offlineSenses.length && <div className="lookup-definition"><LookupText text={lookup.offlineDefinition} onLookup={openLookup} /></div>}
              </section>
            )}
            {!lookup.greTranslation && !lookup.offlineTranslation && !lookup.offlineSenses.length && (
              <div className="lookup-meaning missing">
                {(
                lookup.source === "内置词典载入中"
                  ? "离线词典正在载入，请稍候再点一次。"
                  : lookup.source === "内置词典载入失败"
                    ? "离线词典载入失败；GRE 主词表仍可查询，也可使用联网翻译。"
                    : "内置词典暂未收录，可使用联网翻译。"
                )}
              </div>
            )}
            {lookup.exchange && <p className="lookup-exchange">词形变化：{lookup.exchange}</p>}
            {lookup.phrases.length > 0 && <div className="lookup-phrases"><h3>常用词组</h3>{lookup.phrases.map(([phrase, translation]) => <div key={phrase}><strong><LookupText text={phrase} onLookup={openLookup} /></strong><span>{translation}</span></div>)}</div>}
            {lookup.onlineStatus !== "idle" && (
              <div className={`lookup-online ${lookup.onlineStatus}`}>
                <h3>联网翻译</h3>
                {lookup.onlineStatus === "loading" && <p>正在翻译…</p>}
                {lookup.onlineStatus === "ready" && <p>{lookup.onlineTranslation}</p>}
                {lookup.onlineStatus === "error" && <p>翻译失败：{lookup.onlineError}</p>}
              </div>
            )}
            <p className="lookup-privacy">
              点词释义来自本地；只有点击联网翻译时，当前文字才会发送给第三方 MyMemory。本站后端限流时，浏览器会直接连接该服务重试。
              <br /><a href="/ECDICT-LICENSE.txt" target="_blank" rel="noreferrer">ECDICT 许可</a> · <a href="/COW-LICENSE.txt" target="_blank" rel="noreferrer">Chinese Open Wordnet 0.9 许可</a> · <a href="/WORDNET-LICENSE.txt" target="_blank" rel="noreferrer">WordNet 3.0 许可</a>
            </p>
            <div className="lookup-actions">
              {lookup.greWordId && <button onClick={() => { setGrePreviewWordId(lookup.greWordId!); setLookup(null); }}>打开 GRE 词条</button>}
              <button onClick={() => navigator.clipboard?.writeText([
                lookup.headword,
                lookup.greTranslation,
                lookup.greDefinition,
                displayedLookup.summaryTranslation,
                ...displayedLookupSenses.flatMap(({ sense, displayTranslation }) => [displayTranslation, sense.definition, ...sense.examples.map((example) => example.text)]),
                lookup.onlineTranslation,
              ].filter(Boolean).join("\n"))}>复制</button>
              <button className="translate" disabled={lookup.onlineStatus === "loading"} onClick={() => void translateLookup(lookup.query)}>{lookup.onlineStatus === "loading" ? "翻译中…" : "联网翻译"}</button>
            </div>
          </section>
        </div>
      )}

      {grePreviewWord && (
        <GreWordPreview
          word={grePreviewWord}
          wordMap={wordMap}
          closeLabel={screen === "study" && mode === "quiz" ? "返回原题" : "关闭词条"}
          onClose={() => setGrePreviewWordId(null)}
          onOpen={(wordId) => setGrePreviewWordId(wordId)}
          onLookup={(queryText) => {
            setGrePreviewWordId(null);
            openLookup(queryText);
          }}
          onSpeak={speak}
        />
      )}

      <nav className="bottom-nav" aria-label="主导航">
        <button className={screen === "home" || screen === "study" ? "active" : ""} onClick={() => setScreen("home")}><span>⌂</span>学习</button>
        <button className={screen === "words" ? "active" : ""} onClick={() => setScreen("words")}><span>≡</span>词表</button>
        <button className={screen === "settings" ? "active" : ""} onClick={() => setScreen("settings")}><span>⚙</span>设置</button>
      </nav>
    </main>
  );
}

function Relation({ title, ids, wordMap, onOpen, onLookup }: { title: string; ids: number[]; wordMap: Map<number, WordEntry>; onOpen: (id: number) => void; onLookup: (word: string) => void }) {
  const unique = [...new Set(ids)].filter((id) => wordMap.has(id));
  if (!unique.length) return null;
  return (
    <div className="relation-block"><span>{title}</span><div>{unique.map((id) => { const word = wordMap.get(id)!; return <button key={id} onClick={() => { if (!window.getSelection()?.toString().trim()) onOpen(id); }}><strong><LookupQuery text={word.word} onLookup={onLookup} /></strong><small>{word.definition_zh || <LookupText text={word.definition_en} onLookup={onLookup} />}</small></button>; })}</div></div>
  );
}

function GreWordPreview({ word, wordMap, closeLabel, onClose, onOpen, onLookup, onSpeak }: { word: WordEntry; wordMap: Map<number, WordEntry>; closeLabel: string; onClose: () => void; onOpen: (id: number) => void; onLookup: (word: string) => void; onSpeak: (text: string) => void }) {
  return (
    <div className="lookup-backdrop gre-preview-backdrop" onClick={onClose}>
      <section className="lookup-sheet gre-preview" role="dialog" aria-modal="true" aria-label={`${word.word} 的 GRE 词条`} onClick={(event) => event.stopPropagation()}>
        <div className="lookup-handle" />
        <header>
          <div>
            <span className="lookup-source">GRE 词条页 · #{word.order}</span>
            <h2><LookupQuery text={word.word} onLookup={onLookup} /></h2>
            {word.phonetic && <p>{word.phonetic}</p>}
          </div>
          <button onClick={onClose} aria-label={closeLabel}>×</button>
        </header>
        {word.machine7 && <div className="gre-preview-priority">机经 7.0 重点词</div>}
        <div className="lookup-meaning">{word.definition_zh}</div>
        <div className="lookup-definition"><LookupText text={word.definition_en} onLookup={onLookup} /></div>
        {word.synonyms && <div className="detail-line"><span>近义词</span><p><LookupText text={word.synonyms} onLookup={onLookup} /></p></div>}
        {word.example_en && (
          <div className="example">
            <div className="example-heading"><span>例句</span><button onClick={() => onSpeak(word.example_en)}>▶ 音源 1</button></div>
            <p><LookupText text={word.example_en} onLookup={onLookup} /></p>
            {word.example_zh && <small>{word.example_zh}</small>}
          </div>
        )}
        <div className="relations">
          {word.equivalents.length > 0 && <Relation title="真经等价词" ids={word.equivalents} wordMap={wordMap} onOpen={onOpen} onLookup={onLookup} />}
          {word.roots.map((family) => <Relation key={family.root} title={`词根 ${family.root}`} ids={family.words} wordMap={wordMap} onOpen={onOpen} onLookup={onLookup} />)}
          {word.lookalikes.length > 0 && <Relation title="近形异义词" ids={word.lookalikes} wordMap={wordMap} onOpen={onOpen} onLookup={onLookup} />}
        </div>
        <div className="lookup-actions"><button onClick={onClose}>{closeLabel}</button></div>
      </section>
    </div>
  );
}

function LookupQuery({ text, className, onLookup }: { text: string; className?: string; onLookup: (query: string) => void }) {
  return (
    <span
      className={`lookup-token${className ? ` ${className}` : ""}`}
      data-lookup-scope
      onClick={(event) => {
        event.stopPropagation();
        if (window.getSelection()?.toString().trim()) return;
        if (lookupClickTimer) window.clearTimeout(lookupClickTimer);
        lookupClickTimer = window.setTimeout(() => {
          lookupClickTimer = null;
          onLookup(text);
        }, 180);
      }}
      onDoubleClick={(event) => {
        event.stopPropagation();
        if (lookupClickTimer) {
          window.clearTimeout(lookupClickTimer);
          lookupClickTimer = null;
        }
        const range = document.createRange();
        range.selectNodeContents(event.currentTarget);
        const selection = window.getSelection();
        selection?.removeAllRanges();
        selection?.addRange(range);
      }}
    >{text}</span>
  );
}
