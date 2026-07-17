import os

import fitz
import pytest

from gre_vocab_app.importer import layout as layout_module
from gre_vocab_app.importer.layout import extract_page_spans, group_spans_into_rows
from gre_vocab_app.importer.types import ParserState, TextSpan


def span(x: float, y: float, text: str, size: float = 10) -> TextSpan:
    return TextSpan(x0=x, y0=y, x1=x + 60, y1=y + 11, text=text, size=size)


def test_extract_page_spans_preserves_boundary_whitespace():
    class FakePage:
        def get_text(self, kind):
            assert kind == "dict"
            return {
                "blocks": [
                    {
                        "lines": [
                            {
                                "spans": [
                                    {
                                        "bbox": (10, 20, 30, 40),
                                        "text": " word ",
                                        "size": 10,
                                    },
                                    {
                                        "bbox": (30, 20, 40, 40),
                                        "text": "   ",
                                        "size": 10,
                                    },
                                ]
                            }
                        ]
                    }
                ]
            }

    spans = extract_page_spans(FakePage())

    assert [item.text for item in spans] == [" word "]


def test_visual_lines_cluster_by_center_and_keep_same_line_span_boundaries():
    spans = [
        TextSpan(19, 70, 70, 87, "alpha", 10),
        TextSpan(100, 70, 150, 87, "[a]", 10),
        TextSpan(188, 70, 250, 87, "adj. sure ", 10),
        TextSpan(250, 72.5, 290, 84.5, "\u5fc5\u7136\u7684", 10),
    ]

    rows, _ = group_spans_into_rows(
        spans,
        page_number=5,
        state=ParserState(next_order=1, section="list1"),
    )

    assert rows[0].columns[2] == "adj. sure \u5fc5\u7136\u7684"


def test_visual_line_clustering_does_not_chain_beyond_fixed_tolerance():
    spans = [
        TextSpan(19, 70, 70, 81, "alpha", 10),
        TextSpan(100, 70, 150, 81, "[a]", 10),
        TextSpan(188, 70, 235, 81, "one ", 10),
        TextSpan(240, 74, 295, 85, "two ", 10),
        TextSpan(300, 76, 350, 87, "three", 10),
    ]

    rows, _ = group_spans_into_rows(
        spans,
        page_number=5,
        state=ParserState(next_order=1, section="list1"),
    )

    assert rows[0].columns[2] == "one two \nthree"


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


def test_merges_overlapping_wrapped_headword_spans_without_merging_next_word():
    spans = [
        TextSpan(19, 70, 92, 87, "anthropocentri", 10),
        TextSpan(19, 81, 36, 98, "sm", 10),
        TextSpan(100, 70, 160, 87, "[ˌænθrəpəˈsentrɪz", 10),
        TextSpan(100, 81, 124, 98, "əm]", 10),
        TextSpan(188, 70, 300, 87, "n. a belief that considers", 10),
        TextSpan(188, 81, 300, 98, "human beings as central", 10),
        TextSpan(19, 140, 72, 157, "creed", 10),
        TextSpan(100, 140, 160, 157, "[krid]", 10),
        TextSpan(188, 140, 300, 157, "n. a set of beliefs", 10),
    ]

    rows, state = group_spans_into_rows(
        spans,
        page_number=40,
        state=ParserState(next_order=412, section="list4"),
    )

    assert [row.columns[0] for row in rows] == ["anthropocentrism", "creed"]
    assert rows[0].columns[1] == "[ˌænθrəpəˈsentrɪz\nəm]"
    assert rows[0].columns[2] == (
        "n. a belief that considers\nhuman beings as central"
    )
    assert [row.source_order for row in rows] == [412, 413]
    assert state.next_order == 414


def test_explicit_row_bands_prevent_short_row_from_absorbing_neighbors():
    spans = [
        TextSpan(19, 50, 70, 67, "alpha", 10),
        TextSpan(100, 50, 150, 67, "[a]", 10),
        TextSpan(384, 55, 500, 66, "alpha example", 10),
        TextSpan(384, 90, 500, 101, "alpha tail", 10),
        TextSpan(19, 110, 70, 127, "beta", 10),
        TextSpan(100, 110, 150, 127, "[b]", 10),
        TextSpan(384, 105, 500, 116, "beta example", 10),
        TextSpan(19, 170, 70, 187, "gamma", 10),
        TextSpan(100, 170, 150, 187, "[g]", 10),
        TextSpan(384, 165, 500, 176, "gamma example", 10),
    ]

    rows, _ = group_spans_into_rows(
        spans,
        page_number=110,
        state=ParserState(next_order=1, section="list12"),
        row_boundaries=(40.0, 100.0, 160.0, 220.0),
    )

    assert [row.columns[4] for row in rows] == [
        "alpha example\nalpha tail",
        "beta example",
        "gamma example",
    ]


def test_splits_combined_headword_and_phonetic_span_into_one_real_row():
    spans = [
        TextSpan(
            19,
            70,
            176,
            87,
            "heterogeneous [ˌhetərəˈdʒi:niəs]",
            10,
        ),
        TextSpan(188, 70, 300, 87, "adj. made up of parts", 10),
        TextSpan(19, 130, 80, 147, "oppressive", 10),
        TextSpan(100, 130, 160, 147, "[əˈpresɪv]", 10),
        TextSpan(188, 130, 300, 147, "adj. very cruel", 10),
    ]

    rows, _ = group_spans_into_rows(
        spans,
        page_number=119,
        state=ParserState(next_order=1, section="list13"),
        row_boundaries=(40.0, 100.0, 160.0),
    )

    assert [row.columns[0] for row in rows] == ["heterogeneous", "oppressive"]
    assert rows[0].columns[1] == "[ˌhetərəˈdʒi:niəs]"


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


@pytest.mark.parametrize(
    "page_index, complete_headword, continuation",
    [
        (7, "unconscionable", "e"),
        (39, "anthropocentrism", "sm"),
        (104, "half-formulated", "formulated"),
    ],
)
def test_real_pdf_wrapped_headword_has_one_anchor_row(
    page_index, complete_headword, continuation
):
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
    headwords = [row.columns[0] for row in rows]

    assert complete_headword in headwords
    assert continuation not in headwords


def _real_pdf_rows(page_index):
    source = os.environ.get("GRE_SOURCE_PDF")
    if not source:
        pytest.skip("GRE_SOURCE_PDF is not configured")

    with fitz.open(source) as document:
        page = document[page_index]
        spans = extract_page_spans(page)
        boundaries = layout_module.extract_page_row_boundaries(page)
    rows, _ = group_spans_into_rows(
        spans,
        page_number=page_index + 1,
        state=ParserState(next_order=1, section="sample"),
        row_boundaries=boundaries,
    )
    return {row.columns[0]: row for row in rows}


def test_real_pdf_row_bands_recover_bottom_translation():
    rows = _real_pdf_rows(8)

    assert rows["fluctuate"].columns[4] == (
        "Body temperature can fluctuate if you \n"
        "are ill.\n"
        "人患病后体温可能会上下波动。"
    )


def test_real_pdf_row_bands_keep_comestible_and_neighbors_separate():
    rows = _real_pdf_rows(13)

    assert rows["occult"].columns[4].endswith("过同样的情景似的。")
    assert rows["comestible"].columns[4] == (
        "Ethyl lactate is one kind of comestible \n"
        "synthetic spicery. \n"
        "乳酸乙酯是一种食用合成香料。"
    )
    assert rows["embed"].columns[4].startswith("They used to kind of embed it")


def test_real_pdf_short_slump_row_does_not_absorb_either_neighbor():
    rows = _real_pdf_rows(109)

    assert rows["belabor"].columns[4].endswith("解这件事的重要性")
    assert rows["slump"].columns[4] == (
        "Sales have slumped this year.\n今年销售量锐减。"
    )
    assert rows["elemental"].columns[4].startswith(
        "Learning to control one of the most ele"
    )
    assert rows["aboriginal"].columns[4].startswith(
        "The lndians are the aboriginal"
    )


def test_real_pdf_combined_headword_phonetic_restores_missing_row_and_neighbors():
    rows = _real_pdf_rows(118)

    assert rows["heterogeneous"].columns == (
        "heterogeneous",
        "[ˌhetərəˈdʒi:niəs]",
        "adj. made up of parts that \nare different 各种各样的",
        "disparate, \ndissimilar",
        "America has a very heterogeneous \npopulation. \n美国人口是由不同种族组成的。",
    )
    assert "adj. made up of parts" not in rows["halfhearted"].columns[2]
    assert rows["oppressive"].columns[2].startswith(
        "(1)adj. very cruel or unfair"
    )
    assert "are different" not in rows["oppressive"].columns[2]
    assert rows["oppressive"].columns[3] == ""
    assert not rows["oppressive"].columns[4].startswith("美国人口")


def test_physical_row_coverage_rejects_a_band_without_a_headword_anchor():
    spans = [
        span(19, 50, "alpha"),
        span(100, 50, "[alpha]"),
        span(188, 50, "first definition"),
        span(100, 110, "[missing]"),
        span(188, 110, "definition without a headword"),
    ]

    with pytest.raises(
        ValueError,
        match=r"page 5 physical row coverage failed: .*empty_row_bands=1",
    ):
        layout_module.validate_physical_row_coverage(
            spans,
            page_number=5,
            physical_row_bands=((40.0, 100.0), (100.0, 160.0)),
        )


def test_physical_row_coverage_rejects_multiple_anchors_in_one_band():
    spans = [
        span(19, 50, "alpha"),
        span(100, 50, "[alpha]"),
        span(19, 75, "beta"),
        span(100, 75, "[beta]"),
    ]

    with pytest.raises(
        ValueError,
        match=r"page 5 physical row coverage failed: .*multi_anchor_row_bands=1",
    ):
        layout_module.validate_physical_row_coverage(
            spans,
            page_number=5,
            physical_row_bands=((40.0, 100.0),),
        )


def test_unicode_latin_headwords_are_anchors_but_non_latin_headers_are_not():
    spans = [
        span(19, 50, "单词"),
        span(19, 110, "naiveté"),
        span(100, 110, "[na:'i:vtei]"),
        span(188, 110, "n. innocence"),
        span(19, 170, "cliché"),
        span(100, 170, "['kli:ʃei]"),
        span(188, 170, "n. a hackneyed theme"),
    ]

    rows, _ = group_spans_into_rows(
        spans,
        page_number=5,
        state=ParserState(next_order=1, section="list1"),
        row_boundaries=(40.0, 100.0, 160.0, 220.0),
    )

    assert [row.columns[0] for row in rows] == ["naiveté", "cliché"]


def test_real_pdf_all_independent_physical_word_bands_have_one_anchor():
    source = os.environ.get("GRE_SOURCE_PDF")
    if not source:
        pytest.skip("GRE_SOURCE_PDF is not configured")

    physical_row_bands = 0
    with fitz.open(source) as document:
        for page_index in range(4, len(document)):
            page = document[page_index]
            spans = extract_page_spans(page)
            bands = layout_module.extract_page_word_row_bands(
                page,
                spans,
                is_last_page=page_index + 1 == len(document),
            )
            coverage = layout_module.validate_physical_row_coverage(
                spans,
                page_number=page_index + 1,
                physical_row_bands=bands,
            )
            physical_row_bands += coverage.physical_row_bands
            assert coverage.empty_row_bands == 0
            assert coverage.multi_anchor_row_bands == 0

    assert physical_row_bands == 3292


@pytest.mark.parametrize(
    "page_index, headword",
    [(180, "naiveté"), (204, "cliché")],
)
def test_real_pdf_unicode_latin_headword_row_is_not_missed(page_index, headword):
    rows = _real_pdf_rows(page_index)

    assert headword in rows


def test_page_288_requiem_uses_an_independent_footer_bounded_physical_row():
    source = os.environ.get("GRE_SOURCE_PDF")
    if not source:
        pytest.skip("GRE_SOURCE_PDF is not configured")

    with fitz.open(source) as document:
        page = document[287]
        spans = extract_page_spans(page)
        bands = layout_module.extract_page_word_row_bands(
            page,
            spans,
            is_last_page=True,
        )
        rows, _ = group_spans_into_rows(
            spans,
            page_number=288,
            state=ParserState(next_order=1, section="supplement-4"),
            physical_row_bands=bands,
        )
    requiem = next(span for span in spans if span.text == "requiem")
    requiem_center = (requiem.y0 + requiem.y1) / 2
    footer_top = min(
        span.y0 for span in spans if span.y0 > 800 and span.size < 9
    )

    assert bands[-1] == pytest.approx((667.160034, footer_top))
    assert bands[-1][0] <= requiem_center < bands[-1][1]
    assert rows[-1].columns[0] == "requiem"
