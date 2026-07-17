from __future__ import annotations

import json
import sqlite3
import unicodedata
from pathlib import Path
from typing import Self

from gre_vocab_app.domain import WordEntry

from .schema import CONTENT_SCHEMA_VERSION


_WORD_COLUMNS = (
    "id",
    "source_order",
    "source_section",
    "source_page",
    "headword",
    "phonetic",
    "definition_en",
    "definition_zh",
    "synonyms",
    "example_en",
    "example_zh",
    "raw_definition",
    "raw_example",
    "quality_flags",
)
_TEXT_COLUMNS = _WORD_COLUMNS[2:3] + _WORD_COLUMNS[4:-1]


class ContentDatabaseError(RuntimeError, ValueError):
    """Raised when the immutable vocabulary database cannot be trusted."""


def normalize_search_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    return unicodedata.normalize("NFKC", normalized.casefold())


def _accent_insensitive_key(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", normalize_search_key(value))
    return unicodedata.normalize(
        "NFKC",
        "".join(
            character
            for character in decomposed
            if not unicodedata.combining(character)
        ),
    )


class ContentRepository:
    def __init__(self, path: Path):
        self.path = path.resolve()
        if not path.is_file():
            raise ContentDatabaseError(f"词库文件缺失：{path}")
        try:
            self.db = sqlite3.connect(f"{self.path.as_uri()}?mode=ro", uri=True)
        except sqlite3.Error as error:
            raise ContentDatabaseError(f"无法只读打开词库：{error}") from error
        self.db.row_factory = sqlite3.Row
        try:
            self._validate_contract()
            self._build_search_index()
        except ContentDatabaseError:
            self.db.close()
            raise
        except (
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
            sqlite3.Error,
        ) as error:
            self.db.close()
            raise ContentDatabaseError(f"词库契约校验失败：{error}") from error

    def _validate_contract(self) -> None:
        try:
            integrity_rows = self.db.execute("pragma integrity_check").fetchall()
        except sqlite3.Error as error:
            raise ContentDatabaseError(f"词库完整性检查失败：{error}") from error
        if [tuple(row) for row in integrity_rows] != [("ok",)]:
            details = "; ".join(str(row[0]) for row in integrity_rows) or "无检查结果"
            raise ContentDatabaseError(f"词库完整性检查失败：{details}")

        self._require_columns("metadata", ("key", "value"))
        self._require_columns("words", _WORD_COLUMNS)

        metadata = {
            str(row[0]): str(row[1])
            for row in self.db.execute("select key, value from metadata")
        }
        try:
            version = int(metadata["schema_version"])
        except (KeyError, TypeError, ValueError) as error:
            raise ContentDatabaseError(f"词库版本不兼容：{error}") from error
        if version != CONTENT_SCHEMA_VERSION:
            raise ContentDatabaseError(
                f"词库版本不兼容：需要 {CONTENT_SCHEMA_VERSION}，实际 {version}"
            )

        try:
            expected_count = int(metadata["record_count"])
        except (KeyError, TypeError, ValueError) as error:
            raise ContentDatabaseError(f"词库 record_count 无效：{error}") from error
        actual_count = int(
            self.db.execute("select count(*) from words").fetchone()[0]
        )
        if expected_count != actual_count:
            raise ContentDatabaseError(
                "词库 record_count 与实际记录数不一致："
                f"metadata={expected_count}, actual={actual_count}"
            )
        if actual_count <= 0:
            raise ContentDatabaseError("词库没有可用词条")

        order_row = self.db.execute(
            "select count(distinct source_order), min(source_order), "
            "max(source_order) from words"
        ).fetchone()
        if tuple(order_row) != (actual_count, 1, actual_count):
            raise ContentDatabaseError(
                "词库 source_order 必须唯一且从 1 连续排列："
                f"actual={tuple(order_row)}, count={actual_count}"
            )

        rows = self.db.execute(
            "select * from words order by source_order"
        ).fetchall()
        self._validated_entries = tuple(self._map(row) for row in rows)
        self._entries_by_id = {
            entry.id: entry for entry in self._validated_entries
        }

    def _require_columns(self, table: str, expected: tuple[str, ...]) -> None:
        rows = self.db.execute(f'pragma table_info("{table}")').fetchall()
        actual = tuple(str(row[1]) for row in rows)
        if actual != expected:
            raise ContentDatabaseError(
                f"词库结构不完整：{table} 列应为 {expected}，实际为 {actual}"
            )

    @staticmethod
    def _quality_flags(value: object, *, word_id: object) -> tuple[str, ...]:
        if not isinstance(value, str):
            raise ContentDatabaseError(
                f"词条 {word_id} 的 quality_flags 不是 JSON 文本"
            )
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError as error:
            raise ContentDatabaseError(
                f"词条 {word_id} 的 quality_flags JSON 无效：{error}"
            ) from error
        if not isinstance(decoded, list) or any(
            not isinstance(flag, str) for flag in decoded
        ):
            raise ContentDatabaseError(
                f"词条 {word_id} 的 quality_flags 必须是字符串 JSON 数组"
            )
        return tuple(decoded)

    def close(self) -> None:
        self.db.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    @classmethod
    def _map(cls, row: sqlite3.Row) -> WordEntry:
        for column in ("id", "source_order", "source_page"):
            if type(row[column]) is not int:
                raise ContentDatabaseError(
                    f"词条字段 {column} 必须是整数，实际为 {type(row[column]).__name__}"
                )
        for column in _TEXT_COLUMNS:
            if not isinstance(row[column], str):
                raise ContentDatabaseError(
                    f"词条字段 {column} 必须是文本，实际为 {type(row[column]).__name__}"
                )
        if not row["headword"].strip():
            raise ContentDatabaseError("词条 headword 不能为空")
        return WordEntry(
            id=row["id"],
            source_order=row["source_order"],
            source_section=row["source_section"],
            source_page=row["source_page"],
            headword=row["headword"],
            phonetic=row["phonetic"],
            definition_en=row["definition_en"],
            definition_zh=row["definition_zh"],
            synonyms=row["synonyms"],
            example_en=row["example_en"],
            example_zh=row["example_zh"],
            raw_definition=row["raw_definition"],
            raw_example=row["raw_example"],
            quality_flags=cls._quality_flags(
                row["quality_flags"], word_id=row["id"]
            ),
        )

    def count(self) -> int:
        return int(self.db.execute("select count(*) from words").fetchone()[0])

    def get(self, word_id: int) -> WordEntry:
        try:
            return self._entries_by_id[int(word_id)]
        except KeyError:
            raise KeyError(word_id) from None

    def ids_in_source_order(self) -> tuple[int, ...]:
        return tuple(entry.id for entry in self._validated_entries)

    def _build_search_index(self) -> None:
        self._search_index = tuple(
            (
                entry,
                entry.headword,
                normalize_search_key(entry.headword),
                _accent_insensitive_key(entry.headword),
                entry.source_order,
            )
            for entry in self._validated_entries
        )

    def search(self, query: str, limit: int = 50) -> list[WordEntry]:
        value = query.strip()
        if not value or limit <= 0:
            return []
        key = normalize_search_key(value)
        accent_key = _accent_insensitive_key(value)
        use_accent_fallback = bool(accent_key)
        prefix: list[tuple[WordEntry, str, str, str, int]] = []
        contains: list[tuple[WordEntry, str, str, str, int]] = []
        for item in self._search_index:
            _word_id, _headword, word_key, word_accent_key, _source_order = item
            is_prefix = word_key.startswith(key) or (
                use_accent_fallback
                and word_accent_key.startswith(accent_key)
            )
            if is_prefix:
                prefix.append(item)
            elif key in word_key or (
                use_accent_fallback and accent_key in word_accent_key
            ):
                contains.append(item)
        ordering = lambda item: (len(item[1]), item[2], item[4])
        matches = sorted(prefix, key=ordering) + sorted(contains, key=ordering)
        return [item[0] for item in matches[:limit]]

    def list_by_ids(self, ids: tuple[int, ...]) -> list[WordEntry]:
        return [self.get(word_id) for word_id in ids]
