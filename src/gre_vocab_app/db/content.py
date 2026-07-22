from __future__ import annotations

import json
import sqlite3
import unicodedata
from pathlib import Path
from typing import Self

from gre_vocab_app.domain import RootFamily, SourceList, RelatedWord, WordEntry
from gre_vocab_app.services.relations import WordRelationIndex

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
            self._build_list_index()
            equivalence_pairs = (
                (word_id, related_id)
                for word_id, related_ids in self._equivalent_ids.items()
                for related_id in related_ids
                if word_id < related_id
            )
            self._relations = WordRelationIndex(
                self._validated_entries,
                excluded_lookalike_pairs=equivalence_pairs,
            )
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
        self._require_columns(
            "equivalence_edges",
            ("left_word_id", "right_word_id", "source_pages"),
        )
        self._require_columns(
            "machine7_membership",
            ("word_id", "source_page", "source_headword"),
        )

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
        entry_ids = tuple(entry.id for entry in self._validated_entries)
        if any(word_id <= 0 for word_id in entry_ids):
            raise ContentDatabaseError(
                "word entry id must be a positive integer"
            )
        if len(set(entry_ids)) != len(entry_ids):
            raise ContentDatabaseError("word entry id values must be unique")
        self._entries_by_id = {
            entry.id: entry for entry in self._validated_entries
        }
        self._load_reference_indexes(metadata)

    def _load_reference_indexes(self, metadata: dict[str, str]) -> None:
        foreign_key_errors = self.db.execute("pragma foreign_key_check").fetchall()
        if foreign_key_errors:
            raise ContentDatabaseError(
                f"词库外键完整性检查失败：{[tuple(row) for row in foreign_key_errors]}"
            )

        try:
            expected_edges = int(metadata["equivalence_edge_count"])
            expected_machine7 = int(metadata["machine7_membership_count"])
        except (KeyError, TypeError, ValueError) as error:
            raise ContentDatabaseError(f"词库参考资料计数无效：{error}") from error
        if expected_edges < 0 or expected_machine7 < 0:
            raise ContentDatabaseError("词库参考资料计数不能为负数")

        edge_rows = self.db.execute(
            "select left_word_id, right_word_id, source_pages "
            "from equivalence_edges order by left_word_id, right_word_id"
        ).fetchall()
        if len(edge_rows) != expected_edges:
            raise ContentDatabaseError(
                "词库 equivalence_edge_count 与实际记录数不一致"
            )
        adjacency: dict[int, list[int]] = {
            word_id: [] for word_id in self._entries_by_id
        }
        for row in edge_rows:
            left, right, raw_pages = row
            if type(left) is not int or type(right) is not int:
                raise ContentDatabaseError("等价词关系 id 必须是整数")
            if not 0 < left < right:
                raise ContentDatabaseError("等价词关系 id 必须为正数且有序")
            if left not in self._entries_by_id or right not in self._entries_by_id:
                raise ContentDatabaseError("等价词关系引用了不存在的词条")
            if not isinstance(raw_pages, str):
                raise ContentDatabaseError("等价词来源页必须是 JSON 文本")
            try:
                pages = json.loads(raw_pages)
            except json.JSONDecodeError as error:
                raise ContentDatabaseError(
                    f"等价词来源页 JSON 无效：{error}"
                ) from error
            if (
                not isinstance(pages, list)
                or not pages
                or any(type(page) is not int or page <= 0 for page in pages)
                or pages != sorted(set(pages))
            ):
                raise ContentDatabaseError("等价词来源页必须是有序正整数数组")
            adjacency[left].append(right)
            adjacency[right].append(left)
        self._equivalent_ids = {
            word_id: tuple(
                sorted(
                    related_ids,
                    key=lambda related_id: self._entries_by_id[
                        related_id
                    ].source_order,
                )
            )
            for word_id, related_ids in adjacency.items()
        }

        machine_rows = self.db.execute(
            "select word_id, source_page, source_headword "
            "from machine7_membership order by word_id"
        ).fetchall()
        if len(machine_rows) != expected_machine7:
            raise ContentDatabaseError(
                "词库 machine7_membership_count 与实际记录数不一致"
            )
        machine7: dict[int, tuple[int, str]] = {}
        for row in machine_rows:
            word_id, page, source_headword = row
            if type(word_id) is not int or word_id not in self._entries_by_id:
                raise ContentDatabaseError("机经 7.0 标记引用了不存在的词条")
            if type(page) is not int or page <= 0:
                raise ContentDatabaseError("机经 7.0 来源页必须是正整数")
            if not isinstance(source_headword, str) or not source_headword.strip():
                raise ContentDatabaseError("机经 7.0 来源词头不能为空")
            machine7[word_id] = (page, source_headword)
        self._machine7 = machine7

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

    @staticmethod
    def _section_label(key: str) -> str:
        if key.startswith("list") and key[4:].isdigit():
            return f"List {int(key[4:])}"
        if key.startswith("supplement-") and key[11:].isdigit():
            return f"补充 List {int(key[11:])}"
        return key

    def _build_list_index(self) -> None:
        grouped: dict[str, list[WordEntry]] = {}
        for entry in self._validated_entries:
            grouped.setdefault(entry.source_section, []).append(entry)
        self._source_lists = tuple(
            SourceList(
                key=key,
                label=self._section_label(key),
                word_count=len(entries),
                first_order=entries[0].source_order,
                last_order=entries[-1].source_order,
            )
            for key, entries in grouped.items()
        )
        self._list_ids = {
            key: tuple(entry.id for entry in entries)
            for key, entries in grouped.items()
        }

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

    def source_lists(self) -> tuple[SourceList, ...]:
        return self._source_lists

    def ids_for_section(self, key: str) -> tuple[int, ...]:
        try:
            return self._list_ids[str(key)]
        except KeyError:
            raise KeyError(key) from None

    def source_list(self, key: str) -> SourceList:
        for source_list in self._source_lists:
            if source_list.key == key:
                return source_list
        raise KeyError(key)

    def root_families(self, word_id: int) -> tuple[RootFamily, ...]:
        self.get(word_id)
        return self._relations.root_families(word_id)

    def lookalikes(self, word_id: int) -> tuple[RelatedWord, ...]:
        self.get(word_id)
        return self._relations.lookalikes(word_id)

    @staticmethod
    def _related_word(entry: WordEntry) -> RelatedWord:
        definition = entry.definition_zh or entry.definition_en
        return RelatedWord(
            word_id=entry.id,
            headword=entry.headword,
            definition=" ".join(definition.split()),
        )

    def equivalents(self, word_id: int) -> tuple[RelatedWord, ...]:
        self.get(word_id)
        return tuple(
            self._related_word(self._entries_by_id[related_id])
            for related_id in self._equivalent_ids.get(int(word_id), ())
        )

    def in_machine7(self, word_id: int) -> bool:
        self.get(word_id)
        return int(word_id) in self._machine7

    def machine7_source(self, word_id: int) -> tuple[int, str] | None:
        self.get(word_id)
        return self._machine7.get(int(word_id))
