import json
import sqlite3

import pytest

from gre_vocab_app.importer.build import apply_overrides, build_database
from gre_vocab_app.importer.normalize import WordDraft


def draft(word: str, order: int, flags: tuple[str, ...] = ()) -> WordDraft:
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
        quality_flags=flags,
    )


def test_override_marks_reviewed_flags_and_database_keeps_source_order(tmp_path):
    entries = [draft("beta", 2, ("split_token",)), draft("alpha", 1)]
    fixed = apply_overrides(
        entries,
        {"5:beta": {"definition_en": "adj. repaired", "reviewed": True}},
    )

    assert fixed[0].definition_en == "adj. repaired"
    assert fixed[0].quality_flags == ("reviewed:split_token",)

    path = tmp_path / "words.db"
    build_database(fixed, path)
    with sqlite3.connect(path) as db:
        assert db.execute(
            "select headword from words order by source_order"
        ).fetchall() == [("alpha",), ("beta",)]
        assert dict(db.execute("select key, value from metadata")) == {
            "record_count": "2",
            "schema_version": "1",
        }
        assert json.loads(
            db.execute(
                "select quality_flags from words where headword='beta'"
            ).fetchone()[0]
        ) == ["reviewed:split_token"]
        assert db.execute("pragma integrity_check").fetchone()[0] == "ok"


def test_reviewed_override_is_idempotent_and_does_not_mutate_input():
    original = draft("beta", 2, ("reviewed:split_token", "missing_phonetic"))
    fixed = apply_overrides(
        [original], {"5:beta": {"phonetic": "[b]", "reviewed": True}}
    )

    assert original.phonetic == "[x]"
    assert fixed[0].phonetic == "[b]"
    assert fixed[0].quality_flags == (
        "reviewed:split_token",
        "reviewed:missing_phonetic",
    )


@pytest.mark.parametrize(
    "entries, message",
    [
        ([draft("alpha", 1), draft("beta", 1)], "duplicate source_order"),
        ([draft("   ", 1)], "blank headword"),
    ],
)
def test_database_rejects_invalid_records(tmp_path, entries, message):
    with pytest.raises(ValueError, match=message):
        build_database(entries, tmp_path / "words.db")
    assert not (tmp_path / "words.db").exists()


def test_database_replaces_existing_target_atomically(tmp_path):
    path = tmp_path / "words.db"
    path.write_bytes(b"old database")

    build_database([draft("alpha", 1)], path)

    with sqlite3.connect(path) as db:
        assert db.execute("select count(*) from words").fetchone()[0] == 1
    assert not list(tmp_path.glob("*.tmp"))

