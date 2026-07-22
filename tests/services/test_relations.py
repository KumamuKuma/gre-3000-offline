from dataclasses import replace

from gre_vocab_app.services.relations import WordRelationIndex


def test_relation_index_groups_classical_roots_and_all_family_members(sample_word):
    words = (
        replace(sample_word, id=1, source_order=1, headword="credible"),
        replace(sample_word, id=2, source_order=2, headword="incredible"),
        replace(sample_word, id=3, source_order=3, headword="credulity"),
        replace(sample_word, id=4, source_order=4, headword="abate"),
    )
    index = WordRelationIndex(words)
    families = index.root_families(1)
    credit = next(family for family in families if family.root.startswith("cred"))
    assert [word.word_id for word in credit.words] == [2, 3]


def test_relation_index_finds_morphological_family_without_common_root(sample_word):
    words = (
        replace(sample_word, id=1, source_order=1, headword="aberrant"),
        replace(sample_word, id=2, source_order=2, headword="aberration"),
        replace(sample_word, id=3, source_order=3, headword="placid"),
    )
    index = WordRelationIndex(words)
    assert any(
        {word.word_id for word in family.words} == {2}
        for family in index.root_families(1)
    )


def test_relation_index_finds_close_spelling_with_different_meaning(sample_word):
    words = (
        replace(
            sample_word,
            id=1,
            source_order=1,
            headword="causal",
            definition_zh="因果关系的",
        ),
        replace(
            sample_word,
            id=2,
            source_order=2,
            headword="casual",
            definition_zh="随意的",
        ),
        replace(
            sample_word,
            id=3,
            source_order=3,
            headword="cause",
            definition_zh="原因",
        ),
    )
    index = WordRelationIndex(words)
    assert [word.word_id for word in index.lookalikes(1)] == [2]


def test_relation_index_excludes_same_meaning_and_root_family_from_lookalikes(
    sample_word,
):
    words = (
        replace(sample_word, id=1, source_order=1, headword="credible"),
        replace(sample_word, id=2, source_order=2, headword="incredible"),
        replace(sample_word, id=3, source_order=3, headword="credibly"),
    )
    index = WordRelationIndex(words)
    assert index.lookalikes(1) == ()


def test_relation_index_excludes_source_equivalents_and_spelling_variants(
    sample_word,
):
    words = (
        replace(
            sample_word,
            id=1,
            source_order=1,
            headword="mold",
            definition_zh="塑造",
        ),
        replace(
            sample_word,
            id=2,
            source_order=2,
            headword="mould",
            definition_zh="铸造，使成形",
        ),
        replace(
            sample_word,
            id=3,
            source_order=3,
            headword="causal",
            definition_zh="因果关系的",
        ),
        replace(
            sample_word,
            id=4,
            source_order=4,
            headword="casual",
            definition_zh="随意的",
        ),
    )
    index = WordRelationIndex(words, excluded_lookalike_pairs=((3, 4),))
    assert index.lookalikes(1) == ()
    assert index.lookalikes(3) == ()


def test_relation_index_excludes_shared_meaning_phrase_from_lookalikes(sample_word):
    words = (
        replace(
            sample_word,
            id=1,
            source_order=1,
            headword="bloom",
            definition_zh="繁荣，繁盛",
        ),
        replace(
            sample_word,
            id=2,
            source_order=2,
            headword="boom",
            definition_zh="繁荣，兴盛",
        ),
    )
    index = WordRelationIndex(words)
    assert index.lookalikes(1) == ()


def test_relation_index_uses_reviewed_families_and_root_exclusions(sample_word):
    words = (
        replace(sample_word, id=1, source_order=1, headword="resurgent"),
        replace(sample_word, id=2, source_order=2, headword="resurrect"),
        replace(sample_word, id=3, source_order=3, headword="insurrection"),
        replace(sample_word, id=4, source_order=4, headword="rectitude"),
        replace(sample_word, id=5, source_order=5, headword="tactic"),
        replace(sample_word, id=6, source_order=6, headword="tactful"),
        replace(sample_word, id=7, source_order=7, headword="tangible"),
    )
    index = WordRelationIndex(words)

    surg_family = next(
        family
        for family in index.root_families(1)
        if family.root.startswith("surg")
    )
    assert {word.word_id for word in surg_family.words} == {2, 3}
    assert all(
        not family.root.startswith("rect")
        for family in index.root_families(2)
    )
    assert all(
        not family.root.startswith("tact")
        for family in index.root_families(5)
    )
