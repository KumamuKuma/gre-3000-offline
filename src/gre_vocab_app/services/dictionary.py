from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from gre_vocab_app.domain import WordEntry
from gre_vocab_app.paths import PACKAGE_ROOT


WORD = re.compile(r"[A-Za-z]+(?:['’-][A-Za-z]+)*")


@dataclass(frozen=True, slots=True)
class PhraseMeaning:
    phrase: str
    translation: str


@dataclass(frozen=True, slots=True)
class LookupResult:
    query: str
    normalized: str
    kind: str
    source: str
    headword: str
    phonetic: str = ""
    translation: str = ""
    definition: str = ""
    exchange: str = ""
    phrases: tuple[PhraseMeaning, ...] = ()
    gre_word_id: int | None = None

    @property
    def found(self) -> bool:
        return bool(self.translation or self.definition)


def normalize_query(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).replace("’", "'")
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return ""
    if " " in text:
        return text.strip(" \t\r\n.,;:!?\"“”‘’()[]{}").lower()
    match = WORD.search(text)
    return match.group(0).lower() if match else ""


class DictionaryService:
    def __init__(self, dictionary_path: Path | None = None):
        self._path = dictionary_path or self.default_path()
        self._entries: dict[str, dict[str, object]] | None = None
        self._gre_words: dict[str, WordEntry] = {}

    @staticmethod
    def default_path() -> Path:
        packaged = PACKAGE_ROOT / "data" / "click_dictionary.json"
        if packaged.exists():
            return packaged
        return PACKAGE_ROOT.parents[1] / "resources" / "click_dictionary.json"

    def set_gre_words(self, words: Iterable[WordEntry]) -> None:
        self._gre_words = {
            normalize_query(word.headword): word
            for word in words
            if normalize_query(word.headword)
        }

    def _load(self) -> dict[str, dict[str, object]]:
        if self._entries is None:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
            if (
                payload.get("schema") != "gre-click-dictionary"
                or payload.get("version") != 1
            ):
                raise ValueError("unsupported click dictionary format")
            self._entries = dict(payload.get("entries", {}))
        return self._entries

    @staticmethod
    def _phrases(entry: dict[str, object] | None) -> tuple[PhraseMeaning, ...]:
        if not entry:
            return ()
        values = entry.get("phrases", [])
        return tuple(
            PhraseMeaning(str(item[0]), str(item[1]))
            for item in values
            if isinstance(item, list)
            and len(item) == 2
            and item[0]
            and item[1]
        )

    def lookup(self, query: str) -> LookupResult:
        normalized = normalize_query(query)
        kind = "phrase" if " " in normalized else "word"
        if not normalized:
            return LookupResult(query, "", kind, "本地词典", query)

        entries = self._load()
        entry = entries.get(normalized)
        gre_word = self._gre_words.get(normalized)
        if gre_word is not None:
            return LookupResult(
                query=query,
                normalized=normalized,
                kind="word",
                source="GRE 3000 已审核词库",
                headword=gre_word.headword,
                phonetic=gre_word.phonetic,
                translation=gre_word.definition_zh,
                definition=gre_word.definition_en,
                exchange=str(entry.get("exchange", "")) if entry else "",
                phrases=self._phrases(entry),
                gre_word_id=gre_word.id,
            )

        if entry is not None:
            return LookupResult(
                query=query,
                normalized=normalized,
                kind=kind,
                source="ECDICT 离线英汉词典",
                headword=str(entry.get("word", normalized)),
                phonetic=str(entry.get("phonetic", "")),
                translation=str(entry.get("translation", "")),
                definition=str(entry.get("definition", "")),
                exchange=str(entry.get("exchange", "")),
                phrases=self._phrases(entry),
            )

        if kind == "phrase":
            first = normalized.split()[0]
            for phrase in self._phrases(entries.get(first)):
                if normalize_query(phrase.phrase) == normalized:
                    return LookupResult(
                        query=query,
                        normalized=normalized,
                        kind=kind,
                        source="ECDICT 离线英汉词典",
                        headword=phrase.phrase,
                        translation=phrase.translation,
                    )

        return LookupResult(
            query=query,
            normalized=normalized,
            kind=kind,
            source="本地词典",
            headword=query.strip(),
        )
