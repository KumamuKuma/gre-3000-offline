from dataclasses import FrozenInstanceError

import pytest

from gre_vocab_app.importer.normalize import WordDraft, normalize_row, split_bilingual
from gre_vocab_app.importer.types import RawWordRow


def test_split_bilingual_uses_first_cjk_character():
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
    assert draft.definition_en == "①phrase. by itself"
    assert draft.definition_zh == "本质上 ②phrase. intrinsically 内在地"
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
