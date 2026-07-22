from __future__ import annotations

from pathlib import Path

import fitz

from gre_vocab_app.importer.normalize import WordDraft
from gre_vocab_app.importer.reference_sources import (
    load_reference_data,
    parse_equivalence_pdf,
    parse_machine7_pdf,
)


def _draft(headword: str, order: int) -> WordDraft:
    return WordDraft(
        source_order=order,
        source_section="list1",
        source_page=5,
        headword=headword,
        phonetic="[x]",
        definition_en="adj. sample",
        definition_zh=f"{headword} 的释义",
        synonyms="",
        example_en="",
        example_zh="",
        raw_definition="",
        raw_example="",
        quality_flags=(),
    )


def _five_page_document(path: Path) -> tuple[fitz.Document, fitz.Page]:
    document = fitz.open()
    for _ in range(5):
        page = document.new_page()
    return document, page


def _equivalence_pdf(path: Path) -> None:
    document, page = _five_page_document(path)
    page.insert_text((110, 100), "mitigate", fontname="hebo", fontsize=11.05)
    page.insert_text((220, 100), "abate, temper,", fontname="helv", fontsize=11.05)
    page.insert_text((250, 115), "ameliorate", fontname="helv", fontsize=11.05)
    page.insert_text((115, 140), "sound", fontname="hebo", fontsize=11.05)
    page.insert_text((245, 140), "airtight, valid", fontname="helv", fontsize=11.05)
    document.save(path)
    document.close()


def _machine7_pdf(path: Path) -> None:
    document, page = _five_page_document(path)
    page.insert_text((18.7, 90), "noisome", fontname="hebo", fontsize=9.945)
    page.insert_text((18.7, 150), "self-", fontname="hebo", fontsize=9.945)
    page.insert_text((18.7, 163), "aggrandizing", fontname="hebo", fontsize=9.945)
    page.insert_text((18.7, 220), "adhoc", fontname="hebo", fontsize=9.945)
    document.save(path)
    document.close()


def test_reference_pdf_parsers_follow_reviewed_columns_and_wrapped_rows(tmp_path):
    equivalence = tmp_path / "equivalence.pdf"
    machine7 = tmp_path / "machine7.pdf"
    _equivalence_pdf(equivalence)
    _machine7_pdf(machine7)

    rows, page_count = parse_equivalence_pdf(equivalence)
    machine_rows, machine_page_count = parse_machine7_pdf(machine7)

    assert page_count == 5
    assert rows[0].headword == "mitigate"
    assert rows[0].equivalents == ("abate", "temper", "ameliorate")
    assert rows[1].equivalents == ("airtight", "valid")
    assert machine_page_count == 5
    assert [row.headword for row in machine_rows] == [
        "noisome",
        "self-aggrandizing",
        "adhoc",
    ]


def test_reference_matching_is_conservative_bidirectional_and_not_transitive(tmp_path):
    equivalence = tmp_path / "equivalence.pdf"
    machine7 = tmp_path / "machine7.pdf"
    _equivalence_pdf(equivalence)
    _machine7_pdf(machine7)
    entries = tuple(
        _draft(headword, order)
        for order, headword in enumerate(
            (
                "mitigate",
                "abate",
                "temper",
                "ameliorate",
                "sound",
                "airtight",
                "valid",
                "noisome",
                "self-aggrandizing",
                "ad hoc",
            ),
            start=1,
        )
    )

    data = load_reference_data(
        entries,
        equivalence_pdf=equivalence,
        machine7_pdf=machine7,
    )

    pairs = {
        (edge.left_word_id, edge.right_word_id)
        for edge in data.equivalence_edges
    }
    assert pairs == {(1, 2), (1, 3), (1, 4), (5, 6), (5, 7)}
    assert (2, 3) not in pairs
    assert [item.word_id for item in data.machine7_memberships] == [8, 9, 10]
    assert data.facts["equivalence"]["edge_count"] == 5
    assert data.facts["machine7"]["matched_count"] == 3
