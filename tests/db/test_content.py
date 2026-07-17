import sqlite3
import os
from pathlib import Path

import pytest

import gre_vocab_app.db.content as content_module
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


def relax_words_constraints(path: Path) -> None:
    with sqlite3.connect(path) as database:
        database.executescript(
            """
            alter table words rename to words_valid;
            create table words(
              id integer primary key,
              source_order integer,
              source_section text,
              source_page integer,
              headword text,
              phonetic text,
              definition_en text,
              definition_zh text,
              synonyms text,
              example_en text,
              example_zh text,
              raw_definition text,
              raw_example text,
              quality_flags text
            );
            insert into words select * from words_valid;
            drop table words_valid;
            """
        )


def remove_words_id_primary_key(path: Path) -> None:
    with sqlite3.connect(path) as database:
        database.executescript(
            """
            alter table words rename to words_valid;
            create table words(
              id integer,
              source_order integer not null unique,
              source_section text not null,
              source_page integer not null,
              headword text not null,
              phonetic text not null,
              definition_en text not null,
              definition_zh text not null,
              synonyms text not null,
              example_en text not null,
              example_zh text not null,
              raw_definition text not null,
              raw_example text not null,
              quality_flags text not null
            );
            insert into words select * from words_valid;
            drop table words_valid;
            """
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
    with pytest.raises(ValueError, match="版本|version"):
        ContentRepository(content_path)


def test_content_repository_rejects_missing_required_columns_at_open(content_path):
    with sqlite3.connect(content_path) as database:
        database.execute("alter table words drop column quality_flags")

    error_type = getattr(content_module, "ContentDatabaseError", RuntimeError)
    with pytest.raises(error_type, match="quality_flags|列|结构"):
        ContentRepository(content_path)


def test_content_repository_rejects_metadata_record_count_mismatch(content_path):
    with sqlite3.connect(content_path) as database:
        database.execute(
            "update metadata set value='999' where key='record_count'"
        )

    error_type = getattr(content_module, "ContentDatabaseError", RuntimeError)
    with pytest.raises(error_type, match="record_count|记录数"):
        ContentRepository(content_path)


def test_content_repository_rejects_non_continuous_source_order(content_path):
    with sqlite3.connect(content_path) as database:
        database.execute("update words set source_order=4 where source_order=3")

    error_type = getattr(content_module, "ContentDatabaseError", RuntimeError)
    with pytest.raises(error_type, match="source_order|顺序"):
        ContentRepository(content_path)


@pytest.mark.parametrize("invalid_id", (0, -1, 1))
def test_content_repository_rejects_nonpositive_or_duplicate_entry_ids_before_indexing(
    content_path, invalid_id
):
    remove_words_id_primary_key(content_path)
    with sqlite3.connect(content_path) as database:
        database.execute(
            "update words set id=? where source_order=2", (invalid_id,)
        )

    with pytest.raises(content_module.ContentDatabaseError, match="id"):
        ContentRepository(content_path)


@pytest.mark.parametrize("payload", ("not-json", "{}", '["ok", 7]'))
def test_content_repository_rejects_invalid_quality_flags_json(
    content_path, payload
):
    with sqlite3.connect(content_path) as database:
        database.execute(
            "update words set quality_flags=? where source_order=2", (payload,)
        )

    error_type = getattr(content_module, "ContentDatabaseError", RuntimeError)
    with pytest.raises(error_type, match="quality_flags|JSON"):
        ContentRepository(content_path)


def test_content_repository_closes_connection_after_contract_failure(
    content_path, monkeypatch
):
    with sqlite3.connect(content_path) as database:
        database.execute(
            "update metadata set value='999' where key='record_count'"
        )

    connections = []
    real_connect = content_module.sqlite3.connect

    def capture_connect(*args, **kwargs):
        connection = real_connect(*args, **kwargs)
        connections.append(connection)
        return connection

    monkeypatch.setattr(content_module.sqlite3, "connect", capture_connect)
    error_type = getattr(content_module, "ContentDatabaseError", RuntimeError)
    with pytest.raises(error_type):
        ContentRepository(content_path)

    assert len(connections) == 1
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        connections[0].execute("select 1")


@pytest.mark.parametrize(
    ("column", "value"),
    (
        ("phonetic", None),
        ("source_page", "not-an-integer"),
        ("headword", ""),
    ),
)
def test_content_repository_rejects_invalid_nonfirst_row_and_closes_connection(
    content_path, monkeypatch, column, value
):
    relax_words_constraints(content_path)
    with sqlite3.connect(content_path) as database:
        database.execute(
            f'update words set "{column}"=? where source_order=2',
            (value,),
        )

    connections = []
    real_connect = content_module.sqlite3.connect

    def capture_connect(*args, **kwargs):
        connection = real_connect(*args, **kwargs)
        connections.append(connection)
        return connection

    monkeypatch.setattr(content_module.sqlite3, "connect", capture_connect)
    with pytest.raises(content_module.ContentDatabaseError, match="字段|不能为空"):
        ContentRepository(content_path)

    assert len(connections) == 1
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        connections[0].execute("select 1")


def test_unicode_search_normalizes_case_composition_and_literal_wildcards(tmp_path):
    path = tmp_path / "unicode-words.db"
    words = (
        "naiveté",
        "xnaïveté",
        "cliché",
        "100%pure",
        "under_score",
        r"back\slash",
    )
    build_database(
        [make_draft(word, order) for order, word in enumerate(words, start=1)],
        path,
    )

    with ContentRepository(path) as repository:
        assert [word.headword for word in repository.search("NAÏVETÉ")] == [
            "naiveté",
            "xnaïveté",
        ]
        assert [
            word.headword for word in repository.search("CLICHE\N{COMBINING ACUTE ACCENT}")
        ] == ["cliché"]
        assert [word.headword for word in repository.search("%")] == ["100%pure"]
        assert [word.headword for word in repository.search("_")] == [
            "under_score"
        ]
        assert [word.headword for word in repository.search("\\")] == [
            r"back\slash"
        ]
        assert repository.search("\N{COMBINING ACUTE ACCENT}") == []


@pytest.mark.skipif(
    not os.environ.get("GRE_GENERATED_DB"),
    reason="GRE_GENERATED_DB is not configured",
)
def test_real_generated_database_supports_accented_unicode_queries():
    path = Path(os.environ["GRE_GENERATED_DB"])
    with ContentRepository(path) as repository:
        assert repository.count() == 3292
        assert repository.search("NAÏVETÉ")[0].headword == "naiveté"
        assert repository.search("CLICHE\N{COMBINING ACUTE ACCENT}")[0].headword == "cliché"
