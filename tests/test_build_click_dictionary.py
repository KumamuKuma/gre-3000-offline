from __future__ import annotations

import csv
import json

import pytest

from scripts.build_click_dictionary import (
    COW_SOURCE,
    COW_OVERRIDES_SOURCE,
    CONTEXT_EXAMPLE_SOURCE,
    WORDNET_SOURCE,
    WordNetSenseRecord,
    _build_senses,
    _deduplicate_cow_lemmas,
    _cow_translation_index,
    _cow_curated_translation_index,
    _definition_lines,
    _recorded_word_forms,
    _validate_senses,
    build_dictionary,
)


def test_builds_version_two_senses_with_wordnet_and_labelled_fallbacks(
    tmp_path,
):
    words = tmp_path / "words.json"
    words.write_text(
        json.dumps(
            {
                "words": [
                    {
                        "word": "abate",
                        "definition_en": "",
                        "synonyms": "",
                        "example_en": "",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    ecdict = tmp_path / "ecdict.csv"
    with ecdict.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(
            destination,
            fieldnames=(
                "word",
                "phonetic",
                "translation",
                "definition",
                "exchange",
                "frq",
                "bnc",
            ),
        )
        writer.writeheader()
        writer.writerow(
            {
                "word": "abate",
                "phonetic": "əˈbeɪt",
                "translation": "vi. 减弱\n[法] 废除",
                "definition": (
                    "v become less in amount or intensity\n"
                    "v. become less in amount or intensity"
                ),
                "exchange": "d:abated",
                "frq": "100",
                "bnc": "100",
            }
        )
    wordnet = tmp_path / "wordnet"
    wordnet.mkdir()
    (wordnet / "data.verb").write_text(
        "00000001 00 v 01 abate 0 000 | "
        'become less in amount or intensity; "The pain began to abate"; '
        '"The rain let up"\n',
        encoding="utf-8",
    )
    cow = tmp_path / "wn-data-cmn.tab"
    cow.write_text(
        "00000001-v\tcmn:lemma\t减弱\n",
        encoding="utf-8",
    )
    output = tmp_path / "dictionary.json"

    summary = build_dictionary(
        words_path=words,
        ecdict_path=ecdict,
        output_paths=(output,),
        wordnet_path=wordnet,
        cow_path=cow,
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    entry = payload["entries"]["abate"]
    assert payload["version"] == 2
    assert payload["sources"] == [
        {"name": "ECDICT", "role": "词条与词性级中文汇总"},
        {"name": WORDNET_SOURCE, "role": "英文义项与例句"},
        {
            "name": COW_SOURCE,
            "role": "按 WordNet 3.0 synset 精确对应的中文同义词",
        },
    ]
    assert entry["translation"] == "vi. 减弱\n[法] 废除"
    assert entry["definition"] == (
        "v become less in amount or intensity\n"
        "v. become less in amount or intensity"
    )
    assert len(entry["senses"]) == 1
    assert entry["senses"][0]["translation"] == "减弱"
    assert entry["senses"][0]["examples"] == [
        {
            "text": "The pain began to abate",
            "source": WORDNET_SOURCE,
        }
    ]
    assert summary["senses"] == 1
    assert summary["wordnet_examples"] == 1
    assert summary["context_examples"] == 0
    assert summary["cow_translated_senses"] == 1


def test_adds_long_sentence_words_to_click_dictionary_targets(tmp_path):
    words = tmp_path / "words.json"
    words.write_text(
        json.dumps(
            {
                "words": [
                    {
                        "word": "abate",
                        "definition_en": "",
                        "synonyms": "",
                        "example_en": "",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    sentences = tmp_path / "long_sentences.json"
    sentences.write_text(
        json.dumps(
            {
                "schema": "gre-long-sentences",
                "version": 2,
                "count": 1,
                "sentences": [
                    {
                        "id": 1,
                        "source_number": 1,
                        "text": "Arduous work can abate.",
                        "notes": [
                            {
                                "label": "Mnemonic",
                                "text": "Resilient learners persist.",
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    ecdict = tmp_path / "ecdict.csv"
    with ecdict.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(
            destination,
            fieldnames=(
                "word",
                "phonetic",
                "translation",
                "definition",
                "exchange",
                "frq",
                "bnc",
            ),
        )
        writer.writeheader()
        writer.writerows(
            [
                {"word": "abate", "translation": "v. 减弱"},
                {"word": "arduous", "translation": "adj. 艰巨的"},
                {"word": "work", "translation": "n. 工作"},
                {"word": "can", "translation": "aux. 能够"},
                {"word": "mnemonic", "translation": "n. 助记符"},
                {"word": "resilient", "translation": "adj. 坚韧的"},
                {"word": "learners", "translation": "n. 学习者"},
                {"word": "persist", "translation": "v. 坚持"},
            ]
        )
    output = tmp_path / "dictionary.json"

    summary = build_dictionary(
        words_path=words,
        long_sentences_path=sentences,
        ecdict_path=ecdict,
        output_paths=(output,),
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert summary["targets"] == 8
    assert set(payload["entries"]) == {
        "abate",
        "arduous",
        "can",
        "learners",
        "mnemonic",
        "persist",
        "resilient",
        "work",
    }


def test_rejects_inconsistent_long_sentence_data(tmp_path):
    words = tmp_path / "words.json"
    words.write_text(json.dumps({"words": []}), encoding="utf-8")
    sentences = tmp_path / "long_sentences.json"
    sentences.write_text(
        json.dumps(
            {
                "schema": "gre-long-sentences",
                "version": 2,
                "count": 2,
                "sentences": [{"id": 1, "text": "Only one."}],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unsupported long-sentence"):
        build_dictionary(
            words_path=words,
            long_sentences_path=sentences,
            ecdict_path=tmp_path / "unused.csv",
            output_paths=(tmp_path / "dictionary.json",),
        )


def test_does_not_copy_one_pos_summary_onto_many_english_senses():
    senses = _build_senses(
        headword="subdue",
        translation="vt. 使服从, 压制, 减弱, 抑制, 克制",
        definition=(
            "v put down by force or intimidation\n"
            "v hold within limits and control"
        ),
        exchange="d:subdued/i:subduing/p:subdued/3:subdues",
        wordnet_examples={},
    )

    assert [sense["definition"] for sense in senses] == [
        "put down by force or intimidation",
        "hold within limits and control",
    ]
    assert [sense["translation"] for sense in senses] == ["", ""]
    assert all(sense["examples"] for sense in senses)


def test_does_not_claim_even_one_to_one_ecdict_summary_is_a_synset_mapping():
    senses = _build_senses(
        headword="assuming",
        translation="a. 傲慢的, 僭越的, 不逊的",
        definition=(
            "v take to be the case or to be true\n"
            "v take on titles, offices, duties, responsibilities\n"
            "s excessively forward"
        ),
        exchange="0:assume/1:i/i:assuming",
        wordnet_examples={},
    )

    assert [sense["translation"] for sense in senses] == [
        "",
        "",
        "",
    ]
    assert senses[-1]["part_of_speech"] == "adj."
    assert senses[-1]["definition"] == "excessively forward"


def test_never_uses_the_only_translation_across_parts_of_speech():
    senses = _build_senses(
        headword="record",
        translation="n. 记录",
        definition="v set down in writing",
        exchange="",
        wordnet_examples={},
    )

    assert len(senses) == 1
    assert senses[0]["part_of_speech"] == "v."
    assert senses[0]["translation"] == ""
    assert senses[0]["definition"] == "set down in writing"


def test_keeps_translation_only_entries_usable_and_labelled():
    senses = _build_senses(
        headword="alpha",
        translation="n. 阿尔法",
        definition="",
        exchange="",
        wordnet_examples={},
    )

    assert senses == [
        {
            "part_of_speech": "n.",
            "translation": "阿尔法",
            "definition": "",
            "examples": [
                {
                    "text": (
                        'The word "alpha" is used here with the meaning '
                        "shown above."
                    ),
                    "source": CONTEXT_EXAMPLE_SOURCE,
                }
            ],
        }
    ]


def test_merges_wrapped_definition_continuations_instead_of_making_fake_senses():
    assert _definition_lines(
        "pron. An emphasized or reflexive form of the pronoun of the\n"
        "   second person; -- used as a subject commonly with you;\n"
        "   also, alone in the predicate."
    ) == (
        (
            "pron.",
            "An emphasized or reflexive form of the pronoun of the second "
            "person; -- used as a subject commonly with you; also, alone in "
            "the predicate.",
        ),
    )


def test_unindented_non_pos_line_starts_a_conservative_separate_sense():
    assert _definition_lines(
        "v first independent definition\n"
        "plain independent definition"
    ) == (
        ("v.", "first independent definition"),
        ("", "plain independent definition"),
    )


def test_uppercase_article_is_not_an_unpunctuated_adjective_code():
    assert _definition_lines(
        "A colloquial contraction for can not.\n"
        "a capable of being believed"
    ) == (
        ("", "A colloquial contraction for can not."),
        ("adj.", "capable of being believed"),
    )


def test_build_preserves_ecdict_indent_for_to_shall_and_yourself(tmp_path):
    words = tmp_path / "words.json"
    words.write_text(
        json.dumps(
            {
                "words": [
                    {
                        "word": word,
                        "definition_en": "",
                        "synonyms": "",
                        "example_en": "",
                    }
                    for word in ("to", "shall", "yourself")
                ]
            }
        ),
        encoding="utf-8",
    )
    ecdict = tmp_path / "ecdict.csv"
    with ecdict.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(
            destination,
            fieldnames=(
                "word",
                "phonetic",
                "translation",
                "definition",
                "exchange",
                "frq",
                "bnc",
            ),
        )
        writer.writeheader()
        writer.writerows(
            [
                {
                    "word": "to",
                    "translation": "prep. 到, 向\nadv. 向前",
                    "definition": (
                        "prep. Accord; adaptation; as, an occupation to his "
                        "taste; she has\n   a husband to her mind.\n"
                        "prep. Comparison; as, three is to nine."
                    ),
                },
                {
                    "word": "shall",
                    "translation": "aux. 将",
                    "definition": (
                        "v. A foretelling or an expectation may include\n"
                        "   a certain degree of plan or intention."
                    ),
                },
                {
                    "word": "yourself",
                    "translation": "pron. 你自己",
                    "definition": (
                        "pron. An emphasized or reflexive form of the pronoun "
                        "of the\n   second person; used with you."
                    ),
                },
            ]
        )
    output = tmp_path / "dictionary.json"

    build_dictionary(
        words_path=words,
        ecdict_path=ecdict,
        output_paths=(output,),
    )
    entries = json.loads(output.read_text(encoding="utf-8"))["entries"]

    assert "\n   a husband to her mind." in entries["to"]["definition"]
    assert [sense["part_of_speech"] for sense in entries["to"]["senses"]] == [
        "prep.",
        "prep.",
    ]
    assert "a husband to her mind" in entries["to"]["senses"][0]["definition"]
    assert len(entries["shall"]["senses"]) == 1
    assert "a certain degree" in entries["shall"]["senses"][0]["definition"]
    assert len(entries["yourself"]["senses"]) == 1
    assert entries["yourself"]["senses"][0]["part_of_speech"] == "pron."


def test_reads_cow_synset_rows_and_deduplicates_chinese_lemmas(tmp_path):
    cow = tmp_path / "wn-data-cmn.tab"
    cow.write_text(
        "# Chinese Open Wordnet\n"
        "00462092-v\tcmn:lemma\t征服\n"
        "00462092-v\tcmn:lemma\t抑制\n"
        "00462092-v\tcmn:lemma\t征服\n"
        "00462092-v\tcmn:lemma\t审美+的\n"
        "00462092-v\teng:lemma\tconquer\n"
        "bad-row\tcmn:lemma\t忽略\n",
        encoding="utf-8",
    )

    assert _cow_translation_index(cow) == {
        "00462092-v": ("征服", "抑制", "审美的"),
    }


def test_cow_dedup_keeps_compound_lemma_without_splitting_names():
    assert _deduplicate_cow_lemmas(
        ["使集中", "集中", "集中，聚集", "奥斯汀，简", "奥斯汀，简"]
    ) == ("使集中", "集中，聚集", "奥斯汀，简")


def test_exchange_inflection_code_is_not_treated_as_a_recorded_word_form():
    assert _recorded_word_forms(
        "assuming",
        "0:assume/1:i/i:assuming",
    ) == ("assuming", "assume")


def test_reads_traceable_cow_curated_translation_replacements(tmp_path):
    overrides = tmp_path / "curated.json"
    overrides.write_text(
        json.dumps(
            {
                "schema": "gre-cow-curated-translations",
                "version": 1,
                "overrides": {
                    "03188725-n": {
                        "translations": ["菱形花纹布", "菱形花纹布"],
                        "reason": "WordNet 定义指织物。",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    assert _cow_curated_translation_index(overrides) == {
        "03188725-n": ("菱形花纹布",),
    }


def test_binds_cow_translation_by_exact_synset_and_keeps_wordnet_example():
    wordnet_senses = {
        (
            "abandon",
            "v.",
            "forsake, leave behind",
        ): (
            WordNetSenseRecord(
                "02228031-v",
                ("We abandoned the old car in the empty parking lot",),
            ),
        ),
        (
            "abandon",
            "v.",
            "give up with the intent of never claiming again",
        ): (
            WordNetSenseRecord(
                "02227741-v",
                ("Abandon your life to God",),
            ),
        ),
    }
    senses = _build_senses(
        headword="abandon",
        translation="vt. 放弃, 抛弃\nn. 放任",
        definition=(
            "v. forsake, leave behind\n"
            "v. give up with the intent of never claiming again"
        ),
        exchange="d:abandoned",
        wordnet_senses=wordnet_senses,
        cow_translations={
            "02228031-v": ("遗弃",),
            "02227741-v": ("放弃",),
        },
    )

    assert [sense["translation"] for sense in senses] == ["遗弃", "放弃"]
    assert [sense["definition"] for sense in senses] == [
        "forsake, leave behind",
        "give up with the intent of never claiming again",
    ]
    assert senses[0]["examples"] == [
        {
            "text": "We abandoned the old car in the empty parking lot",
            "source": WORDNET_SOURCE,
        }
    ]
    assert all(sense["translation"] != "放任" for sense in senses)


def test_cow_satellite_adjective_and_unmapped_sense_are_honest():
    wordnet_senses = {
        (
            "aesthetic",
            "adj.",
            "aesthetically pleasing",
        ): (
            WordNetSenseRecord(
                "02393086-a",
                ("The design is aesthetic",),
            ),
        ),
        (
            "aesthetic",
            "adj.",
            "relating to or dealing with the subject of aesthetics",
        ): (
            WordNetSenseRecord("02991287-a", ()),
        ),
    }
    senses = _build_senses(
        headword="aesthetic",
        translation="a. 美学的, 审美的, 有美感的",
        definition=(
            "a. relating to or dealing with the subject of aesthetics\n"
            "s. aesthetically pleasing"
        ),
        exchange="",
        wordnet_senses=wordnet_senses,
        cow_translations={"02393086-a": ("审美愉悦的",)},
    )

    assert [sense["translation"] for sense in senses] == ["", "审美愉悦的"]
    assert senses[0]["examples"][0]["source"] == CONTEXT_EXAMPLE_SOURCE
    assert senses[1]["examples"][0]["source"] == WORDNET_SOURCE


def test_aback_gets_distinct_synset_translations_and_examples():
    wordnet_senses = {
        (
            "aback",
            "adv.",
            "having the wind against the forward side of the sails",
        ): (
            WordNetSenseRecord(
                "00075739-r",
                ("The ship came up into the wind with all yards aback",),
            ),
        ),
        ("aback", "adv.", "by surprise"): (
            WordNetSenseRecord(
                "00075656-r",
                ("They were taken aback by the caustic remarks",),
            ),
        ),
    }
    senses = _build_senses(
        headword="aback",
        translation="adv. 向后, 朝后, 突然, 船顶风地",
        definition=(
            "r. having the wind against the forward side of the sails\n"
            "r. by surprise"
        ),
        exchange="",
        wordnet_senses=wordnet_senses,
        cow_translations={
            "00075739-r": ("顶风地",),
            "00075656-r": ("出乎意料地",),
        },
    )

    assert [sense["translation"] for sense in senses] == [
        "顶风地",
        "出乎意料地",
    ]
    assert all(
        sense["examples"][0]["source"] == WORDNET_SOURCE
        for sense in senses
    )


def test_yourself_wrapped_definition_stays_one_unmapped_sense_with_fallback():
    senses = _build_senses(
        headword="yourself",
        translation="pron. 你自己",
        definition=(
            "pron. An emphasized or reflexive form of the pronoun of the\n"
            "   second person; -- used as a subject commonly with you;\n"
            "   also, alone in the predicate."
        ),
        exchange="",
        wordnet_senses={},
        cow_translations={},
    )

    assert len(senses) == 1
    assert senses[0]["part_of_speech"] == "pron."
    assert senses[0]["translation"] == ""
    assert "second person" in senses[0]["definition"]
    assert senses[0]["examples"][0]["source"] == CONTEXT_EXAMPLE_SOURCE


def test_rejects_any_dictionary_sense_without_an_example():
    with pytest.raises(ValueError, match="has no example"):
        _validate_senses(
            {
                "abate": {
                    "senses": [
                        {
                            "part_of_speech": "v.",
                            "translation": "减弱",
                            "definition": "become less",
                            "examples": [],
                        }
                    ]
                }
            }
        )


def test_rejects_duplicate_senses_after_build_normalization():
    duplicate = {
        "part_of_speech": "v.",
        "translation": "减弱",
        "definition": "become less",
        "examples": [
            {
                "text": 'In this context, "abate" means become less.',
                "source": CONTEXT_EXAMPLE_SOURCE,
            }
        ],
    }
    with pytest.raises(ValueError, match="duplicate sense"):
        _validate_senses(
            {
                "abate": {
                    "senses": [duplicate, dict(duplicate)],
                }
            }
        )
