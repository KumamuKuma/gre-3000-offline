import os
from pathlib import Path

import pytest

from gre_vocab_app.importer.build import _extract_with_diagnostics


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
