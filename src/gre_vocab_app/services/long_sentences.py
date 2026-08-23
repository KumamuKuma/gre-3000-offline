from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from gre_vocab_app.paths import PACKAGE_ROOT


@dataclass(frozen=True, slots=True)
class LongSentence:
    """One reviewed sentence from the source book."""

    id: int
    source_number: int
    text: str
    source_pages: tuple[int, ...]


class LongSentenceService:
    """Load and validate the bundled long-sentence reading material."""

    def __init__(self, data_path: Path | None = None):
        self._path = data_path or self.default_path()
        self._sentences: tuple[LongSentence, ...] | None = None

    @staticmethod
    def default_path() -> Path:
        packaged = PACKAGE_ROOT / "data" / "long_sentences.json"
        if packaged.exists():
            return packaged
        return PACKAGE_ROOT.parents[1] / "resources" / "long_sentences.json"

    def load(self) -> tuple[LongSentence, ...]:
        if self._sentences is None:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
            self._sentences = self._parse(payload)
        return self._sentences

    @staticmethod
    def _parse(payload: object) -> tuple[LongSentence, ...]:
        if not isinstance(payload, dict):
            raise ValueError("long sentence data must be a JSON object")
        if (
            payload.get("schema") != "gre-long-sentences"
            or payload.get("version") != 1
        ):
            raise ValueError("unsupported long sentence data format")
        records = payload.get("sentences")
        if not isinstance(records, list):
            raise ValueError("long sentence data is missing sentences")

        sentences: list[LongSentence] = []
        source_numbers: set[int] = set()
        for index, record in enumerate(records, start=1):
            if not isinstance(record, dict):
                raise ValueError(f"sentence {index} must be an object")
            sentence_id = record.get("id")
            source_number = record.get("source_number", sentence_id)
            text = record.get("text")
            source_pages = record.get("source_pages")
            if type(sentence_id) is not int or sentence_id != index:
                raise ValueError("sentence ids must be consecutive from 1")
            if type(source_number) is not int or source_number <= 0:
                raise ValueError(f"sentence {index} has an invalid source number")
            if source_number in source_numbers:
                raise ValueError("sentence source numbers must be unique")
            if not isinstance(text, str) or not text.strip():
                raise ValueError(f"sentence {index} has no text")
            if not isinstance(source_pages, list) or not source_pages:
                raise ValueError(f"sentence {index} has no source pages")
            if any(type(page) is not int or page <= 0 for page in source_pages):
                raise ValueError(f"sentence {index} has invalid source pages")

            normalized_text = " ".join(text.split())
            normalized_pages = tuple(dict.fromkeys(source_pages))
            sentences.append(
                LongSentence(
                    id=sentence_id,
                    source_number=source_number,
                    text=normalized_text,
                    source_pages=normalized_pages,
                )
            )
            source_numbers.add(source_number)
        return tuple(sentences)
