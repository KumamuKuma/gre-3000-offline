import os
from pathlib import Path

import pytest

from gre_vocab_app.importer import build as build_module
from gre_vocab_app.importer.build import (
    APPROVED_SOURCE_PROFILE,
    _extract_with_diagnostics,
    apply_overrides_with_audit,
    load_overrides,
    semantic_checks,
)
from gre_vocab_app.importer.reference_sources import load_reference_data


@pytest.fixture(scope="module")
def real_import():
    source = os.environ.get("GRE_SOURCE_PDF")
    if not source:
        pytest.skip("GRE_SOURCE_PDF is not configured")
    entries, page_count, coverage, diagnostics = _extract_with_diagnostics(
        Path(source)
    )
    return (
        {entry.source_order: entry for entry in entries},
        page_count,
        coverage,
        diagnostics,
    )


@pytest.fixture(scope="module")
def reviewed_import(real_import):
    rows, _, _, _ = real_import
    override_path = Path(build_module.__file__).with_name("overrides.json")
    entries, details = apply_overrides_with_audit(
        list(rows.values()), load_overrides(override_path)
    )
    return {entry.source_order: entry for entry in entries}, details


@pytest.fixture(scope="module")
def real_reference_import(reviewed_import):
    equivalence = os.environ.get("GRE_EQUIVALENCE_PDF")
    machine7 = os.environ.get("GRE_MACHINE7_PDF")
    if not equivalence or not machine7:
        pytest.skip("GRE reference PDFs are not configured")
    rows, _details = reviewed_import
    return load_reference_data(
        list(rows.values()),
        equivalence_pdf=Path(equivalence),
        machine7_pdf=Path(machine7),
    )


def test_real_pdf_curated_manifest_is_traceable_and_exhaustive(reviewed_import):
    rows, details = reviewed_import

    assert len(details) == APPROVED_SOURCE_PROFILE["override_count"] == 203
    assert all(detail["kinds"] for detail in details)
    assert all(detail["reason"] for detail in details)
    assert all(detail["evidence"] for detail in details)
    assert all(detail["reviewed"] is True for detail in details)
    assert all(not detail["remaining_original_issues"] for detail in details)
    assert not [
        entry.source_order
        for entry in rows.values()
        if any(
            not flag.startswith("reviewed:")
            for flag in entry.quality_flags
        )
    ]

    kind_counts: dict[str, int] = {}
    for detail in details:
        for kind in detail["kinds"]:
            kind_counts[kind] = kind_counts.get(kind, 0) + 1
    assert kind_counts == {
        "content_completion": 4,
        "definition": 32,
        "example": 129,
        "part_of_speech": 20,
        "phonetic": 32,
    }


def test_real_pdf_high_risk_corrections_have_the_reviewed_final_values(
    reviewed_import,
):
    rows, details = reviewed_import
    corrected_orders = {detail["source_order"] for detail in details}

    assert rows[116].definition_en == "adj. merciless or cruel"
    assert rows[529].phonetic == "[əˈmiːljəreɪt]"
    assert rows[884].phonetic == "[raʊ]"
    assert rows[1009].phonetic == (
        "[v. ɑːˈtɪkjəleɪt; adj. ɑːˈtɪkjələt]"
    )
    assert rows[1808].phonetic == "[maɪˈnjuːt]"
    assert rows[2765].phonetic == "[spɑːk]"
    assert rows[3159].example_en == (
        "He puffed himself up in front of the girls."
    )
    assert rows[3164].definition_en.startswith("n. a short, memorable statement")
    assert rows[3182].definition_en.startswith("phrase. to have great power")
    assert rows[3231].example_en == (
        "He does not seem the least bit tractable."
    )
    assert rows[598].example_en.startswith("The blighted roses")
    assert rows[1172].example_en.startswith("The report revealed a strong bias")
    assert rows[2982].example_en == (
        "Bright cushions accent the dark furniture."
    )
    assert rows[3051].phonetic == "[ˌʃɔːtˈlɪvd]"
    assert rows[10].example_zh == "不要极力向别人宣扬你的工作或观点。"
    assert rows[93].example_zh == "工会领导人已要求政府取消这次涨价。"
    assert rows[837].example_zh.endswith("能不断给人惊喜并使人着迷。")
    assert rows[1323].example_en.endswith("registered for less than $10.")
    assert rows[1524].example_zh.endswith("种种弊病的长篇悲叹。")
    assert rows[2900].example_zh.startswith("与特朗普相比")
    assert rows[3154].example_zh.endswith("在原址建一座办公楼。")
    assert rows[3290].definition_zh.startswith("就其本身而言")

    rejected_fragments = (
        "变节你的工作",
        "感到惊讶和催眠",
        "特别小的组委会",
        "反对祸害，反对网络",
        "相对于普京来说",
        "竖立一座办公大楼在网站上",
        "包纳交集很多",
        "最无法无天的怪家伙",
    )
    assert not [
        (entry.source_order, fragment)
        for entry in rows.values()
        for fragment in rejected_fragments
        if fragment in entry.example_zh
    ]

    # These are valid boundary cases deliberately excluded after adjudication.
    assert {1002, 3246}.isdisjoint(corrected_orders)
    assert "have rebounded" in rows[1002].example_en


def test_real_pdf_named_semantic_regressions(real_import):
    rows, _, _, _ = real_import

    allegory = rows[6]
    assert "(2)n. a story" in allegory.definition_en
    assert allegory.definition_zh == "\u8c61\u5f81\u5bd3\u8a00"

    surrender = rows[335]
    assert "(2)v. to give" in surrender.definition_en
    assert "(3)v. to allow" in surrender.definition_en
    assert "to influence or control you" in surrender.definition_en
    assert surrender.definition_zh == "\u6295\u964d\u4ea4\u51fa\u653e\u4efb"

    assert "depressing summer" in rows[59].example_en
    assert "depr essing" not in rows[59].example_en
    assert rows[59].definition_zh == "\u4ee4\u4eba\u6cae\u4e27\u7684"

    equivalent = rows[532]
    assert "equivalent of" in equivalent.example_en
    assert "government worker" in equivalent.example_en
    assert "equiv alent" not in equivalent.example_en
    assert "governm ent" not in equivalent.example_en
    assert equivalent.definition_zh == "\u76f8\u540c\u7684\uff0c\u7b49\u4ef7\u7684"


def test_real_pdf_wraps_and_example_language_assignment(real_import):
    rows, _, _, _ = real_import

    assert rows[16].synonyms == "preternatural"
    assert "(2)adj. much better" in rows[16].definition_en
    assert rows[31].synonyms == "encyclopedic, comprehensive"
    assert "of the problem" in rows[31].example_en
    assert rows[53].synonyms == "controversial"
    assert "divisive issue" in rows[53].example_en

    embody = rows[121]
    assert "embody Japan's" in embody.example_en
    assert "relations nightmare" in embody.example_en
    assert "Toyota" not in embody.example_en.split("nightmare.", 1)[-1]
    assert "Toyota" in embody.example_zh

    assert rows[8].example_en.endswith("his report is true.")
    assert rows[8].example_zh.startswith("\u4e0d\u7ba1\u4f60\u600e\u4e48\u8bf4,")
    assert rows[17].example_en.endswith("tempestuous months.")
    assert "8 \u4e2a\u6708" in rows[17].example_zh
    assert rows[33].example_en == (
        "For 40 years she has captivated the world with her radiant looks."
    )
    assert rows[33].example_zh.startswith("40\u5e74\u6765")


def test_real_pdf_invalid_source_phonetic_is_flagged_without_invention(real_import):
    rows, _, _, _ = real_import

    ameliorate = rows[529]
    assert ameliorate.phonetic == "ameliorate"
    assert ameliorate.quality_flags == ("invalid_phonetic",)


def test_real_pdf_dewrap_profile_matches_reviewed_geometry(real_import):
    rows, page_count, coverage, diagnostics = real_import

    assert page_count == 288
    assert len(rows) == 3292
    assert coverage.physical_row_bands == 3292
    assert diagnostics.dewrap_counts == {
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
    }


def test_real_pdf_semantic_scans_remain_zero(real_import):
    rows, _, _, diagnostics = real_import

    checks = semantic_checks(list(rows.values()), diagnostics)

    assert {item["name"]: item["count"] for item in checks} == {
        "english_fields_contain_cjk": 0,
        "definition_zh_contains_english_sense": 0,
        "hard_wrap_residue": 0,
        "normal_wrap_overjoin": 0,
    }


def test_real_reference_pdfs_match_reviewed_direct_relationship_profile(
    real_reference_import,
):
    facts = real_reference_import.facts
    equivalence = facts["equivalence"]
    machine7 = facts["machine7"]

    assert len(real_reference_import.equivalence_edges) == 547
    assert len(real_reference_import.machine7_memberships) == 1410
    assert equivalence["row_count"] == 940
    assert equivalence["matched_headword_rows"] == 864
    assert equivalence["matched_equivalent_mentions"] == 931
    assert machine7["unique_headword_count"] == 1450
    assert machine7["matched_count"] == 1410
    assert all(
        edge.left_word_id < edge.right_word_id
        for edge in real_reference_import.equivalence_edges
    )
