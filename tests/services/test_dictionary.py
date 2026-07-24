from __future__ import annotations

import json
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

    assert result.source == "GRE 3000 已审核词库"
    assert result.translation == sample_word.definition_zh
    assert result.gre_word_id == sample_word.id


def test_common_word_and_exact_phrase_are_available_offline(tmp_path: Path):
    service = DictionaryService(_dictionary(tmp_path / "dictionary.json"))

    word = service.lookup("worked")
    common = service.lookup("work")
    phrase = service.lookup("work out")

    assert not word.found
    assert common.translation == "n. 工作；v. 工作"
    assert common.phrases[0].phrase == "work out"
    assert phrase.translation == "锻炼；解决"
    assert phrase.kind == "phrase"
