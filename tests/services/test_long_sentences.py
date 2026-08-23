import json
from pathlib import Path

import pytest

from gre_vocab_app.services.long_sentences import (
    LongSentence,
    LongSentenceService,
)


def _write_payload(path: Path, sentences: list[object]) -> None:
    path.write_text(
        json.dumps(
            {
                "schema": "gre-long-sentences",
                "version": 1,
                "sentences": sentences,
            }
        ),
        encoding="utf-8",
    )


def test_long_sentence_service_loads_normalizes_and_caches(tmp_path: Path):
    data = tmp_path / "long_sentences.json"
    _write_payload(
        data,
        [
            {
                "id": 1,
                "source_number": 69,
                "text": "  Although   it was difficult, we continued.  ",
                "source_pages": [12, 12],
            },
            {
                "id": 2,
                "source_number": 71,
                "text": "The next sentence follows.",
                "source_pages": [13],
            },
        ],
    )
    service = LongSentenceService(data)

    assert service.load() == (
        LongSentence(1, 69, "Although it was difficult, we continued.", (12,)),
        LongSentence(2, 71, "The next sentence follows.", (13,)),
    )
    data.unlink()
    assert service.load()[1].source_number == 71


@pytest.mark.parametrize(
    "sentences, message",
    (
        ([{"id": 2, "text": "Sentence.", "source_pages": [1]}], "ids"),
        (
            [
                {
                    "id": 1,
                    "source_number": 1,
                    "text": " ",
                    "source_pages": [1],
                }
            ],
            "no text",
        ),
        (
            [
                {
                    "id": 1,
                    "source_number": 1,
                    "text": "Sentence.",
                    "source_pages": [],
                }
            ],
            "no source pages",
        ),
    ),
)
def test_long_sentence_service_rejects_invalid_records(
    tmp_path: Path, sentences: list[object], message: str
):
    data = tmp_path / "invalid.json"
    _write_payload(data, sentences)

    with pytest.raises(ValueError, match=message):
        LongSentenceService(data).load()


def test_long_sentence_service_rejects_unsupported_schema(tmp_path: Path):
    data = tmp_path / "invalid.json"
    data.write_text(
        json.dumps({"schema": "something-else", "version": 1, "sentences": []}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unsupported"):
        LongSentenceService(data).load()
