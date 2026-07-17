from dataclasses import FrozenInstanceError

import pytest

from gre_vocab_app.importer.normalize import (
    WordDraft,
    normalize_row,
    normalize_row_with_diagnostics,
    split_bilingual,
)
from gre_vocab_app.importer.types import RawWordRow


def test_split_bilingual_separates_one_mixed_language_line():
    assert split_bilingual("adj. sure to happen 必然的") == (
        "adj. sure to happen",
        "必然的",
    )


def test_normalize_row_preserves_cleaned_raw_text():
    row = RawWordRow(
        source_page=144,
        source_order=1400,
        source_section="list16",
        columns=(
            "  halcyon  ",
            "['hælsɪən]",
            " n.  calm, peaceful  \n宁静的，太平的 ",
            "  serene\t tranquil  ",
            " I savor the halcyon times.  \n我享受这段太平时光。 ",
        ),
    )

    draft = normalize_row(row)

    assert draft == WordDraft(
        source_order=1400,
        source_section="list16",
        source_page=144,
        headword="halcyon",
        phonetic="['hælsɪən]",
        definition_en="n. calm, peaceful",
        definition_zh="宁静的，太平的",
        synonyms="serene tranquil",
        example_en="I savor the halcyon times.",
        example_zh="我享受这段太平时光。",
        raw_definition="n. calm, peaceful\n宁静的，太平的",
        raw_example="I savor the halcyon times.\n我享受这段太平时光。",
        quality_flags=(),
    )


def test_word_draft_is_immutable():
    row = RawWordRow(
        source_page=1,
        source_order=1,
        source_section="list1",
        columns=("abate", "[əˈbeɪt]", "v. weaken 减弱", "", ""),
    )
    draft = normalize_row(row)

    with pytest.raises(FrozenInstanceError):
        draft.headword = "changed"


def test_numbered_phrase_sense_is_kept_and_missing_translation_is_flagged():
    row = RawWordRow(
        source_page=288,
        source_order=3001,
        source_section="supplement-2",
        columns=(
            "per se",
            "[ˌpɜːr ˈseɪ]",
            "①phrase. by itself 本质上\n②phrase. intrinsically 内在地",
            "",
            "It is not wrong per se.",
        ),
    )

    draft = normalize_row(row)

    assert draft.headword == "per se"
    assert draft.synonyms == ""
    assert draft.phonetic == "[ˌpɜːr ˈseɪ]"
    assert draft.definition_en == "①phrase. by itself ②phrase. intrinsically"
    assert draft.definition_zh == "本质上内在地"
    assert draft.raw_definition == (
        "①phrase. by itself 本质上\n②phrase. intrinsically 内在地"
    )
    assert draft.quality_flags == ("incomplete_example",)


def test_phonetic_newline_is_removed_without_adding_space():
    row = RawWordRow(
        source_page=9,
        source_order=42,
        source_section="list1",
        columns=(
            "abate",
            "[ə\nˈbeɪt]",
            "v. to become weaker 减弱",
            "mitigate",
            "The pain began to abate. 疼痛开始减轻。",
        ),
    )

    assert normalize_row(row).phonetic == "[əˈbeɪt]"


def test_normalize_row_merges_deduplicates_and_sorts_quality_flags():
    row = RawWordRow(
        source_page=10,
        source_order=43,
        source_section="list1",
        columns=(" \n", "\t", "English only", "", "Example only"),
        flags=("zeta", "incomplete_definition", "alpha"),
    )

    assert normalize_row(row).quality_flags == (
        "alpha",
        "incomplete_definition",
        "incomplete_example",
        "missing_headword",
        "missing_phonetic",
        "zeta",
    )


def test_definition_aggregates_each_visual_line_by_script():
    row = RawWordRow(
        source_page=5,
        source_order=6,
        source_section="list1",
        columns=(
            "allegory",
            "['aeligori]",
            "(1)n. a symbolic \nrepresentation \u8c61\u5f81\n"
            "(2)n. a story in which the \ncharacters are symbols \u5bd3\u8a00",
            "",
            "An allegory. \u4e00\u4e2a\u5bd3\u8a00\u3002",
        ),
    )

    draft = normalize_row(row)

    assert draft.definition_en == (
        "(1)n. a symbolic representation (2)n. a story in which the "
        "characters are symbols"
    )
    assert draft.definition_zh == "\u8c61\u5f81\u5bd3\u8a00"


def test_numbered_english_sense_after_chinese_on_same_visual_line_stays_english():
    row = RawWordRow(
        source_page=33,
        source_order=335,
        source_section="list4",
        columns=(
            "surrender",
            "[s]",
            "(2)v. give control \u4ea4\n\u51fa (3)v. allow something \n\u653e\u4efb",
            "",
            "They surrender. \u4ed6\u4eec\u6295\u964d\u3002",
        ),
    )

    draft = normalize_row(row)

    assert draft.definition_en == "(2)v. give control (3)v. allow something"
    assert draft.definition_zh == "\u4ea4\u51fa\u653e\u4efb"


def test_dewrap_uses_preserved_boundary_whitespace_and_reports_latin_joins():
    row = RawWordRow(
        source_page=9,
        source_order=59,
        source_section="list1",
        columns=(
            "depressing",
            "[d]",
            "adj. causing someone to \nfeel sad \u4ee4\n\u4eba\u6cae\u4e27\u7684",
            "controvers\nial",
            "It was a pretty depr\nessing summer and a \nway to slow\n down.\n"
            "\u8fd9\u662f\u4e00\u4e2a\u4ee4 \n\u4eba\u6cae\u4e27\u7684\u590f\u5929\u3002",
        ),
    )

    draft, events = normalize_row_with_diagnostics(row)

    assert draft.definition_en == "adj. causing someone to feel sad"
    assert draft.definition_zh == "\u4ee4\u4eba\u6cae\u4e27\u7684"
    assert draft.synonyms == "controversial"
    assert draft.example_en == "It was a pretty depressing summer and a way to slow down."
    assert draft.example_zh == "\u8fd9\u662f\u4e00\u4e2a\u4ee4\u4eba\u6cae\u4e27\u7684\u590f\u5929\u3002"
    assert [(event.field, event.kind) for event in events] == [
        ("definition", "normal_space"),
        ("synonyms", "hard_join"),
        ("example", "hard_join"),
        ("example", "normal_space"),
        ("example", "normal_space"),
    ]


def test_example_switches_once_to_chinese_and_assigns_neutral_lines_forward():
    row = RawWordRow(
        source_page=15,
        source_order=121,
        source_section="list2",
        columns=(
            "embody",
            "[embodi]",
            "v. represent \u8c61\u5f81",
            "",
            "Toyota used to embo\ndy quality.\n40\n"
            "\u5e74\u6765\u4e30\u7530\u6c7d\u8f66\nToyota\n\uff08 \uff09\u4e00\u76f4\u5f88\u6709\u540d\u3002",
        ),
    )

    draft = normalize_row(row)

    assert draft.example_en == "Toyota used to embody quality."
    assert draft.example_zh == "40\u5e74\u6765\u4e30\u7530\u6c7d\u8f66Toyota\uff08 \uff09\u4e00\u76f4\u5f88\u6709\u540d\u3002"


def test_latin_name_wrapped_inside_chinese_block_keeps_its_source_space():
    row = RawWordRow(
        source_page=100,
        source_order=1000,
        source_section="list10",
        columns=(
            "candidate",
            "[c]",
            "n. person \u4eba",
            "",
            "He spoke. \n\u5019\u9009\u4ebaNewt \nGingrich\u53d1\u8a00\u3002",
        ),
    )

    draft, events = normalize_row_with_diagnostics(row)

    assert draft.example_en == "He spoke."
    assert draft.example_zh == "\u5019\u9009\u4ebaNewt Gingrich\u53d1\u8a00\u3002"
    assert [(event.field, event.kind) for event in events] == [
        ("example", "normal_space")
    ]


@pytest.mark.parametrize(
    "phonetic, expected_flag",
    [
        ("", "missing_phonetic"),
        ("ameliorate", "invalid_phonetic"),
        ("not ipa", "invalid_phonetic"),
        ("[ameliorate]", None),
        ("/ameliorate/", None),
    ],
)
def test_phonetic_validation_rejects_empty_equal_and_unbracketed_values(
    phonetic, expected_flag
):
    row = RawWordRow(
        source_page=50,
        source_order=529,
        source_section="list6",
        columns=(
            "ameliorate",
            phonetic,
            "v. make better \u6539\u5584",
            "",
            "It improved. \u60c5\u51b5\u6539\u5584\u4e86\u3002",
        ),
    )

    flags = normalize_row(row).quality_flags

    if expected_flag is None:
        assert "missing_phonetic" not in flags
        assert "invalid_phonetic" not in flags
    else:
        assert expected_flag in flags
