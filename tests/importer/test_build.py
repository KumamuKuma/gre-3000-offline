import json
import sqlite3
from dataclasses import replace

import fitz
import pytest

from gre_vocab_app.importer import build as build_module
from gre_vocab_app.importer.build import (
    APPROVED_SOURCE_PROFILE,
    ExtractionDiagnostics,
    RecordDewrapEvent,
    apply_overrides,
    apply_overrides_with_audit,
    build_database,
    load_overrides,
    semantic_checks,
    strict_checks_from_facts,
)
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
    incomplete = replace(
        draft("beta", 2),
        definition_zh="",
        quality_flags=("incomplete_definition",),
    )
    entries = [incomplete, draft("alpha", 1)]
    fixed = apply_overrides(
        entries,
        {"5:beta": {"definition_zh": "修复", "reviewed": True}},
    )

    assert fixed[0].definition_zh == "修复"
    assert fixed[0].quality_flags == ("reviewed:incomplete_definition",)

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
        ) == ["reviewed:incomplete_definition"]
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


def test_override_recomputes_flags_and_audits_before_after_and_original_issue():
    original = draft("beta", 2, ("missing_phonetic",))
    original = WordDraft(
        **{
            **{name: getattr(original, name) for name in original.__dataclass_fields__},
            "phonetic": "",
        }
    )

    fixed, details = apply_overrides_with_audit(
        [original], {"5:beta": {"phonetic": "[b]", "reviewed": True}}
    )

    assert fixed[0].quality_flags == ("reviewed:missing_phonetic",)
    assert details[0]["key"] == "5:beta"
    assert details[0]["source_order"] == 2
    assert details[0]["original_issues"] == ["missing_phonetic"]
    assert details[0]["changed_fields"] == ["phonetic"]
    assert details[0]["before"]["phonetic"] == ""
    assert details[0]["after"]["phonetic"] == "[b]"


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_order", 99),
        ("source_page", 99),
        ("source_section", "list2"),
        ("raw_definition", "forged"),
        ("raw_example", "forged"),
        ("quality_flags", []),
    ],
)
def test_override_rejects_provenance_raw_and_quality_flag_fields(field, value):
    with pytest.raises(ValueError, match="forbidden override field"):
        apply_overrides(
            [draft("beta", 2, ("split_token",))],
            {"5:beta": {field: value, "reviewed": True}},
        )


def test_override_requires_every_key_to_match_exactly_one_original_row():
    with pytest.raises(ValueError, match="matched 0 rows"):
        apply_overrides(
            [draft("beta", 2, ("split_token",))],
            {"5:betta": {"reviewed": True}},
        )

    with pytest.raises(ValueError, match="matched 2 rows"):
        apply_overrides(
            [draft("beta", 2, ("split_token",)), draft("beta", 3, ("split_token",))],
            {"5:beta": {"reviewed": True}},
        )


def test_reviewed_override_requires_a_real_original_issue():
    with pytest.raises(ValueError, match="no original issue"):
        apply_overrides([draft("beta", 2)], {"5:beta": {"reviewed": True}})


def test_override_rejects_invalid_post_override_content():
    original = draft("beta", 2, ("missing_phonetic",))

    with pytest.raises(ValueError, match="invalid after override"):
        apply_overrides(
            [original],
            {"5:beta": {"phonetic": "not ipa", "reviewed": True}},
        )


def test_override_rejects_changed_field_outside_original_issue_field_union():
    original = replace(
        draft("beta", 2),
        phonetic="",
        quality_flags=("missing_phonetic",),
    )

    with pytest.raises(ValueError, match="unauthorized changed field: headword"):
        apply_overrides(
            [original],
            {"5:beta": {"headword": "gamma", "reviewed": True}},
        )


def test_unknown_override_issue_is_review_only():
    original = draft("beta", 2, ("split_token",))

    with pytest.raises(ValueError, match="unauthorized changed field: definition_en"):
        apply_overrides(
            [original],
            {
                "5:beta": {
                    "definition_en": "adj. repaired",
                    "reviewed": True,
                }
            },
        )

    reviewed = apply_overrides(
        [original], {"5:beta": {"reviewed": True}}
    )
    assert reviewed[0].quality_flags == ("reviewed:split_token",)


def test_override_loader_rejects_duplicate_json_keys(tmp_path):
    path = tmp_path / "overrides.json"
    path.write_text(
        '{"5:beta":{"reviewed":true},"5:beta":{"reviewed":true}}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate JSON key: 5:beta"):
        load_overrides(path)


def test_hard_wrap_scan_uses_boundary_context_not_an_unrelated_spaced_substring():
    entry = draft("dispel", 581)
    entry = WordDraft(
        **{
            **{name: getattr(entry, name) for name in entry.__dataclass_fields__},
            "example_en": (
                "The President is attempting to dispel the notion that he has "
                "neglected the economy."
            ),
        }
    )
    diagnostics = ExtractionDiagnostics(
        dewrap_counts={},
        dewrap_events=(
            RecordDewrapEvent(
                source_order=581,
                field="example",
                kind="hard_join",
                left="The President is attempting to dispel t",
                right="he notion that he has neglected the ec",
            ),
        ),
    )

    result = semantic_checks([entry], diagnostics)

    assert next(item for item in result if item["name"] == "hard_wrap_residue")[
        "pass"
    ] is True


def test_wrap_scan_checks_latin_names_that_belong_to_the_chinese_example():
    entry = draft("putative", 1167)
    entry = WordDraft(
        **{
            **{name: getattr(entry, name) for name in entry.__dataclass_fields__},
            "example_zh": "\u5019\u9009\u4ebaNewt Gingrich\u53d1\u8a00\u3002",
        }
    )
    diagnostics = ExtractionDiagnostics(
        dewrap_counts={},
        dewrap_events=(
            RecordDewrapEvent(
                source_order=1167,
                field="example",
                kind="normal_space",
                left="\u5019\u9009\u4ebaNewt ",
                right="Gingrich\u53d1\u8a00",
            ),
        ),
    )

    result = semantic_checks([entry], diagnostics)

    assert next(item for item in result if item["name"] == "normal_wrap_overjoin")[
        "pass"
    ] is True


@pytest.mark.parametrize(
    "english_sense",
    [
        "vt. to make something better",
        "vi. to become calm",
        "pron. used to refer to a person",
        "conj. joining two clauses",
        "det. identifying a noun",
        "aux. used with another verb",
        "interj. expressing surprise",
        "unable to change",
        "inflexible",
    ],
)
def test_semantic_scan_detects_full_pos_and_unlabelled_english_senses(
    english_sense,
):
    entry = replace(
        draft("contaminated", 42),
        definition_zh=f"中文释义 {english_sense}",
    )

    result = semantic_checks(
        [entry], ExtractionDiagnostics(dewrap_counts={}, dewrap_events=())
    )

    check = next(
        item
        for item in result
        if item["name"] == "definition_zh_contains_english_sense"
    )
    assert check == {
        "name": "definition_zh_contains_english_sense",
        "pass": False,
        "count": 1,
        "source_orders": [42],
    }


@pytest.mark.parametrize(
    "proper_name",
    ["Toyota", "New York", "DNA", "eBay"],
)
def test_semantic_scan_does_not_treat_proper_names_as_english_senses(
    proper_name,
):
    entry = replace(
        draft("named", 43),
        definition_zh=f"中文专名{proper_name}公司",
    )

    result = semantic_checks(
        [entry], ExtractionDiagnostics(dewrap_counts={}, dewrap_events=())
    )

    check = next(
        item
        for item in result
        if item["name"] == "definition_zh_contains_english_sense"
    )
    assert check["pass"] is True
    assert check["source_orders"] == []


@pytest.mark.parametrize(
    "kind,rendered",
    [
        ("normal_space", "型号Model 3已经发布。"),
        ("hard_join", "型号Model3已经发布。"),
    ],
)
def test_semantic_wrap_scan_covers_mixed_chinese_block_boundaries(
    kind, rendered
):
    entry = replace(draft("model", 44), example_zh=rendered)
    diagnostics = ExtractionDiagnostics(
        dewrap_counts={},
        dewrap_events=(
            RecordDewrapEvent(
                source_order=44,
                field="example",
                kind=kind,
                left="型号Model " if kind == "normal_space" else "型号Model",
                right="3已经发布。",
            ),
        ),
    )

    result = semantic_checks([entry], diagnostics)

    check_name = (
        "normal_wrap_overjoin" if kind == "normal_space" else "hard_wrap_residue"
    )
    assert next(item for item in result if item["name"] == check_name)[
        "pass"
    ] is True


def approved_facts():
    return {
        "source_sha256": APPROVED_SOURCE_PROFILE["sha256"],
        "page_count": 288,
        "physical_coverage": {
            "physical_row_bands": 3292,
            "empty_row_bands": 0,
            "multi_anchor_row_bands": 0,
        },
        "record_count": 3292,
        "continuity": {
            "first_source_order": 1,
            "last_source_order": 3292,
            "missing_source_orders": [],
            "duplicate_source_orders": [],
        },
        "page_range": {"first_source_page": 5, "last_source_page": 288},
        "section_counts": APPROVED_SOURCE_PROFILE["section_counts"],
        "override_use": {"declared": 5, "applied": 5},
        "unresolved_count": 0,
        "dewrap_counts": {
            "definition": {
                "normal_space": 3993,
                "hard_join": 0,
                "hard_join_records": 0,
            },
            "example": {
                "normal_space": 3416,
                "hard_join": 241,
                "hard_join_records": 212,
            },
            "synonyms": {
                "normal_space": 2,
                "hard_join": 255,
                "hard_join_records": 237,
            },
        },
        "semantic_checks": [{"name": "language_contamination", "pass": True}],
    }


@pytest.mark.parametrize(
    "mutate, failing_check",
    [
        (lambda facts: facts.update(source_sha256="0" * 64), "source_sha256"),
        (lambda facts: facts.update(page_count=287), "page_count"),
        (
            lambda facts: facts["physical_coverage"].update(physical_row_bands=3291),
            "physical_row_bands",
        ),
        (lambda facts: facts.update(record_count=3291), "record_count"),
        (
            lambda facts: facts["continuity"].update(missing_source_orders=[42]),
            "source_order_continuity",
        ),
        (
            lambda facts: facts["page_range"].update(last_source_page=287),
            "source_page_range",
        ),
        (
            lambda facts: facts["section_counts"].update(list1=104),
            "section_counts",
        ),
        (
            lambda facts: facts["override_use"].update(applied=4),
            "override_use",
        ),
        (lambda facts: facts.update(unresolved_count=1), "unresolved_records"),
        (
            lambda facts: facts["dewrap_counts"]["example"].update(hard_join=240),
            "dewrap_profile",
        ),
        (
            lambda facts: facts["semantic_checks"][0].update(pass_=False),
            "semantic_scans",
        ),
    ],
)
def test_strict_profile_mutations_fail_the_named_gate(mutate, failing_check):
    facts = approved_facts()
    # Avoid mutating the shared approved section-count mapping.
    facts["section_counts"] = dict(facts["section_counts"])
    mutate(facts)
    if "pass_" in facts["semantic_checks"][0]:
        facts["semantic_checks"][0]["pass"] = facts["semantic_checks"][0].pop(
            "pass_"
        )

    checks = strict_checks_from_facts(facts)

    assert all(check["pass"] for check in checks if check["name"] != failing_check)
    assert next(check for check in checks if check["name"] == failing_check)["pass"] is False


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
