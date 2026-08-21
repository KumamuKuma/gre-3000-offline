from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from gre_vocab_app.services.dictionary import (
    DictionaryService,
    normalize_query,
)


def _dictionary(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "schema": "gre-click-dictionary",
                "version": 1,
                "entries": {
                    "work": {
                        "word": "work",
                        "phonetic": "wɜːk",
                        "translation": "n. 工作；v. 工作",
                        "definition": "activity involving effort",
                        "exchange": "p:worked/i:working",
                        "phrases": [
                            ["work out", "锻炼；解决"],
                            ["work on", "从事；致力于"],
                        ],
                    },
                    "inevitable": {
                        "word": "inevitable",
                        "phonetic": "ɪnˈevɪtəbl",
                        "translation": "不可避免的",
                        "definition": "certain to happen",
                        "exchange": "",
                        "phrases": [],
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def test_normalize_query_handles_curly_apostrophes_and_sentence_punctuation():
    assert normalize_query("  Worker’s, ") == "worker's"
    assert normalize_query("  work out! ") == "work out"


def test_gre_entry_takes_priority_and_keeps_offline_phrases(
    tmp_path: Path, sample_word
):
    service = DictionaryService(_dictionary(tmp_path / "dictionary.json"))
    service.set_gre_words([sample_word])

    result = service.lookup("inevitable")

    assert result.source == "GRE 3000 已审核词库 + ECDICT 离线英汉词典"
    assert result.translation == sample_word.definition_zh
    assert result.gre_translation == sample_word.definition_zh
    assert result.gre_definition == sample_word.definition_en
    assert result.gre_example_en == sample_word.example_en
    assert result.offline_translation == "不可避免的"
    assert result.offline_definition == "certain to happen"
    assert result.senses
    assert all(sense.examples for sense in result.senses)
    assert result.gre_word_id == sample_word.id


def test_common_word_and_exact_phrase_are_available_offline(tmp_path: Path):
    service = DictionaryService(_dictionary(tmp_path / "dictionary.json"))

    word = service.lookup("worked")
    common = service.lookup("work")
    phrase = service.lookup("work out")

    assert not word.found
    assert common.translation == "n. 工作；v. 工作"
    assert common.offline_translation == common.translation
    assert common.senses
    assert all(sense.examples for sense in common.senses)
    assert common.phrases[0].phrase == "work out"
    assert phrase.translation == "锻炼；解决"
    assert phrase.kind == "phrase"


def test_gre_phrase_keeps_reviewed_entry_and_adds_offline_phrase_meaning(
    tmp_path: Path,
    sample_word,
):
    path = _dictionary(tmp_path / "dictionary.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["entries"]["ad"] = {
        "word": "ad",
        "phonetic": "æd",
        "translation": "n. 广告",
        "definition": "n. a public promotion",
        "exchange": "",
        "phrases": [["ad hoc", "特别地；临时"]],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    service = DictionaryService(path)
    gre_phrase = replace(
        sample_word,
        headword="ad hoc",
        definition_en="adj. formed for a particular purpose",
        definition_zh="特别的；临时的",
    )
    service.set_gre_words([gre_phrase])

    result = service.lookup("ad hoc")

    assert result.source == "GRE 3000 已审核词库 + ECDICT 离线英汉词典"
    assert result.gre_word_id == gre_phrase.id
    assert result.gre_translation == gre_phrase.definition_zh
    assert result.offline_translation == "特别地；临时"
    assert result.senses[0].translation == result.offline_translation
    assert result.senses[0].examples[0].source == "释义语境（非语料例句）"
    assert "ad hoc" in result.senses[0].examples[0].text


def test_version_two_senses_preserve_source_examples_and_fill_missing_ones(
    tmp_path: Path,
):
    path = tmp_path / "dictionary-v2.json"
    path.write_text(
        json.dumps(
            {
                "schema": "gre-click-dictionary",
                "version": 2,
                "entries": {
                    "work": {
                        "word": "work",
                        "phonetic": "wɜːk",
                        "translation": "n. 工作\nv. 运转",
                        "definition": "n. activity involving effort\n"
                        "v. function correctly",
                        "exchange": "",
                        "phrases": [],
                        "senses": [
                            {
                                "part_of_speech": "n.",
                                "translation": "工作",
                                "definition": "activity involving effort",
                                "examples": [
                                    {
                                        "text": "It is difficult work.",
                                        "source": "Princeton WordNet 3.0",
                                    }
                                ],
                            },
                            {
                                "part_of_speech": "v.",
                                "translation": "运转",
                                "definition": "function correctly",
                                "examples": [],
                            },
                        ],
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    result = DictionaryService(path).lookup("work")

    assert result.senses[0].examples[0].text == "It is difficult work."
    assert result.senses[0].examples[0].source == "Princeton WordNet 3.0"
    assert "work" in result.senses[1].examples[0].text
    assert result.senses[1].examples[0].source == "释义语境（非语料例句）"


def test_version_one_fallback_never_repeats_or_cross_applies_summary_translation(
    tmp_path: Path,
):
    path = tmp_path / "dictionary-v1.json"
    path.write_text(
        json.dumps(
            {
                "schema": "gre-click-dictionary",
                "version": 1,
                "entries": {
                    "subdue": {
                        "word": "subdue",
                        "translation": "vt. 使服从, 压制, 减弱, 抑制, 克制",
                        "definition": (
                            "v put down by force or intimidation\n"
                            "v hold within limits and control"
                        ),
                        "phrases": [],
                    },
                    "record": {
                        "word": "record",
                        "translation": "n. 记录",
                        "definition": "v set down in writing",
                        "phrases": [],
                    },
                    "yourself": {
                        "word": "yourself",
                        "translation": "pron. 你自己",
                        "definition": (
                            "pron. An emphasized or reflexive form of the "
                            "pronoun of the\n   second person; used with you."
                        ),
                        "phrases": [],
                    },
                    "alpha": {
                        "word": "alpha",
                        "translation": "n. 阿尔法",
                        "definition": "",
                        "phrases": [],
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    service = DictionaryService(path)

    subdue = service.lookup("subdue")
    assert subdue.offline_translation == "vt. 使服从, 压制, 减弱, 抑制, 克制"
    assert [sense.translation for sense in subdue.senses] == ["", ""]
    assert [sense.definition for sense in subdue.senses] == [
        "put down by force or intimidation",
        "hold within limits and control",
    ]

    record = service.lookup("record")
    assert len(record.senses) == 1
    assert record.senses[0].part_of_speech == "v."
    assert record.senses[0].translation == ""

    yourself = service.lookup("yourself")
    assert len(yourself.senses) == 1
    assert yourself.senses[0].part_of_speech == "pron."
    assert "second person" in yourself.senses[0].definition

    alpha = service.lookup("alpha")
    assert len(alpha.senses) == 1
    assert alpha.senses[0].translation == "阿尔法"
    assert all(
        sense.examples
        for result in (subdue, record, yourself, alpha)
        for sense in result.senses
    )
