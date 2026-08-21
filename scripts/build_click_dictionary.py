from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


TOKEN = re.compile(r"[A-Za-z]+(?:['’-][A-Za-z]+)*")
PHRASE = re.compile(r"[A-Za-z][A-Za-z'’ -]{2,60}")
TRANSLATION_PART_OF_SPEECH = re.compile(
    r"^(?P<part>"
    r"(?:n|v|vt|vi|a|adj|ad|adv|prep|conj|pron|num|art|int|aux|abbr)\."
    r")\s*(?P<translation>.+)$",
    re.IGNORECASE,
)
DEFINITION_PART_OF_SPEECH = re.compile(
    r"^(?P<part>"
    r"(?:n|v|vt|vi|a|adj|ad|adv|prep|conj|pron|num|art|int|aux|abbr|s|r)"
    r")\.?\s+(?P<definition>.+)$",
    re.IGNORECASE,
)
WORDNET_DATA_FILES = {
    "n.": "data.noun",
    "v.": "data.verb",
    "adj.": "data.adj",
    "adv.": "data.adv",
}
WORDNET_SYNSET_PARTS = {
    "n.": "n",
    "v.": "v",
    "adj.": "a",
    "adv.": "r",
}
WORDNET_EXAMPLE = re.compile(r'"([^"]+)"')
WORDNET_SYNSET_ID = re.compile(r"^(?P<offset>\d{8})-(?P<part>[nvar])$")
WORDNET_SOURCE = "Princeton WordNet 3.0"
COW_SOURCE = "Chinese Open Wordnet 0.9"
CONTEXT_EXAMPLE_SOURCE = "释义语境（非语料例句）"
DEFAULT_COW_PATH = (
    Path(__file__).resolve().parents[1]
    / "resources"
    / "cow"
    / "wn-data-cmn.tab"
)


@dataclass(frozen=True, slots=True)
class WordNetSenseRecord:
    synset_id: str
    examples: tuple[str, ...]


def _clean(
    value: str,
    *,
    max_lines: int | None,
    max_chars: int | None,
) -> str:
    lines = [
        re.sub(r"\s+", " ", line).strip()
        for line in value.replace("\\n", "\n").splitlines()
    ]
    text = "\n".join(line for line in lines if line)
    if max_chars is not None:
        text = text[:max_chars]
    text = text.strip()
    if max_lines is not None:
        text = "\n".join(text.splitlines()[:max_lines])
    return text


def _canonical_part_of_speech(value: str) -> str:
    part = value.lower().rstrip(".")
    if part in {"v", "vt", "vi", "aux"}:
        return "v."
    if part in {"a", "adj", "s"}:
        return "adj."
    if part in {"ad", "adv", "r"}:
        return "adv."
    return f"{part}." if part else ""


def _translation_lines(value: str) -> tuple[tuple[str, str], ...]:
    values: list[tuple[str, str]] = []
    for raw_line in value.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = TRANSLATION_PART_OF_SPEECH.match(line)
        if match:
            values.append(
                (match.group("part"), match.group("translation").strip())
            )
        else:
            values.append(("", line))
    return tuple(values)


def _definition_lines(value: str) -> tuple[tuple[str, str], ...]:
    values: list[tuple[str, str]] = []
    for raw_line in value.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            continue
        match = DEFINITION_PART_OF_SPEECH.match(line)
        if match:
            values.append(
                (
                    _canonical_part_of_speech(match.group("part")),
                    match.group("definition").strip(),
                )
            )
        elif values:
            # ECDICT occasionally wraps one English definition over several
            # physical lines.  Treat an unprefixed continuation as part of the
            # preceding definition instead of manufacturing a new sense.
            part, previous = values[-1]
            values[-1] = (part, f"{previous} {line}".strip())
        else:
            values.append(("", line))
    return tuple(values)


def _definition_key(value: str) -> str:
    text = re.sub(
        r"\s+",
        " ",
        value.strip().casefold().replace("’", "'"),
    )
    text = re.sub(r"\s*;\s*--?\s*[^;]*$", "", text)
    text = re.sub(r"(?:\s*;\s*){2,}(?:-+\s*[^;]*)?$", "", text)
    text = re.sub(r"\s*([;,:])\s*", r"\1 ", text)
    return text.strip().rstrip(" .")


def _headword_key(value: str) -> str:
    return re.sub(
        r"\s+",
        " ",
        value.lower().replace("_", " ").replace("’", "'").strip(),
    )


def _candidate_headword_keys(headword: str, exchange: str) -> tuple[str, ...]:
    values = [_headword_key(headword)]
    for item in exchange.split("/"):
        marker, separator, value = item.partition(":")
        if separator and marker == "0" and value.strip():
            values.append(_headword_key(value))
    return tuple(dict.fromkeys(value for value in values if value))


def _recorded_word_forms(headword: str, exchange: str) -> tuple[str, ...]:
    values = [_headword_key(headword)]
    for item in exchange.split("/"):
        _marker, separator, value = item.partition(":")
        cleaned = _headword_key(value) if separator else ""
        if cleaned and re.fullmatch(r"[a-z][a-z' -]*", cleaned):
            values.append(cleaned)
    return tuple(dict.fromkeys(value for value in values if value))


def _example_uses_recorded_form(
    example: str,
    *,
    headword: str,
    exchange: str,
) -> bool:
    text = example.casefold().replace("’", "'")
    return any(
        re.search(
            rf"(?<![a-z]){re.escape(form)}(?![a-z])",
            text,
        )
        for form in _recorded_word_forms(headword, exchange)
    )


def _wordnet_base(wordnet_path: Path | None) -> Path | None:
    if wordnet_path is None:
        return None
    candidates = (wordnet_path, wordnet_path / "dict")
    return next(
        (
            candidate
            for candidate in candidates
            if any((candidate / name).is_file() for name in WORDNET_DATA_FILES.values())
        ),
        None,
    )


def _wordnet_sense_index(
    wordnet_path: Path | None,
) -> dict[tuple[str, str, str], tuple[WordNetSenseRecord, ...]]:
    if wordnet_path is None:
        return {}
    base = _wordnet_base(wordnet_path)
    if base is None:
        raise FileNotFoundError(
            f"WordNet data.noun/data.verb files not found below {wordnet_path}"
        )

    values: dict[tuple[str, str, str], list[WordNetSenseRecord]] = defaultdict(
        list
    )
    for part, filename in WORDNET_DATA_FILES.items():
        path = base / filename
        if not path.is_file():
            continue
        with path.open("r", encoding="utf-8") as source:
            for raw_line in source:
                if " | " not in raw_line:
                    continue
                encoded_synset, gloss = raw_line.split(" | ", 1)
                fields = encoded_synset.split()
                if len(fields) < 4:
                    continue
                try:
                    word_count = int(fields[3], 16)
                except ValueError:
                    continue
                if not fields[0].isdigit() or len(fields[0]) != 8:
                    continue
                lemmas = tuple(
                    _headword_key(fields[4 + index * 2])
                    for index in range(word_count)
                    if 4 + index * 2 < len(fields)
                )
                gloss = gloss.strip()
                definition = re.split(r';\s*"', gloss, maxsplit=1)[0]
                examples = tuple(
                    bytes(value, "utf-8").decode("unicode_escape")
                    for value in WORDNET_EXAMPLE.findall(gloss)
                    if value.strip()
                )
                raw_part = fields[2].lower()
                synset_part = WORDNET_SYNSET_PARTS.get(part)
                if raw_part == "s":
                    synset_part = "a"
                if synset_part is None:
                    continue
                synset_id = f"{fields[0]}-{synset_part}"
                for lemma in lemmas:
                    key = (lemma, part, _definition_key(definition))
                    record = WordNetSenseRecord(synset_id, examples)
                    if record not in values[key]:
                        values[key].append(record)
    return {key: tuple(records) for key, records in values.items()}


def _wordnet_example_index(
    wordnet_path: Path | None,
) -> dict[tuple[str, str, str], tuple[str, ...]]:
    """Return the legacy example-only index used by v2 callers/tests."""
    if wordnet_path is None:
        return {}
    records = _wordnet_sense_index(wordnet_path)
    values: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    for key, sense_records in records.items():
        for record in sense_records:
            for example in record.examples:
                if example not in values[key]:
                    values[key].append(example)
    return {key: tuple(examples) for key, examples in values.items()}


def _cow_synset_id(value: str) -> str | None:
    match = WORDNET_SYNSET_ID.fullmatch(value.strip().lower())
    if not match:
        return None
    return f"{match.group('offset')}-{match.group('part')}"


def _cow_translation_index(
    cow_path: Path | None,
) -> dict[str, tuple[str, ...]]:
    """Read Chinese Open Wordnet's synset-to-Chinese lemma table.

    COW 0.9 uses rows such as ``00462092-v<TAB>cmn:lemma<TAB>征服``.
    A few mirrors omit the language prefix or put the lemma in the second
    column, so the parser accepts both forms while ignoring comments and
    non-Chinese rows.
    """
    if cow_path is None:
        return {}
    if not cow_path.is_file():
        raise FileNotFoundError(f"Chinese Open Wordnet file not found: {cow_path}")

    values: dict[str, list[str]] = defaultdict(list)
    with cow_path.open("r", encoding="utf-8-sig") as source:
        for raw_line in source:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            columns = [column.strip() for column in line.split("\t")]
            if len(columns) < 3:
                continue
            synset_id = _cow_synset_id(columns[0])
            if synset_id is None:
                continue
            if columns[1].casefold() not in {"cmn:lemma", "zho:lemma"}:
                continue
            # COW marks detachable Chinese morphology as ``审美+的``.  The
            # plus sign is annotation, not user-facing punctuation.
            translation = columns[2].replace("+", "").strip()
            if translation and translation not in values[synset_id]:
                values[synset_id].append(translation)
    return {key: tuple(items) for key, items in values.items()}


def _context_example(headword: str, definition: str) -> dict[str, str]:
    if definition:
        meaning = " ".join(definition.split()).rstrip(" .")
        text = f'In this context, "{headword}" means {meaning}.'
    else:
        text = (
            f'The word "{headword}" is used here with the meaning shown above.'
        )
    return {"text": text, "source": CONTEXT_EXAMPLE_SOURCE}


def _merge_duplicate_senses(
    senses: list[dict[str, object]],
) -> list[dict[str, object]]:
    merged: list[dict[str, object]] = []
    by_signature: dict[tuple[str, str, str], dict[str, object]] = {}
    for sense in senses:
        signature = (
            str(sense.get("part_of_speech", "")),
            str(sense.get("translation", "")),
            str(sense.get("definition", "")),
        )
        existing = by_signature.get(signature)
        if existing is None:
            copied = {
                **sense,
                "examples": [
                    dict(example)
                    for example in sense.get("examples", [])
                    if isinstance(example, dict)
                ],
            }
            by_signature[signature] = copied
            merged.append(copied)
            continue

        existing_examples = existing["examples"]
        if not isinstance(existing_examples, list):
            existing_examples = []
            existing["examples"] = existing_examples
        seen_examples = {
            (str(example.get("text", "")), str(example.get("source", "")))
            for example in existing_examples
            if isinstance(example, dict)
        }
        for example in sense.get("examples", []):
            if not isinstance(example, dict):
                continue
            example_key = (
                str(example.get("text", "")),
                str(example.get("source", "")),
            )
            if example_key in seen_examples:
                continue
            seen_examples.add(example_key)
            existing_examples.append(dict(example))
    return merged


def _wordnet_records_for_definition(
    *,
    headword: str,
    definition_part: str,
    definition_text: str,
    exchange: str,
    wordnet_senses: dict[
        tuple[str, str, str], tuple[WordNetSenseRecord, ...]
    ],
    wordnet_examples: dict[tuple[str, str, str], tuple[str, ...]] | None = None,
) -> tuple[WordNetSenseRecord, ...]:
    for candidate in _candidate_headword_keys(headword, exchange):
        records = wordnet_senses.get(
            (
                candidate,
                definition_part,
                _definition_key(definition_text),
            ),
            (),
        )
        if records:
            return records
        if wordnet_examples is not None:
            examples = wordnet_examples.get(
                (candidate, definition_part, _definition_key(definition_text)),
                (),
            )
            if examples:
                return (WordNetSenseRecord("", examples),)
    return ()


def _examples_for_definition(
    *,
    headword: str,
    definition_text: str,
    exchange: str,
    records: tuple[WordNetSenseRecord, ...],
) -> list[dict[str, str]]:
    sourced_examples = tuple(
        dict.fromkeys(
            example
            for record in records
            for example in record.examples
            if _example_uses_recorded_form(
                example,
                headword=headword,
                exchange=exchange,
            )
        )
    )
    if sourced_examples:
        return [
            {"text": text, "source": WORDNET_SOURCE}
            for text in sourced_examples
        ]
    return [_context_example(headword, definition_text)]


def _build_senses(
    *,
    headword: str,
    translation: str,
    definition: str,
    exchange: str,
    wordnet_senses: dict[
        tuple[str, str, str], tuple[WordNetSenseRecord, ...]
    ] | None = None,
    cow_translations: dict[str, tuple[str, ...]] | None = None,
    # Kept as a compatibility hook for callers that supplied the pre-v2
    # example-only index directly.
    wordnet_examples: dict[tuple[str, str, str], tuple[str, ...]] | None = None,
) -> list[dict[str, object]]:
    wordnet_senses = wordnet_senses or {}
    cow_translations = cow_translations or {}
    translations = _translation_lines(translation)
    definitions = tuple(
        dict.fromkeys(
            (
                definition_part,
                definition_text,
            )
            for definition_part, definition_text in _definition_lines(definition)
        )
    )
    senses: list[dict[str, object]] = []

    for definition_part, definition_text in definitions:
        records = _wordnet_records_for_definition(
            headword=headword,
            definition_part=definition_part,
            definition_text=definition_text,
            exchange=exchange,
            wordnet_senses=wordnet_senses,
            wordnet_examples=wordnet_examples,
        )
        cow_translation = "；".join(
            dict.fromkeys(
                translation
                for record in records
                for translation in cow_translations.get(record.synset_id, ())
                if translation
            )
        )
        if cow_translation:
            matching_translation = cow_translation
            sense_part = definition_part
        else:
            matching_translation = ""
            sense_part = definition_part
        senses.append(
            {
                "part_of_speech": sense_part,
                "translation": matching_translation,
                "definition": definition_text,
                "examples": _examples_for_definition(
                    headword=headword,
                    definition_text=definition_text,
                    exchange=exchange,
                    records=records,
                ),
            }
        )

    # ECDICT's translation is a headword/POS-level Chinese summary, while its
    # English definitions are individual WordNet senses. Repeating a summary
    # beside every English definition falsely presents it as a precise mapping.
    # The entry-level ``translation`` retains that summary. Only a synset-level
    # bilingual source may populate a definition's ``translation`` above.
    if not definitions:
        for part, translation_text in translations:
            senses.append(
                {
                    "part_of_speech": part,
                    "translation": translation_text,
                    "definition": "",
                    "examples": [_context_example(headword, "")],
                }
            )
    return _merge_duplicate_senses(senses)


def _validate_senses(entries: dict[str, dict[str, object]]) -> None:
    for key, entry in entries.items():
        senses = entry.get("senses")
        if not isinstance(senses, list) or not senses:
            raise ValueError(f"dictionary entry {key!r} has no senses")
        seen_senses: set[tuple[str, str, str]] = set()
        for index, sense in enumerate(senses):
            if not isinstance(sense, dict):
                raise ValueError(
                    f"dictionary entry {key!r} sense {index} is invalid"
                )
            if not str(sense.get("translation", "")).strip() and not str(
                sense.get("definition", "")
            ).strip():
                raise ValueError(
                    f"dictionary entry {key!r} sense {index} has no meaning"
                )
            signature = (
                str(sense.get("part_of_speech", "")),
                str(sense.get("translation", "")),
                str(sense.get("definition", "")),
            )
            if signature in seen_senses:
                raise ValueError(
                    f"dictionary entry {key!r} contains a duplicate sense"
                )
            seen_senses.add(signature)
            examples = sense.get("examples")
            if not isinstance(examples, list) or not examples:
                raise ValueError(
                    f"dictionary entry {key!r} sense {index} has no example"
                )
            seen_examples: set[tuple[str, str]] = set()
            for example in examples:
                if (
                    not isinstance(example, dict)
                    or not str(example.get("text", "")).strip()
                    or not str(example.get("source", "")).strip()
                ):
                    raise ValueError(
                        f"dictionary entry {key!r} sense {index} "
                        "has an invalid example"
                    )
                example_key = (
                    str(example.get("text", "")),
                    str(example.get("source", "")),
                )
                if example_key in seen_examples:
                    raise ValueError(
                        f"dictionary entry {key!r} sense {index} "
                        "contains a duplicate example"
                    )
                seen_examples.add(example_key)


def _rank(row: dict[str, str]) -> tuple[int, int, int, str]:
    def score(name: str) -> int:
        try:
            value = int(row.get(name) or 0)
        except ValueError:
            return 9_999_999
        return value if value > 0 else 9_999_999

    word = row["word"].strip()
    return (min(score("frq"), score("bnc")), len(word), word.count(" "), word)


def _target_tokens(words_path: Path) -> set[str]:
    payload = json.loads(words_path.read_text(encoding="utf-8"))
    fields = (
        "word",
        "definition_en",
        "synonyms",
        "example_en",
    )
    return {
        match.group(0).lower().replace("’", "'")
        for word in payload["words"]
        for field in fields
        for match in TOKEN.finditer(str(word.get(field, "")))
    }


def build_dictionary(
    *,
    words_path: Path,
    ecdict_path: Path,
    output_paths: tuple[Path, ...],
    wordnet_path: Path | None = None,
    cow_path: Path | None = None,
) -> dict[str, int]:
    if cow_path is not None and wordnet_path is None:
        raise ValueError("Chinese Open Wordnet requires a WordNet 3.0 source")
    targets = _target_tokens(words_path)
    wordnet_senses = _wordnet_sense_index(wordnet_path)
    cow_translations = _cow_translation_index(cow_path)
    entries: dict[str, dict[str, object]] = {}
    phrase_candidates: dict[
        str, list[tuple[tuple[int, int, int, str], str, str]]
    ] = defaultdict(list)

    with ecdict_path.open("r", encoding="utf-8", newline="") as source:
        for row in csv.DictReader(source):
            raw_word = row["word"].strip()
            normalized = raw_word.lower().replace("’", "'")
            translation = _clean(
                row.get("translation", ""),
                max_lines=None,
                max_chars=None,
            )
            if not translation:
                continue
            if normalized in targets and " " not in normalized:
                current = entries.get(normalized)
                candidate = {
                    "word": raw_word,
                    "phonetic": _clean(
                        row.get("phonetic", ""), max_lines=1, max_chars=120
                    ),
                    "translation": translation,
                    "definition": _clean(
                        row.get("definition", ""),
                        max_lines=None,
                        max_chars=None,
                    ),
                    "exchange": _clean(
                        row.get("exchange", ""), max_lines=1, max_chars=260
                    ),
                    "phrases": [],
                }
                if current is None or len(translation) > len(
                    str(current["translation"])
                ):
                    entries[normalized] = candidate
                continue

            if (
                " " not in normalized
                or not PHRASE.fullmatch(raw_word)
                or len(normalized.split()) > 5
            ):
                continue
            first = normalized.split()[0].strip("-'")
            if first not in targets:
                continue
            phrase_candidates[first].append(
                (
                    _rank(row),
                    raw_word,
                    _clean(translation, max_lines=None, max_chars=None),
                )
            )

    for key, candidates in phrase_candidates.items():
        if key not in entries:
            continue
        seen: set[str] = set()
        phrases: list[list[str]] = []
        for _rank_value, phrase, translation in sorted(candidates):
            normalized = phrase.lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            phrases.append([phrase, translation])
            if len(phrases) == 5:
                break
        entries[key]["phrases"] = phrases

    for entry in entries.values():
        entry["senses"] = _build_senses(
            headword=str(entry["word"]),
            translation=str(entry["translation"]),
            definition=str(entry["definition"]),
            exchange=str(entry["exchange"]),
            wordnet_senses=wordnet_senses,
            cow_translations=cow_translations,
        )
    _validate_senses(entries)

    payload = {
        "schema": "gre-click-dictionary",
        "version": 2,
        "source": "ECDICT",
        "sources": [
            {
                "name": "ECDICT",
                "role": "词条与词性级中文汇总",
            },
            *(
                [
                    {
                        "name": WORDNET_SOURCE,
                        "role": "英文义项与例句",
                    }
                ]
                if wordnet_path is not None
                else []
            ),
            *(
                [
                    {
                        "name": COW_SOURCE,
                        "role": "按 WordNet 3.0 synset 精确对应的中文同义词",
                    }
                ]
                if cow_path is not None
                else []
            ),
        ],
        "entry_count": len(entries),
        "target_count": len(targets),
        "entries": dict(sorted(entries.items())),
    }
    encoded = json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), sort_keys=False
    )
    for output_path in output_paths:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(encoded, encoding="utf-8")
    return {
        "targets": len(targets),
        "entries": len(entries),
        "missing": len(targets - entries.keys()),
        "phrases": sum(
            len(entry["phrases"]) for entry in entries.values()
        ),
        "senses": sum(len(entry["senses"]) for entry in entries.values()),
        "wordnet_examples": sum(
            1
            for entry in entries.values()
            for sense in entry["senses"]
            for example in sense["examples"]
            if example["source"] == WORDNET_SOURCE
        ),
        "context_examples": sum(
            1
            for entry in entries.values()
            for sense in entry["senses"]
            for example in sense["examples"]
            if example["source"] == CONTEXT_EXAMPLE_SOURCE
        ),
        "cow_translated_senses": sum(
            1
            for entry in entries.values()
            for sense in entry["senses"]
            if sense["translation"] and sense["definition"]
        ),
        "bytes": len(encoded.encode("utf-8")),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the compact offline click-to-lookup dictionary."
    )
    parser.add_argument("--words", required=True, type=Path)
    parser.add_argument("--ecdict", required=True, type=Path)
    parser.add_argument(
        "--wordnet",
        type=Path,
        help=(
            "Optional Princeton WordNet directory containing data.noun, "
            "data.verb, data.adj, and data.adv. Source examples are preferred; "
            "uncovered senses receive an explicitly labelled context example."
        ),
    )
    parser.add_argument(
        "--cow",
        type=Path,
        help=(
            f"Optional {COW_SOURCE} wn-data-cmn.tab. Chinese "
            "lemmas are joined to English definitions by exact WordNet "
            "3.0 synset offset and part of speech. Requires --wordnet. "
            f"Defaults to {DEFAULT_COW_PATH} when that file exists."
        ),
    )
    parser.add_argument("--output", required=True, action="append", type=Path)
    args = parser.parse_args()
    cow_path = args.cow
    if (
        cow_path is None
        and args.wordnet is not None
        and DEFAULT_COW_PATH.is_file()
    ):
        cow_path = DEFAULT_COW_PATH
    summary = build_dictionary(
        words_path=args.words,
        ecdict_path=args.ecdict,
        output_paths=tuple(args.output),
        wordnet_path=args.wordnet,
        cow_path=cow_path,
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
