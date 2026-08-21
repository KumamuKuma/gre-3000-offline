from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _word_forms(key: str, exchange: str) -> tuple[str, ...]:
    values = [key.lower().replace("’", "'")]
    recorded_markers = {"0", "d", "p", "i", "3", "s", "r", "t", "f"}
    for item in exchange.split("/"):
        marker, separator, value = item.partition(":")
        if marker not in recorded_markers:
            continue
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
    assert payload["target_count"] == 11_633
    assert payload["sources"] == [
        {"name": "ECDICT", "role": "词条与词性级中文汇总"},
        {"name": "Princeton WordNet 3.0", "role": "英文义项与例句"},
        {
            "name": "Chinese Open Wordnet 0.9",
            "role": "按 WordNet 3.0 synset 精确对应的中文同义词",
        },
        {
            "name": "项目内 COW 已审核修正",
            "role": "对高置信 COW 词义翻译错误的可追溯修正",
        },
    ]

    senses = [
        sense
        for entry in payload["entries"].values()
        for sense in entry["senses"]
    ]
    examples = [example for sense in senses for example in sense["examples"]]
    assert len(senses) == 31_551
    assert len(examples) == 36_382
    assert all(sense["translation"] or sense["definition"] for sense in senses)
    assert all(example["text"] and example["source"] for example in examples)
    assert sum(
        bool(sense["translation"] and sense["definition"])
        for sense in senses
    ) == 13_422
    assert sum(
        example["source"] == "Princeton WordNet 3.0"
        for example in examples
    ) == 19_812
    assert sum(
        example["source"] == "释义语境（非语料例句）"
        for example in examples
    ) == 16_570

    entries = payload["entries"]
    expected_curated_translations = {
        ("diaper", "a fabric (usually cotton or linen) with a distinctive woven pattern of small repeated figures"): "菱形花纹布",
        ("apple", "native Eurasian tree widely cultivated in many varieties for its firm rounded edible fruits"): "苹果树",
        ("pounds", "the basic unit of money in Cyprus; equal to 100 cents"): "塞浦路斯镑",
        ("decreasing", "music"): "渐弱的；渐慢的",
    }
    for (word, definition), translation in expected_curated_translations.items():
        matching = [
            sense
            for sense in entries[word]["senses"]
            if sense["definition"] == definition
        ]
        assert len(matching) == 1
        assert matching[0]["translation"] == translation

    assert entries["centralize"]["senses"][0]["translation"] == (
        "使集中；形成中心；把集中起来；集中，聚集；集结"
    )
    for key, entry in entries.items():
        for sense in entry["senses"]:
            lemmas = [
                value.strip()
                for value in sense["translation"].split("；")
                if value.strip()
            ]
            redundant = {
                part.strip()
                for lemma in lemmas
                for part in re.split(r"[，,]", lemma)
                if part.strip() != lemma and part.strip() in lemmas
            }
            assert not redundant, (key, sense["translation"], redundant)

    for contraction in ("can't", "i'd", "i'm", "won't"):
        senses_for_word = entries[contraction]["senses"]
        assert len(senses_for_word) == 1
        assert senses_for_word[0]["part_of_speech"] == ""
        assert senses_for_word[0]["definition"].startswith("A ")


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
    for name in (
        "ECDICT-LICENSE.txt",
        "WORDNET-LICENSE.txt",
        "COW-LICENSE.txt",
    ):
        native = ROOT / "resources" / name
        web = ROOT / "web" / "public" / name
        assert native.is_file()
        assert web.is_file()
        assert native.read_text(encoding="utf-8").strip() == web.read_text(
            encoding="utf-8"
        ).strip()
