from dataclasses import FrozenInstanceError

import pytest

from gre_vocab_app.domain import BrowseOrder, StudyMode, WordEntry


def test_word_entry_is_immutable_and_preserves_quality_flags():
    word = WordEntry(
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

    assert word.headword == "abate"
    assert word.quality_flags == ("reviewed_split",)
    assert StudyMode.READING.value == "reading"
    assert BrowseOrder.RANDOM.value == "random"
    with pytest.raises(FrozenInstanceError):
        word.headword = "wane"
