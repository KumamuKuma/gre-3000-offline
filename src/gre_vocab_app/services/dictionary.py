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
TRANSLATION_PART_OF_SPEECH = re.compile(
    r"^(?P<part>"
    r"(?:n|v|vt|vi|a|adj|ad|adv|prep|conj|pron|num|art|int|aux|abbr)\."
    r")\s*(?P<translation>.+)$",
    re.IGNORECASE,
)
DEFINITION_PART_OF_SPEECH = re.compile(
    r"^(?P<part>"
    r"(?:n|v|vt|vi|a|adj|ad|adv|prep|conj|pron|num|art|int|aux|abbr|s|r)"
    r")(?P<dot>\.)?\s+(?P<definition>.+)$",
    re.IGNORECASE,
)
CONTEXT_EXAMPLE_SOURCE = "释义语境（非语料例句）"
OFFLINE_DICTIONARY_SOURCE = (
    "离线英汉词典（ECDICT 中文总览 · COW 逐义项中文 · "
    "WordNet 英文释义与例句）"
)
GRE_OFFLINE_DICTIONARY_SOURCE = (
    f"GRE 3000 已审核词库 + {OFFLINE_DICTIONARY_SOURCE}"
)


@dataclass(frozen=True, slots=True)
class PhraseMeaning:
    phrase: str
    translation: str


@dataclass(frozen=True, slots=True)
class SenseExample:
    text: str
    source: str


@dataclass(frozen=True, slots=True)
class DictionarySense:
    part_of_speech: str
    translation: str
    definition: str
    examples: tuple[SenseExample, ...]


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
    gre_translation: str = ""
    gre_definition: str = ""
    gre_example_en: str = ""
    gre_example_zh: str = ""
    offline_translation: str = ""
    offline_definition: str = ""
    senses: tuple[DictionarySense, ...] = ()

    @property
    def found(self) -> bool:
        return bool(
            self.translation
            or self.definition
            or self.gre_translation
            or self.gre_definition
            or self.offline_translation
            or self.offline_definition
            or self.senses
        )


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
                or payload.get("version") not in {1, 2}
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

    @staticmethod
    def _canonical_part_of_speech(value: str) -> str:
        part = value.lower().rstrip(".")
        if part in {"v", "vt", "vi", "aux"}:
            return "v"
        if part in {"a", "adj", "s"}:
            return "adj"
        if part in {"ad", "adv", "r"}:
            return "adv"
        return part

    @staticmethod
    def _split_translation_line(value: str) -> tuple[str, str]:
        match = TRANSLATION_PART_OF_SPEECH.match(value.strip())
        if not match:
            return "", value.strip()
        return match.group("part"), match.group("translation").strip()

    @classmethod
    def _definition_lines(
        cls,
        entry: dict[str, object],
    ) -> tuple[tuple[str, str], ...]:
        values: list[tuple[str, str]] = []
        for raw_line in str(entry.get("definition", "")).splitlines():
            is_continuation = bool(raw_line[:1].isspace())
            line = re.sub(r"\s+", " ", raw_line).strip()
            if not line:
                continue
            if is_continuation and values:
                part, previous = values[-1]
                values[-1] = (part, f"{previous} {line}".strip())
                continue
            match = DEFINITION_PART_OF_SPEECH.match(line)
            uppercase_one_letter_code = bool(
                match
                and not match.group("dot")
                and len(match.group("part")) == 1
                and match.group("part") not in {"n", "v", "a", "s", "r"}
            )
            # An unpunctuated leading "a" is ambiguous once indentation has
            # been lost by an old v1 producer (for example, "a certain...").
            # Preserve it as text instead of claiming it is an adjective POS.
            ambiguous_a = bool(
                match
                and match.group("part").casefold() == "a"
                and not match.group("dot")
                and values
            )
            if match and not uppercase_one_letter_code and not ambiguous_a:
                part = cls._canonical_part_of_speech(match.group("part"))
                values.append((part, match.group("definition").strip()))
            else:
                values.append(("", line))
        return tuple(values)

    @staticmethod
    def _context_example(headword: str, definition: str) -> SenseExample:
        if definition:
            meaning = " ".join(definition.split()).rstrip(" .")
            text = f'In this context, "{headword}" means {meaning}.'
        else:
            text = (
                f'The word "{headword}" is used here with the meaning '
                "shown above."
            )
        return SenseExample(text=text, source=CONTEXT_EXAMPLE_SOURCE)

    @classmethod
    def _phrase_senses(
        cls,
        phrase: PhraseMeaning | None,
    ) -> tuple[DictionarySense, ...]:
        if phrase is None:
            return ()
        return (
            DictionarySense(
                part_of_speech="",
                translation=phrase.translation,
                definition="",
                examples=(cls._context_example(phrase.phrase, ""),),
            ),
        )

    @classmethod
    def _find_phrase(
        cls,
        entries: dict[str, dict[str, object]],
        normalized: str,
    ) -> PhraseMeaning | None:
        if " " not in normalized:
            return None
        first = normalized.split()[0]
        return next(
            (
                phrase
                for phrase in cls._phrases(entries.get(first))
                if normalize_query(phrase.phrase) == normalized
            ),
            None,
        )

    @classmethod
    def _senses(
        cls,
        entry: dict[str, object] | None,
        *,
        headword: str,
    ) -> tuple[DictionarySense, ...]:
        if not entry:
            return ()

        encoded_senses = entry.get("senses", [])
        parsed: list[DictionarySense] = []
        if isinstance(encoded_senses, list):
            for raw_sense in encoded_senses:
                if not isinstance(raw_sense, dict):
                    continue
                translation = str(raw_sense.get("translation", "")).strip()
                definition = str(raw_sense.get("definition", "")).strip()
                part = str(raw_sense.get("part_of_speech", "")).strip()
                examples: list[SenseExample] = []
                raw_examples = raw_sense.get("examples", [])
                if isinstance(raw_examples, list):
                    for raw_example in raw_examples:
                        if not isinstance(raw_example, dict):
                            continue
                        text = str(raw_example.get("text", "")).strip()
                        source = str(raw_example.get("source", "")).strip()
                        if text and source:
                            examples.append(SenseExample(text, source))
                if not translation and not definition:
                    continue
                if not examples:
                    examples.append(cls._context_example(headword, definition))
                parsed.append(
                    DictionarySense(
                        part_of_speech=part,
                        translation=translation,
                        definition=definition,
                        examples=tuple(examples),
                    )
                )
        if parsed:
            return tuple(parsed)

        definitions = cls._definition_lines(entry)
        translations = tuple(
            cls._split_translation_line(line)
            for line in str(entry.get("translation", "")).splitlines()
            if line.strip()
        )
        legacy_senses: list[DictionarySense] = []
        for definition_part, definition in definitions:
            legacy_senses.append(
                DictionarySense(
                    part_of_speech=(
                        f"{definition_part}."
                        if definition_part and not definition_part.endswith(".")
                        else definition_part
                    ),
                    translation="",
                    definition=definition,
                    examples=(cls._context_example(headword, definition),),
                )
            )
        if not definitions:
            for part, translation in translations:
                legacy_senses.append(
                    DictionarySense(
                        part_of_speech=part,
                        translation=translation,
                        definition="",
                        examples=(cls._context_example(headword, ""),),
                    )
                )
        return tuple(legacy_senses)

    def lookup(self, query: str) -> LookupResult:
        normalized = normalize_query(query)
        kind = "phrase" if " " in normalized else "word"
        if not normalized:
            return LookupResult(query, "", kind, "本地词典", query)

        entries = self._load()
        entry = entries.get(normalized)
        phrase = self._find_phrase(entries, normalized) if entry is None else None
        gre_word = self._gre_words.get(normalized)
        if gre_word is not None:
            offline_translation = (
                str(entry.get("translation", "")) if entry else ""
            )
            if not offline_translation and phrase is not None:
                offline_translation = phrase.translation
            offline_definition = (
                str(entry.get("definition", "")) if entry else ""
            )
            return LookupResult(
                query=query,
                normalized=normalized,
                kind="word",
                source=(
                    GRE_OFFLINE_DICTIONARY_SOURCE
                    if entry or phrase
                    else "GRE 3000 已审核词库"
                ),
                headword=gre_word.headword,
                phonetic=gre_word.phonetic,
                translation=gre_word.definition_zh,
                definition=gre_word.definition_en,
                exchange=str(entry.get("exchange", "")) if entry else "",
                phrases=self._phrases(entry),
                gre_word_id=gre_word.id,
                gre_translation=gre_word.definition_zh,
                gre_definition=gre_word.definition_en,
                gre_example_en=gre_word.example_en,
                gre_example_zh=gre_word.example_zh,
                offline_translation=offline_translation,
                offline_definition=offline_definition,
                senses=(
                    self._senses(entry, headword=gre_word.headword)
                    if entry
                    else self._phrase_senses(phrase)
                ),
            )

        if entry is not None:
            return LookupResult(
                query=query,
                normalized=normalized,
                kind=kind,
                source=OFFLINE_DICTIONARY_SOURCE,
                headword=str(entry.get("word", normalized)),
                phonetic=str(entry.get("phonetic", "")),
                translation=str(entry.get("translation", "")),
                definition=str(entry.get("definition", "")),
                exchange=str(entry.get("exchange", "")),
                phrases=self._phrases(entry),
                offline_translation=str(entry.get("translation", "")),
                offline_definition=str(entry.get("definition", "")),
                senses=self._senses(
                    entry,
                    headword=str(entry.get("word", normalized)),
                ),
            )

        if phrase is not None:
            return LookupResult(
                query=query,
                normalized=normalized,
                kind=kind,
                source=OFFLINE_DICTIONARY_SOURCE,
                headword=phrase.phrase,
                translation=phrase.translation,
                offline_translation=phrase.translation,
                senses=self._phrase_senses(phrase),
            )

        return LookupResult(
            query=query,
            normalized=normalized,
            kind=kind,
            source="本地词典",
            headword=query.strip(),
        )
