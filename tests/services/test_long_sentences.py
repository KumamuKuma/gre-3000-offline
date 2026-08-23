import json
from pathlib import Path

import pytest

from gre_vocab_app.services.long_sentences import (
    LongSentence,
    LongSentenceNote,
    LongSentenceService,
)


def _write_payload(path: Path, sentences: list[object]) -> None:
    path.write_text(
        json.dumps(
            {
                "schema": "gre-long-sentences",
                "version": 2,
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
                "notes": [
                    {"label": "难度", "text": "GRE"},
                    {"label": "译文", "text": "  这些空格应原样保留。  "},
                ],
            },
            {
                "id": 2,
                "source_number": 71,
                "text": "The next sentence follows.",
                "source_pages": [13],
                "notes": [{"label": "解释", "text": "Second note."}],
            },
        ],
    )
    service = LongSentenceService(data)

    assert service.load() == (
        LongSentence(
            1,
            69,
            "Although it was difficult, we continued.",
            (12,),
            (
                LongSentenceNote("难度", "GRE"),
                LongSentenceNote("译文", "  这些空格应原样保留。  "),
            ),
        ),
        LongSentence(
            2,
            71,
            "The next sentence follows.",
            (13,),
            (LongSentenceNote("解释", "Second note."),),
        ),
    )
    data.unlink()
    assert service.load()[1].source_number == 71


@pytest.mark.parametrize(
    "sentences, message",
    (
        (
            [
                {
                    "id": 2,
                    "text": "Sentence.",
                    "source_pages": [1],
                    "notes": [{"label": "译文", "text": "句子。"}],
                }
            ],
            "ids",
        ),
        (
            [
                {
                    "id": 1,
                    "source_number": 1,
                    "text": " ",
                    "source_pages": [1],
                    "notes": [{"label": "译文", "text": "句子。"}],
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
                    "notes": [{"label": "译文", "text": "句子。"}],
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
        json.dumps({"schema": "something-else", "version": 2, "sentences": []}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unsupported"):
        LongSentenceService(data).load()


@pytest.mark.parametrize(
    "notes, message",
    (
        (None, "no notes"),
        ([], "no notes"),
        ({"label": "译文", "text": "句子。"}, "no notes"),
        ([{"label": "译文"}], "only label and text"),
        (
            [{"label": "译文", "text": "句子。", "extra": "no"}],
            "only label and text",
        ),
        ([{"label": " ", "text": "句子。"}], "no label"),
        ([{"label": "译文", "text": "  "}], "no text"),
        ([{"label": 1, "text": "句子。"}], "no label"),
        ([{"label": "译文", "text": 1}], "no text"),
    ),
)
def test_long_sentence_service_requires_nonempty_strict_notes(
    tmp_path: Path, notes: object, message: str
):
    data = tmp_path / "invalid-notes.json"
    _write_payload(
        data,
        [
            {
                "id": 1,
                "source_number": 1,
                "text": "Sentence.",
                "source_pages": [1],
                "notes": notes,
            }
        ],
    )

    with pytest.raises(ValueError, match=message):
        LongSentenceService(data).load()


def test_long_sentence_service_rejects_version_one_payload(tmp_path: Path):
    data = tmp_path / "old.json"
    data.write_text(
        json.dumps(
            {"schema": "gre-long-sentences", "version": 1, "sentences": []}
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unsupported"):
        LongSentenceService(data).load()
