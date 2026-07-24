from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path


TOKEN = re.compile(r"[A-Za-z]+(?:['’-][A-Za-z]+)*")
PHRASE = re.compile(r"[A-Za-z][A-Za-z'’ -]{2,60}")


def _clean(value: str, *, max_lines: int, max_chars: int) -> str:
    lines = [
        re.sub(r"\s+", " ", line).strip()
        for line in value.replace("\\n", "\n").splitlines()
    ]
    text = "\n".join(line for line in lines if line)[:max_chars].strip()
    return "\n".join(text.splitlines()[:max_lines])


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
) -> dict[str, int]:
    targets = _target_tokens(words_path)
    entries: dict[str, dict[str, object]] = {}
    phrase_candidates: dict[
        str, list[tuple[tuple[int, int, int, str], str, str]]
    ] = defaultdict(list)

    with ecdict_path.open("r", encoding="utf-8", newline="") as source:
        for row in csv.DictReader(source):
            raw_word = row["word"].strip()
            normalized = raw_word.lower().replace("’", "'")
            translation = _clean(
                row.get("translation", ""), max_lines=8, max_chars=760
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
                        max_lines=5,
                        max_chars=620,
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
                (_rank(row), raw_word, _clean(translation, max_lines=3, max_chars=280))
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

    payload = {
        "schema": "gre-click-dictionary",
        "version": 1,
        "source": "ECDICT",
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
        "bytes": len(encoded.encode("utf-8")),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the compact offline click-to-lookup dictionary."
    )
    parser.add_argument("--words", required=True, type=Path)
    parser.add_argument("--ecdict", required=True, type=Path)
    parser.add_argument("--output", required=True, action="append", type=Path)
    args = parser.parse_args()
    summary = build_dictionary(
        words_path=args.words,
        ecdict_path=args.ecdict,
        output_paths=tuple(args.output),
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
