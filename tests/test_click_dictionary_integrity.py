from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _word_forms(key: str, exchange: str) -> tuple[str, ...]:
    values = [key.lower().replace("’", "'")]
    for item in exchange.split("/"):
        _marker, separator, value = item.partition(":")
        cleaned = value.lower().replace("’", "'").strip() if separator else ""
        if cleaned and re.fullmatch(r"[a-z][a-z' -]*", cleaned):
            values.append(cleaned)
    return tuple(dict.fromkeys(values))


def test_checked_in_click_dictionaries_are_identical_complete_version_two_data():
    native_bytes = (ROOT / "resources" / "click_dictionary.json").read_bytes()
    web_bytes = (
        ROOT / "web" / "public" / "data" / "click_dictionary.json"
    ).read_bytes()
    assert native_bytes == web_bytes

    payload = json.loads(native_bytes)
    assert payload["schema"] == "gre-click-dictionary"
    assert payload["version"] == 2
    assert payload["entry_count"] == len(payload["entries"]) == 11_414

    senses = [
        sense
        for entry in payload["entries"].values()
        for sense in entry["senses"]
    ]
    examples = [example for sense in senses for example in sense["examples"]]
    assert len(senses) == 37_343
    assert len(examples) == 42_228
    assert all(sense["translation"] or sense["definition"] for sense in senses)
    assert all(example["text"] and example["source"] for example in examples)
    assert sum(
        example["source"] == "Princeton WordNet 3.0"
        for example in examples
    ) == 19_974
    assert sum(
        example["source"] == "释义语境（非语料例句）"
        for example in examples
    ) == 22_254


def test_every_wordnet_example_contains_the_looked_up_word_or_recorded_form():
    payload = json.loads(
        (ROOT / "resources" / "click_dictionary.json").read_text(
            encoding="utf-8"
        )
    )
    for key, entry in payload["entries"].items():
        forms = _word_forms(key, entry.get("exchange", ""))
        for sense in entry["senses"]:
            for example in sense["examples"]:
                if example["source"] != "Princeton WordNet 3.0":
                    continue
                text = example["text"].lower().replace("’", "'")
                assert any(
                    re.search(
                        rf"(?<![a-z]){re.escape(form)}(?![a-z])",
                        text,
                    )
                    for form in forms
                ), (key, example["text"])


def test_dictionary_licenses_ship_for_native_and_web_distribution():
    for name in ("ECDICT-LICENSE.txt", "WORDNET-LICENSE.txt"):
        native = ROOT / "resources" / name
        web = ROOT / "web" / "public" / name
        assert native.is_file()
        assert web.is_file()
        assert native.read_text(encoding="utf-8").strip() == web.read_text(
            encoding="utf-8"
        ).strip()
