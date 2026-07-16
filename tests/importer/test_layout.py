import os

import fitz
import pytest

from gre_vocab_app.importer.layout import extract_page_spans, group_spans_into_rows
from gre_vocab_app.importer.types import ParserState, TextSpan


def span(x: float, y: float, text: str, size: float = 10) -> TextSpan:
    return TextSpan(x0=x, y0=y, x1=x + 60, y1=y + 11, text=text, size=size)


def test_groups_five_columns_and_updates_mid_page_section():
    spans = [
        span(19, 48, "张巍GRE镇考3000词 乱序版 list1"),
        span(19, 70, "querulous"),
        span(100, 70, "['kwerələs]"),
        span(188, 70, "adj. habitually complaining"),
        span(188, 82, "抱怨的"),
        span(320, 70, "peevish"),
        span(384, 70, "One gets unsettled."),
        span(384, 82, "人会心绪不宁。"),
        span(19, 108, "rote"),
        span(100, 108, "[roʊt]"),
        span(188, 108, "n. mechanical repetition"),
        span(188, 120, "死记硬背"),
    ]

    rows, state = group_spans_into_rows(
        spans,
        page_number=5,
        state=ParserState(next_order=1, section="unknown"),
    )

    assert [row.columns[0] for row in rows] == ["querulous", "rote"]
    assert rows[0].columns == (
        "querulous",
        "['kwerələs]",
        "adj. habitually complaining\n抱怨的",
        "peevish",
        "One gets unsettled.\n人会心绪不宁。",
    )
    assert rows[0].source_page == 5
    assert rows[0].source_section == "list1"
    assert rows[1].source_order == 2
    assert state.next_order == 3


def test_assigns_leading_cell_lines_to_nearest_headword_row():
    spans = [
        span(188, 84, "first definition"),
        span(19, 90, "alpha"),
        span(100, 90, "[alpha]"),
        span(320, 90, "first synonym"),
        span(384, 72, "first example"),
        span(384, 108, "first example detail"),
        span(188, 132, "second definition"),
        span(19, 144, "beta"),
        span(100, 144, "[beta]"),
        span(320, 144, "second synonym"),
        span(384, 131, "second example"),
        span(384, 158, "second example detail"),
    ]

    rows, _ = group_spans_into_rows(
        spans,
        page_number=5,
        state=ParserState(next_order=1, section="list1"),
    )

    assert rows[0].columns[2] == "first definition"
    assert rows[0].columns[4] == "first example\nfirst example detail"
    assert rows[1].columns[2] == "second definition"
    assert rows[1].columns[4] == "second example\nsecond example detail"


def test_updates_section_for_split_mid_page_supplement_header():
    spans = [
        span(19, 70, "alpha"),
        span(100, 70, "[alpha]"),
        span(188, 70, "first definition"),
        span(252, 108, "补充重点单词"),
        span(323, 108, "list1"),
        span(19, 144, "beta"),
        span(100, 144, "[beta]"),
        span(188, 144, "second definition"),
    ]

    rows, state = group_spans_into_rows(
        spans,
        page_number=271,
        state=ParserState(next_order=100, section="list30"),
    )

    assert [row.source_section for row in rows] == ["list30", "supplement-1"]
    assert state.section == "supplement-1"


def test_page_end_section_header_updates_state_without_contaminating_last_row():
    spans = [
        span(19, 70, "alpha"),
        span(100, 70, "[alpha]"),
        span(188, 70, "first definition"),
        span(234, 144, "补充重点单词", size=15),
        span(323, 144, "list2", size=15),
        span(234, 164, "微信公众号：张巍GRE"),
    ]

    rows, state = group_spans_into_rows(
        spans,
        page_number=279,
        state=ParserState(next_order=200, section="supplement-1"),
    )

    assert rows[0].columns[2] == "first definition"
    assert state.section == "supplement-2"


def test_ignores_list_number_in_example_text():
    spans = [
        span(19, 70, "alpha"),
        span(100, 70, "[alpha]"),
        span(188, 70, "first definition"),
        span(384, 70, "List 2 reasons for the decision."),
    ]

    rows, state = group_spans_into_rows(
        spans,
        page_number=5,
        state=ParserState(next_order=1, section="list1"),
    )

    assert rows[0].columns[4] == "List 2 reasons for the decision."
    assert state.section == "list1"


@pytest.mark.parametrize("page_index", [4, 143, 287])
def test_real_pdf_sample_pages_have_five_column_rows(page_index):
    source = os.environ.get("GRE_SOURCE_PDF")
    if not source:
        pytest.skip("GRE_SOURCE_PDF is not configured")

    with fitz.open(source) as document:
        spans = extract_page_spans(document[page_index])
    rows, _ = group_spans_into_rows(
        spans,
        page_number=page_index + 1,
        state=ParserState(next_order=1, section="sample"),
    )

    assert rows
    assert all(len(row.columns) == 5 for row in rows)
    assert all(row.columns[0] for row in rows)
