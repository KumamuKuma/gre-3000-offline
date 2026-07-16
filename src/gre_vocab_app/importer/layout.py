import re
import unicodedata
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from .types import ParserState, RawWordRow, TextSpan


COLUMN_BOUNDS = (0.0, 95.0, 180.0, 315.0, 380.0, 596.0)
COMBINED_HEADWORD_PHONETIC = re.compile(r"^(.+?)\s+(\[[^\n]+\])$")
SECTION = re.compile(r"(补充重点单词\s*)?list\s*(\d+)", re.IGNORECASE)
SUPPLEMENT = re.compile(r"补充重点单词")
MAIN_HEADER = re.compile(r"张巍|镇考|乱序版")
HEADER_BRANDING = re.compile(r"微信公众号")
LATEST_VOCAB_HEADER = re.compile(r"最新真题词汇")
HEADER_LINE_TOLERANCE = 4.0
TABLE_HEADER_BOTTOM = 41.0
FOOTER_TOP_FRACTION = 0.9
FOOTER_MAX_SIZE = 9.0
MINIMUM_OPEN_ROW_HEIGHT = 30.0
HEADWORD_PUNCTUATION = frozenset(" .'-")


@dataclass(frozen=True, slots=True)
class PhysicalRowCoverage:
    physical_row_bands: int
    empty_row_bands: int
    multi_anchor_row_bands: int


def extract_page_spans(page) -> list[TextSpan]:
    result: list[TextSpan] = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for item in line.get("spans", []):
                text = item["text"].strip()
                if text:
                    x0, y0, x1, y1 = item["bbox"]
                    result.append(
                        TextSpan(x0, y0, x1, y1, text, item["size"])
                    )
    return result


def extract_page_row_boundaries(page) -> tuple[float, ...]:
    minimum_width = float(page.rect.width) * 0.8
    candidates = sorted(
        float(drawing["rect"].y0)
        for drawing in page.get_drawings()
        if drawing["rect"].width > minimum_width
        and drawing["rect"].height < 1.0
    )
    boundaries: list[float] = []
    for candidate in candidates:
        if not boundaries or candidate - boundaries[-1] > 0.5:
            boundaries.append(candidate)
    return tuple(boundaries)


def _column(x0: float) -> int | None:
    for index in range(5):
        if COLUMN_BOUNDS[index] <= x0 < COLUMN_BOUNDS[index + 1]:
            return index
    return None


def _join_cell(spans: Iterable[TextSpan]) -> str:
    lines: dict[float, list[TextSpan]] = defaultdict(list)
    for item in spans:
        lines[round(item.y0, 1)].append(item)

    rendered = []
    for y in sorted(lines):
        rendered.append(
            " ".join(item.text for item in sorted(lines[y], key=lambda span: span.x0))
        )
    return "\n".join(rendered).strip()


def _center_y(span: TextSpan) -> float:
    return (span.y0 + span.y1) / 2


def _is_latin_letter(character: str) -> bool:
    return unicodedata.category(character).startswith("L") and "LATIN" in (
        unicodedata.name(character, "")
    )


def _is_headword(text: str) -> bool:
    return bool(text) and _is_latin_letter(text[0]) and all(
        _is_latin_letter(character) or character in HEADWORD_PUNCTUATION
        for character in text
    )


def _merge_wrapped_anchors(anchors: list[TextSpan]) -> list[TextSpan]:
    merged: list[TextSpan] = []
    for anchor in anchors:
        if not merged or anchor.y0 >= merged[-1].y1:
            merged.append(anchor)
            continue

        previous = merged[-1]
        same_line = (
            abs(_center_y(previous) - _center_y(anchor))
            <= HEADER_LINE_TOLERANCE
        )
        separated = anchor.x0 > previous.x1 + 1.0
        separator = " " if same_line and separated else ""
        merged[-1] = TextSpan(
            x0=min(previous.x0, anchor.x0),
            y0=min(previous.y0, anchor.y0),
            x1=max(previous.x1, anchor.x1),
            y1=max(previous.y1, anchor.y1),
            text=f"{previous.text}{separator}{anchor.text}",
            size=max(previous.size, anchor.size),
        )
    return merged


def _split_combined_headword_phonetic(spans: Iterable[TextSpan]) -> list[TextSpan]:
    result: list[TextSpan] = []
    for span in spans:
        match = (
            COMBINED_HEADWORD_PHONETIC.fullmatch(span.text)
            if span.x0 < COLUMN_BOUNDS[1]
            else None
        )
        if match is None or not _is_headword(match.group(1)):
            result.append(span)
            continue

        headword, phonetic = match.groups()
        result.extend(
            (
                TextSpan(
                    span.x0,
                    span.y0,
                    min(span.x1, COLUMN_BOUNDS[1] - 1.0),
                    span.y1,
                    headword,
                    span.size,
                ),
                TextSpan(
                    COLUMN_BOUNDS[1] + 1.0,
                    span.y0,
                    max(span.x1, COLUMN_BOUNDS[1] + 2.0),
                    span.y1,
                    phonetic,
                    span.size,
                ),
            )
        )
    return result


def _usable_spans(spans: Iterable[TextSpan]) -> list[TextSpan]:
    return [
        span
        for span in _split_combined_headword_phonetic(spans)
        if 38 <= span.y0 <= 810 and span.size <= 25
    ]


def _section_events(usable: Sequence[TextSpan]) -> list[tuple[float, str]]:
    events: list[tuple[float, str]] = []
    for span in usable:
        match = SECTION.search(span.text)
        if not match:
            continue
        line_neighbors = [
            other
            for other in usable
            if abs(_center_y(other) - _center_y(span)) <= HEADER_LINE_TOLERANCE
        ]
        is_supplement = bool(match.group(1)) or any(
            SUPPLEMENT.search(other.text) for other in line_neighbors
        )
        is_main_header = span.x0 < 180 or any(
            MAIN_HEADER.search(other.text) for other in line_neighbors
        )
        if not is_supplement and not is_main_header:
            continue
        prefix = "supplement-" if is_supplement else "list"
        events.append((_center_y(span), prefix + match.group(2)))
    events.sort(key=lambda item: item[0])
    return events


def _content_spans(
    spans: Iterable[TextSpan],
) -> tuple[list[TextSpan], list[tuple[float, str]]]:
    usable = _usable_spans(spans)
    events = _section_events(usable)
    header_centers = [y for y, _ in events]
    for event_y, section in events:
        if not section.startswith("supplement-"):
            continue
        header_centers.extend(
            _center_y(span)
            for span in usable
            if HEADER_BRANDING.search(span.text)
            and 0 < _center_y(span) - event_y <= 32
        )
    content = [
        span
        for span in usable
        if not any(
            abs(_center_y(span) - y) <= HEADER_LINE_TOLERANCE
            for y in header_centers
        )
    ]
    return content, events


def _headword_anchors(content: Iterable[TextSpan]) -> list[TextSpan]:
    anchor_spans = sorted(
        [
            span
            for span in content
            if span.x0 < COLUMN_BOUNDS[1] and _is_headword(span.text)
        ],
        key=_center_y,
    )
    return _merge_wrapped_anchors(anchor_spans)


def _is_latest_vocab_header_band(
    spans: Sequence[TextSpan], start_y: float, end_y: float
) -> bool:
    texts = [
        span.text for span in spans if start_y <= _center_y(span) < end_y
    ]
    return any(LATEST_VOCAB_HEADER.search(text) for text in texts) and any(
        HEADER_BRANDING.search(text) for text in texts
    )


def _has_continuous_body_border(
    page, row_boundaries: Sequence[float]
) -> bool:
    body_top = next(
        (
            boundary
            for boundary in row_boundaries
            if boundary >= TABLE_HEADER_BOTTOM - 1.0
        ),
        row_boundaries[0],
    )
    body_bottom = row_boundaries[-1]
    return any(
        drawing["rect"].width < 1.0
        and drawing["rect"].height > 1.0
        and drawing["rect"].y0 <= body_top + 0.5
        and drawing["rect"].y1 >= body_bottom - 0.5
        for drawing in page.get_drawings()
    )


def _footer_top(spans: Sequence[TextSpan], page_height: float) -> float | None:
    candidates = [
        span.y0
        for span in spans
        if span.y0 >= page_height * FOOTER_TOP_FRACTION
        and span.size < FOOTER_MAX_SIZE
    ]
    return min(candidates) if candidates else None


def extract_page_word_row_bands(
    page,
    spans: Sequence[TextSpan],
    *,
    is_last_page: bool = False,
) -> tuple[tuple[float, float], ...]:
    """Enumerate physical word rows from PDF geometry, independent of anchors."""
    row_boundaries = extract_page_row_boundaries(page)
    if len(row_boundaries) < 2:
        return ()

    events = _section_events(_usable_spans(spans))
    bands = [
        (start_y, end_y)
        for start_y, end_y in zip(row_boundaries, row_boundaries[1:])
        if end_y > TABLE_HEADER_BOTTOM
        and not any(start_y <= event_y < end_y for event_y, _ in events)
        and not _is_latest_vocab_header_band(spans, start_y, end_y)
    ]

    footer_top = _footer_top(spans, float(page.rect.height))
    if (
        is_last_page
        and footer_top is not None
        and footer_top - row_boundaries[-1] >= MINIMUM_OPEN_ROW_HEIGHT
        and not _has_continuous_body_border(page, row_boundaries)
    ):
        bands.append((row_boundaries[-1], footer_top))
    return tuple(bands)


def _format_bands(bands: Sequence[tuple[float, float]]) -> str:
    return ",".join(f"{start_y:.2f}-{end_y:.2f}" for start_y, end_y in bands)


def validate_physical_row_coverage(
    spans: Sequence[TextSpan],
    *,
    page_number: int,
    physical_row_bands: Sequence[tuple[float, float]],
) -> PhysicalRowCoverage:
    content, _ = _content_spans(spans)
    anchors = _headword_anchors(content)
    anchors_by_band = [
        [
            anchor
            for anchor in anchors
            if start_y <= _center_y(anchor) < end_y
        ]
        for start_y, end_y in physical_row_bands
    ]
    empty = [
        band
        for band, band_anchors in zip(physical_row_bands, anchors_by_band)
        if not band_anchors
    ]
    multiple = [
        band
        for band, band_anchors in zip(physical_row_bands, anchors_by_band)
        if len(band_anchors) > 1
    ]
    unassigned = [
        anchor
        for anchor in anchors
        if not any(
            start_y <= _center_y(anchor) < end_y
            for start_y, end_y in physical_row_bands
        )
    ]
    if empty or multiple or unassigned:
        details = [
            f"physical_row_bands={len(physical_row_bands)}",
            f"empty_row_bands={len(empty)}",
            f"multi_anchor_row_bands={len(multiple)}",
            f"unassigned_headword_anchors={len(unassigned)}",
        ]
        if empty:
            details.append(f"empty={_format_bands(empty)}")
        if multiple:
            details.append(f"multiple={_format_bands(multiple)}")
        if unassigned:
            details.append(
                "unassigned=" + ",".join(anchor.text for anchor in unassigned)
            )
        raise ValueError(
            f"page {page_number} physical row coverage failed: "
            + " ".join(details)
        )
    return PhysicalRowCoverage(
        physical_row_bands=len(physical_row_bands),
        empty_row_bands=0,
        multi_anchor_row_bands=0,
    )


def _physical_row_bounds(
    anchor: TextSpan, row_boundaries: Sequence[float]
) -> tuple[float, float] | None:
    center = _center_y(anchor)
    lower = [boundary for boundary in row_boundaries if boundary < center]
    upper = [boundary for boundary in row_boundaries if boundary > center]
    if not lower or not upper:
        return None
    return max(lower), min(upper)


def group_spans_into_rows(
    spans: list[TextSpan],
    page_number: int,
    state: ParserState,
    *,
    row_boundaries: Sequence[float] = (),
    physical_row_bands: Sequence[tuple[float, float]] = (),
) -> tuple[list[RawWordRow], ParserState]:
    content, section_events = _content_spans(spans)
    anchors = _headword_anchors(content)

    rows: list[RawWordRow] = []
    current_section = state.section
    next_order = state.next_order
    for index, anchor in enumerate(anchors):
        for event_y, event_section in section_events:
            if event_y <= _center_y(anchor):
                current_section = event_section

        midpoint_start = (
            (_center_y(anchors[index - 1]) + _center_y(anchor)) / 2
            if index
            else 38
        )
        midpoint_end = (
            (_center_y(anchor) + _center_y(anchors[index + 1])) / 2
            if index + 1 < len(anchors)
            else 810
        )
        if physical_row_bands:
            physical_bounds = next(
                (
                    band
                    for band in physical_row_bands
                    if band[0] <= _center_y(anchor) < band[1]
                ),
                None,
            )
            if physical_bounds is None:
                raise ValueError(
                    f"headword anchor outside physical row bands: {anchor.text}"
                )
        else:
            physical_bounds = _physical_row_bounds(anchor, row_boundaries)
        start_y, end_y = physical_bounds or (midpoint_start, midpoint_end)
        buckets: list[list[TextSpan]] = [[] for _ in range(5)]
        for item in content:
            center_y = _center_y(item)
            column = _column(item.x0)
            if column is not None and start_y <= center_y < end_y:
                buckets[column].append(item)

        columns = (anchor.text,) + tuple(
            _join_cell(bucket) for bucket in buckets[1:]
        )
        flags = ("missing_phonetic",) if not columns[1] else ()
        rows.append(
            RawWordRow(
                source_page=page_number,
                source_order=next_order,
                source_section=current_section,
                columns=columns,
                flags=flags,
            )
        )
        next_order += 1

    final_section = section_events[-1][1] if section_events else current_section
    return rows, ParserState(next_order=next_order, section=final_section)
