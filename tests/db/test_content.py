import sqlite3

import pytest

from gre_vocab_app.db.content import ContentRepository
from gre_vocab_app.importer.build import build_database
from gre_vocab_app.importer.normalize import WordDraft


def make_draft(word: str, order: int) -> WordDraft:
    return WordDraft(
        source_order=order,
        source_section="list1",
        source_page=5,
        headword=word,
        phonetic="[x]",
        definition_en="adj. sample",
        definition_zh="示例",
        synonyms="",
        example_en="",
        example_zh="",
        raw_definition="adj. sample 示例",
        raw_example="",
        quality_flags=("reviewed:sample",) if word == "abate" else (),
    )


@pytest.fixture
def content_path(tmp_path):
    path = tmp_path / "words.db"
    build_database(
        [
            make_draft("abate", 1),
            make_draft("unabated", 2),
            make_draft("alphabet", 3),
        ],
        path,
    )
    return path


def test_content_repository_maps_records_and_opens_database_read_only(content_path):
    with ContentRepository(content_path) as repository:
        word = repository.get(1)
        assert word.headword == "abate"
        assert word.quality_flags == ("reviewed:sample",)
        assert repository.count() == 3
        assert repository.ids_in_source_order() == (1, 2, 3)
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            repository.db.execute(
                "update words set headword='changed' where id=1"
            )


def test_content_search_prefers_prefix_then_contains_and_honors_limit(content_path):
    with ContentRepository(content_path) as repository:
        assert [word.headword for word in repository.search("abat", limit=10)] == [
            "abate",
            "unabated",
        ]
        assert [word.headword for word in repository.search("a", limit=2)] == [
            "abate",
            "alphabet",
        ]
        assert repository.search("   ") == []
        assert repository.search("a", limit=0) == []


def test_content_get_and_list_by_ids_preserve_contract(content_path):
    with ContentRepository(content_path) as repository:
        assert [word.headword for word in repository.list_by_ids((3, 1))] == [
            "alphabet",
            "abate",
        ]
        with pytest.raises(KeyError, match="999"):
            repository.get(999)


def test_content_repository_rejects_schema_mismatch(content_path):
    with sqlite3.connect(content_path) as database:
        database.execute(
            "update metadata set value='999' where key='schema_version'"
        )
    with pytest.raises(ValueError, match="version"):
        ContentRepository(content_path)

