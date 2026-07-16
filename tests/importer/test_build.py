import json
import sqlite3

import fitz
import pytest

from gre_vocab_app.importer import build as build_module
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


def test_import_rejects_a_physical_word_row_without_a_headword(tmp_path, capsys):
    source = tmp_path / "missing-headword.pdf"
    with fitz.open() as document:
        for _ in range(6):
            document.new_page(width=595.44, height=841.68)
        page = document[4]
        for y in (11.16, 40.16, 101.16):
            page.draw_rect(
                fitz.Rect(17.16, y, 569.52, y + 0.36),
                color=None,
                fill=(0, 0, 0),
            )
        for x in (17.16, 98.16, 186.16, 323.16, 382.16, 569.16):
            page.draw_rect(
                fitz.Rect(x, 11.16, x + 0.36, 101.52),
                color=None,
                fill=(0, 0, 0),
            )
        page.insert_text((188.0, 70.0), "definition without a headword")
        document.save(source)
    overrides = tmp_path / "overrides.json"
    overrides.write_text("{}", encoding="utf-8")

    exit_code = build_module.main(
        [
            "--pdf",
            str(source),
            "--output",
            str(tmp_path / "words.db"),
            "--audit-json",
            str(tmp_path / "audit.json"),
            "--audit-html",
            str(tmp_path / "audit.html"),
            "--overrides",
            str(overrides),
            "--strict",
        ]
    )

    assert exit_code == 1
    assert "empty_row_bands=1" in capsys.readouterr().err
    assert not (tmp_path / "words.db").exists()
