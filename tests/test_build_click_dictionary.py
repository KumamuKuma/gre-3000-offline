from __future__ import annotations

import csv
import json

import pytest

from scripts.build_click_dictionary import (
    CONTEXT_EXAMPLE_SOURCE,
    WORDNET_SOURCE,
    _validate_senses,
    build_dictionary,
)


def test_builds_version_two_senses_with_wordnet_and_labelled_fallbacks(
    tmp_path,
):
    words = tmp_path / "words.json"
    words.write_text(
        json.dumps(
            {
                "words": [
                    {
                        "word": "abate",
                        "definition_en": "",
                        "synonyms": "",
                        "example_en": "",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    ecdict = tmp_path / "ecdict.csv"
    with ecdict.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(
            destination,
            fieldnames=(
                "word",
                "phonetic",
                "translation",
                "definition",
                "exchange",
                "frq",
                "bnc",
            ),
        )
        writer.writeheader()
        writer.writerow(
            {
                "word": "abate",
                "phonetic": "əˈbeɪt",
                "translation": "vi. 减弱\n[法] 废除",
                "definition": (
                    "v become less in amount or intensity\n"
                    "v. become less in amount or intensity"
                ),
                "exchange": "d:abated",
                "frq": "100",
                "bnc": "100",
            }
        )
    wordnet = tmp_path / "wordnet"
    wordnet.mkdir()
    (wordnet / "data.verb").write_text(
        "00000001 00 v 01 abate 0 000 | "
        'become less in amount or intensity; "The pain began to abate"; '
        '"The rain let up"\n',
        encoding="utf-8",
    )
    output = tmp_path / "dictionary.json"

    summary = build_dictionary(
        words_path=words,
        ecdict_path=ecdict,
        output_paths=(output,),
        wordnet_path=wordnet,
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    entry = payload["entries"]["abate"]
    assert payload["version"] == 2
    assert entry["translation"] == "vi. 减弱\n[法] 废除"
    assert entry["definition"] == (
        "v become less in amount or intensity\n"
        "v. become less in amount or intensity"
    )
    assert len(entry["senses"]) == 2
    assert entry["senses"][0]["examples"] == [
        {
            "text": "The pain began to abate",
            "source": WORDNET_SOURCE,
        }
    ]
    assert entry["senses"][1]["examples"][0]["source"] == (
        CONTEXT_EXAMPLE_SOURCE
    )
    assert summary["senses"] == 2
    assert summary["wordnet_examples"] == 1
    assert summary["context_examples"] == 1


def test_rejects_any_dictionary_sense_without_an_example():
    with pytest.raises(ValueError, match="has no example"):
        _validate_senses(
            {
                "abate": {
                    "senses": [
                        {
                            "part_of_speech": "v.",
                            "translation": "减弱",
                            "definition": "become less",
                            "examples": [],
                        }
                    ]
                }
            }
        )


def test_rejects_duplicate_senses_after_build_normalization():
    duplicate = {
        "part_of_speech": "v.",
        "translation": "减弱",
        "definition": "become less",
        "examples": [
            {
                "text": 'In this context, "abate" means become less.',
                "source": CONTEXT_EXAMPLE_SOURCE,
            }
        ],
    }
    with pytest.raises(ValueError, match="duplicate sense"):
        _validate_senses(
            {
                "abate": {
                    "senses": [duplicate, dict(duplicate)],
                }
            }
        )
