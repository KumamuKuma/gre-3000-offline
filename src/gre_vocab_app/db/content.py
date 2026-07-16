from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Self

from gre_vocab_app.domain import WordEntry

from .schema import CONTENT_SCHEMA_VERSION


class ContentRepository:
    def __init__(self, path: Path):
        self.path = path.resolve()
        self.db = sqlite3.connect(f"{self.path.as_uri()}?mode=ro", uri=True)
        self.db.row_factory = sqlite3.Row
        try:
            version = self.db.execute(
                "select value from metadata where key='schema_version'"
            ).fetchone()
            if version is None or int(version[0]) != CONTENT_SCHEMA_VERSION:
                raise ValueError("content database version is incompatible")
        except Exception:
            self.db.close()
            raise

    def close(self) -> None:
        self.db.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    @staticmethod
    def _map(row: sqlite3.Row) -> WordEntry:
        return WordEntry(
            id=int(row["id"]),
            source_order=int(row["source_order"]),
            source_section=str(row["source_section"]),
            source_page=int(row["source_page"]),
            headword=str(row["headword"]),
            phonetic=str(row["phonetic"]),
            definition_en=str(row["definition_en"]),
            definition_zh=str(row["definition_zh"]),
            synonyms=str(row["synonyms"]),
            example_en=str(row["example_en"]),
            example_zh=str(row["example_zh"]),
            raw_definition=str(row["raw_definition"]),
            raw_example=str(row["raw_example"]),
            quality_flags=tuple(json.loads(row["quality_flags"])),
        )

    def count(self) -> int:
        return int(self.db.execute("select count(*) from words").fetchone()[0])

    def get(self, word_id: int) -> WordEntry:
        row = self.db.execute(
            "select * from words where id=?", (word_id,)
        ).fetchone()
        if row is None:
            raise KeyError(word_id)
        return self._map(row)

    def ids_in_source_order(self) -> tuple[int, ...]:
        rows = self.db.execute(
            "select id from words order by source_order"
        ).fetchall()
        return tuple(int(row[0]) for row in rows)

    @staticmethod
    def _like_literal(value: str) -> str:
        return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

    def search(self, query: str, limit: int = 50) -> list[WordEntry]:
        value = query.strip()
        if not value or limit <= 0:
            return []
        escaped = self._like_literal(value)
        prefix_pattern = f"{escaped}%"
        ordering = "order by length(headword), headword collate nocase, source_order"
        prefix = self.db.execute(
            f"select * from words where headword like ? escape '\\' collate nocase {ordering} limit ?",
            (prefix_pattern, limit),
        ).fetchall()
        result = [self._map(row) for row in prefix]
        remaining = limit - len(result)
        if remaining <= 0:
            return result
        contains = self.db.execute(
            f"select * from words "
            f"where headword like ? escape '\\' collate nocase "
            f"and headword not like ? escape '\\' collate nocase "
            f"{ordering} limit ?",
            (f"%{escaped}%", prefix_pattern, remaining),
        ).fetchall()
        result.extend(self._map(row) for row in contains)
        return result

    def list_by_ids(self, ids: tuple[int, ...]) -> list[WordEntry]:
        return [self.get(word_id) for word_id in ids]

