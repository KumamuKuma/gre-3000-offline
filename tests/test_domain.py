from dataclasses import FrozenInstanceError

import pytest

from gre_vocab_app.domain import (
    BrowseOrder,
    SessionSnapshot,
    StudyMode,
    WordEntry,
)


def make_word() -> WordEntry:
    return WordEntry(
        id=7,
        source_order=4,
        source_section="list1",
        source_page=5,
        headword="abate",
        phonetic="[əˈbeɪt]",
        definition_en="v. to become weaker",
        definition_zh="减弱",
        synonyms="mitigate",
        example_en="The pain began to abate.",
        example_zh="疼痛开始减轻。",
        raw_definition="v. to become weaker 减弱",
        raw_example="The pain began to abate. 疼痛开始减轻。",
        quality_flags=("reviewed_split",),
    )


def test_word_entry_is_immutable_and_preserves_quality_flags():
    word = make_word()

    assert word.headword == "abate"
    assert word.quality_flags == ("reviewed_split",)
    with pytest.raises(FrozenInstanceError):
        word.headword = "wane"


def test_study_modes_and_source_only_order_are_explicit():
    assert tuple(mode.value for mode in StudyMode) == (
        "reading",
        "brief",
        "recall",
        "quiz",
    )
    assert tuple(order.value for order in BrowseOrder) == ("source",)


def test_session_snapshot_annotation_and_quiz_fields_default_safely():
    snapshot = SessionSnapshot(
        word=make_word(),
        index=0,
        total=1,
        mode=StudyMode.READING,
        order=BrowseOrder.SOURCE,
        answer_visible=False,
        at_start=True,
        at_end=True,
    )

    assert snapshot.star_rating == 0
    assert snapshot.star_filter is None
    assert snapshot.list_key is None
    assert snapshot.root_families == ()
    assert snapshot.lookalikes == ()
    assert snapshot.quiz_choices == ()
    assert snapshot.quiz_correct_index is None
    assert snapshot.quiz_selected_index is None
