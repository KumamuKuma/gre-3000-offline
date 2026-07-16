import pytest

from gre_vocab_app.domain import WordEntry


@pytest.fixture
def sample_word() -> WordEntry:
    return WordEntry(
        id=1,
        source_order=1,
        source_section="list1",
        source_page=5,
        headword="inevitable",
        phonetic="[ɪnˈevɪtəbl]",
        definition_en="adj. sure to happen",
        definition_zh="必然的",
        synonyms="unavoidable, preordained, ineluctable",
        example_en="It was inevitable.",
        example_zh="这是不可避免的。",
        raw_definition="adj. sure to happen 必然的",
        raw_example="It was inevitable. 这是不可避免的。",
    )
