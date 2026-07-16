import re
from collections import defaultdict
from collections.abc import Iterable, Sequence

from .types import ParserState, RawWordRow, TextSpan


COLUMN_BOUNDS = (0.0, 95.0, 180.0, 315.0, 380.0, 596.0)
HEADWORD = re.compile(r"^[A-Za-z][A-Za-z .'-]*$")
COMBINED_HEADWORD_PHONETIC = re.compile(
    r"^([A-Za-z][A-Za-z .'-]*?)\s+(\[[^\n]+\])$"
)
SECTION = re.compile(r"(补充重点单词\s*)?list\s*(\d+)", re.IGNORECASE)
SUPPLEMENT = re.compile(r"补充重点单词")
MAIN_HEADER = re.compile(r"张巍|镇考|乱序版")
HEADER_BRANDING = re.compile(r"微信公众号")
HEADER_LINE_TOLERANCE = 4.0


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
        if match is None:
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
) -> tuple[list[RawWordRow], ParserState]:
    usable = [
        span
        for span in _split_combined_headword_phonetic(spans)
        if 38 <= span.y0 <= 810 and span.size <= 25
    ]
    section_events: list[tuple[float, str]] = []
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
        section_events.append((_center_y(span), prefix + match.group(2)))
    section_events.sort(key=lambda item: item[0])
    header_centers = [y for y, _ in section_events]
    for event_y, section in section_events:
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
    anchor_spans = sorted(
        [
            span
            for span in content
            if span.x0 < COLUMN_BOUNDS[1] and HEADWORD.fullmatch(span.text)
        ],
        key=_center_y,
    )
    anchors = _merge_wrapped_anchors(anchor_spans)

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
