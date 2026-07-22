from __future__ import annotations

import hashlib
import re
import statistics
import unicodedata
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import fitz

from .normalize import WordDraft


_EQUIVALENCE_TEXT = re.compile(r"[A-Za-z][A-Za-z' .,-]*\Z")
_MACHINE_HEADWORD_TEXT = re.compile(r"[^\W\d_][^\r\n]*\Z", re.UNICODE)


@dataclass(frozen=True, slots=True)
class EquivalenceRow:
    headword: str
    equivalents: tuple[str, ...]
    source_page: int


@dataclass(frozen=True, slots=True)
class Machine7Headword:
    headword: str
    source_page: int


@dataclass(frozen=True, slots=True)
class EquivalenceEdge:
    left_word_id: int
    right_word_id: int
    source_pages: tuple[int, ...]

    def __post_init__(self) -> None:
        if not 0 < self.left_word_id < self.right_word_id:
            raise ValueError("equivalence edge ids must be positive and ordered")
        if not self.source_pages or any(page <= 0 for page in self.source_pages):
            raise ValueError("equivalence edge must have positive source pages")
        if tuple(sorted(set(self.source_pages))) != self.source_pages:
            raise ValueError("equivalence source pages must be unique and sorted")


@dataclass(frozen=True, slots=True)
class Machine7Membership:
    word_id: int
    source_page: int
    source_headword: str

    def __post_init__(self) -> None:
        if self.word_id <= 0 or self.source_page <= 0:
            raise ValueError("machine 7.0 membership ids and pages must be positive")
        if not self.source_headword.strip():
            raise ValueError("machine 7.0 source headword cannot be blank")


@dataclass(frozen=True, slots=True)
class ReferenceData:
    equivalence_edges: tuple[EquivalenceEdge, ...] = ()
    machine7_memberships: tuple[Machine7Membership, ...] = ()
    facts: dict[str, object] | None = None

    @classmethod
    def empty(cls) -> "ReferenceData":
        return cls(
            facts={
                "equivalence": {
                    "configured": False,
                    "sha256": "",
                    "page_count": 0,
                    "row_count": 0,
                    "unique_headword_count": 0,
                    "equivalent_mention_count": 0,
                    "matched_headword_rows": 0,
                    "matched_equivalent_mentions": 0,
                    "edge_count": 0,
                    "unmatched_headwords": [],
                    "unmatched_equivalents": [],
                },
                "machine7": {
                    "configured": False,
                    "sha256": "",
                    "page_count": 0,
                    "headword_count": 0,
                    "unique_headword_count": 0,
                    "matched_count": 0,
                    "unmatched_headwords": [],
                },
            }
        )


@dataclass(frozen=True, slots=True)
class _TextLine:
    baseline: float
    x0: float
    x1: float
    text: str
    fonts: tuple[str, ...]
    sizes: tuple[float, ...]


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _page_lines(page: fitz.Page) -> list[_TextLine]:
    result: list[_TextLine] = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", ()):
            spans = sorted(line["spans"], key=lambda span: span["origin"][0])
            text = "".join(span["text"] for span in spans).strip()
            if not text:
                continue
            result.append(
                _TextLine(
                    baseline=float(
                        statistics.median(span["origin"][1] for span in spans)
                    ),
                    x0=float(min(span["bbox"][0] for span in spans)),
                    x1=float(max(span["bbox"][2] for span in spans)),
                    text=text,
                    fonts=tuple(str(span["font"]) for span in spans),
                    sizes=tuple(float(span["size"]) for span in spans),
                )
            )
    return result


def _equivalence_token_text(value: str) -> str:
    value = _equivalence_line_text(value)
    value = re.sub(r"\s+,", ",", value)
    value = re.sub(r",(?=\S)", ", ", value)
    return re.sub(r"\s+", " ", value).strip(" ,")


def _equivalence_line_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).replace("，", ",")
    return re.sub(r"\s+", " ", value).strip()


def parse_equivalence_pdf(path: Path) -> tuple[tuple[EquivalenceRow, ...], int]:
    rows: list[EquivalenceRow] = []
    with fitz.open(path) as document:
        if document.needs_pass:
            raise ValueError("equivalence PDF requires a password")
        page_count = len(document)
        for page_index in range(4, page_count):
            lines = _page_lines(document[page_index])
            anchors = sorted(
                (
                    line.baseline,
                    _equivalence_line_text(line.text),
                )
                for line in lines
                if 55 <= line.baseline <= 780
                and 80 <= line.x0 <= 180
                and _EQUIVALENCE_TEXT.fullmatch(
                    _equivalence_line_text(line.text)
                )
                and all("Bold" in font for font in line.fonts)
                and all(abs(size - 11.05) < 0.25 for size in line.sizes)
            )
            equivalent_lines = [
                (
                    line.baseline,
                    line.x0,
                    _equivalence_line_text(line.text),
                )
                for line in lines
                if 55 <= line.baseline <= 780
                and 190 <= (line.x0 + line.x1) / 2 <= 390
                and _EQUIVALENCE_TEXT.fullmatch(
                    _equivalence_line_text(line.text)
                )
                and all(abs(size - 11.05) < 0.25 for size in line.sizes)
            ]
            for index, (baseline, headword) in enumerate(anchors):
                lower = (
                    (anchors[index - 1][0] + baseline) / 2
                    if index
                    else 50.0
                )
                upper = (
                    (baseline + anchors[index + 1][0]) / 2
                    if index + 1 < len(anchors)
                    else 785.0
                )
                pieces = [
                    text
                    for candidate_y, _x0, text in sorted(equivalent_lines)
                    if lower < candidate_y <= upper
                ]
                rendered = _equivalence_token_text(" ".join(pieces))
                equivalents = tuple(
                    dict.fromkeys(
                        item.strip()
                        for item in rendered.split(",")
                        if item.strip()
                    )
                )
                if not equivalents:
                    raise ValueError(
                        "equivalence row has no equivalent terms: "
                        f"page={page_index + 1}, headword={headword!r}"
                    )
                rows.append(
                    EquivalenceRow(
                        headword=headword,
                        equivalents=equivalents,
                        source_page=page_index + 1,
                    )
                )
    if not rows:
        raise ValueError("equivalence PDF contains no parsed rows")
    return tuple(rows), page_count


def parse_machine7_pdf(path: Path) -> tuple[tuple[Machine7Headword, ...], int]:
    rows: list[Machine7Headword] = []
    with fitz.open(path) as document:
        if document.needs_pass:
            raise ValueError("machine 7.0 PDF requires a password")
        page_count = len(document)
        for page_index in range(4, page_count):
            fragments: list[tuple[float, str]] = []
            for block in document[page_index].get_text("dict")["blocks"]:
                for line in block.get("lines", ()):
                    for span in line["spans"]:
                        x, y = span["origin"]
                        text = str(span["text"]).strip()
                        if (
                            "Bold" in str(span["font"])
                            and x < 30
                            and 40 <= y <= 810
                            and abs(float(span["size"]) - 9.945) < 0.25
                            and text
                        ):
                            fragments.append((float(y), text))
            fragments.sort()
            groups: list[list[tuple[float, str]]] = []
            for baseline, text in fragments:
                if groups and baseline - groups[-1][-1][0] < 16.0:
                    groups[-1].append((baseline, text))
                else:
                    groups.append([(baseline, text)])
            for group in groups:
                headword = unicodedata.normalize(
                    "NFKC", "".join(fragment for _y, fragment in group)
                ).strip()
                if _MACHINE_HEADWORD_TEXT.fullmatch(headword) is None:
                    raise ValueError(
                        "invalid machine 7.0 headword: "
                        f"page={page_index + 1}, headword={headword!r}"
                    )
                rows.append(
                    Machine7Headword(
                        headword=headword,
                        source_page=page_index + 1,
                    )
                )
    normalized = [_match_key(row.headword) for row in rows]
    if not rows:
        raise ValueError("machine 7.0 PDF contains no parsed headwords")
    if len(normalized) != len(set(normalized)):
        raise ValueError("machine 7.0 PDF contains duplicate parsed headwords")
    return tuple(rows), page_count


def _match_key(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold().strip()


def _compact_match_key(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", _match_key(value))
    accentless = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return re.sub(r"[^a-z0-9]", "", accentless)


def _word_matcher(
    entries: Sequence[WordDraft],
) -> tuple[dict[str, tuple[int, ...]], dict[str, tuple[int, ...]]]:
    exact: dict[str, list[int]] = defaultdict(list)
    compact: dict[str, list[int]] = defaultdict(list)
    for word_id, entry in enumerate(
        sorted(entries, key=lambda item: item.source_order), start=1
    ):
        exact[_match_key(entry.headword)].append(word_id)
        compact[_compact_match_key(entry.headword)].append(word_id)
    return (
        {key: tuple(values) for key, values in exact.items()},
        {key: tuple(values) for key, values in compact.items()},
    )


def _match_word_id(
    value: str,
    exact: dict[str, tuple[int, ...]],
    compact: dict[str, tuple[int, ...]],
) -> int | None:
    candidates = exact.get(_match_key(value), ())
    if not candidates:
        candidates = compact.get(_compact_match_key(value), ())
    return candidates[0] if len(candidates) == 1 else None


def load_reference_data(
    entries: Sequence[WordDraft],
    *,
    equivalence_pdf: Path,
    machine7_pdf: Path,
) -> ReferenceData:
    equivalence_hash = file_sha256(equivalence_pdf)
    machine7_hash = file_sha256(machine7_pdf)
    equivalence_rows, equivalence_pages = parse_equivalence_pdf(equivalence_pdf)
    machine7_rows, machine7_pages = parse_machine7_pdf(machine7_pdf)
    if file_sha256(equivalence_pdf) != equivalence_hash:
        raise ValueError("equivalence PDF changed during extraction")
    if file_sha256(machine7_pdf) != machine7_hash:
        raise ValueError("machine 7.0 PDF changed during extraction")

    exact, compact = _word_matcher(entries)
    edge_pages: dict[tuple[int, int], set[int]] = defaultdict(set)
    unmatched_heads: list[dict[str, object]] = []
    unmatched_equivalents: list[dict[str, object]] = []
    matched_headword_rows = 0
    matched_equivalent_mentions = 0
    equivalent_mention_count = 0
    for row in equivalence_rows:
        headword_id = _match_word_id(row.headword, exact, compact)
        if headword_id is None:
            unmatched_heads.append(
                {"headword": row.headword, "source_page": row.source_page}
            )
        else:
            matched_headword_rows += 1
        for equivalent in row.equivalents:
            equivalent_mention_count += 1
            equivalent_id = _match_word_id(equivalent, exact, compact)
            if equivalent_id is None:
                unmatched_equivalents.append(
                    {"headword": equivalent, "source_page": row.source_page}
                )
                continue
            matched_equivalent_mentions += 1
            if headword_id is None or equivalent_id == headword_id:
                continue
            left, right = sorted((headword_id, equivalent_id))
            edge_pages[(left, right)].add(row.source_page)

    edges = tuple(
        EquivalenceEdge(left, right, tuple(sorted(pages)))
        for (left, right), pages in sorted(edge_pages.items())
    )

    memberships: list[Machine7Membership] = []
    unmatched_machine7: list[dict[str, object]] = []
    for row in machine7_rows:
        word_id = _match_word_id(row.headword, exact, compact)
        if word_id is None:
            unmatched_machine7.append(
                {"headword": row.headword, "source_page": row.source_page}
            )
            continue
        memberships.append(
            Machine7Membership(
                word_id=word_id,
                source_page=row.source_page,
                source_headword=row.headword,
            )
        )
    memberships.sort(key=lambda item: item.word_id)
    if len({item.word_id for item in memberships}) != len(memberships):
        raise ValueError("machine 7.0 rows resolved to duplicate main-word ids")

    facts: dict[str, object] = {
        "equivalence": {
            "configured": True,
            "sha256": equivalence_hash,
            "page_count": equivalence_pages,
            "row_count": len(equivalence_rows),
            "unique_headword_count": len(
                {_match_key(row.headword) for row in equivalence_rows}
            ),
            "equivalent_mention_count": equivalent_mention_count,
            "matched_headword_rows": matched_headword_rows,
            "matched_equivalent_mentions": matched_equivalent_mentions,
            "edge_count": len(edges),
            "unmatched_headwords": unmatched_heads,
            "unmatched_equivalents": unmatched_equivalents,
        },
        "machine7": {
            "configured": True,
            "sha256": machine7_hash,
            "page_count": machine7_pages,
            "headword_count": len(machine7_rows),
            "unique_headword_count": len(
                {_match_key(row.headword) for row in machine7_rows}
            ),
            "matched_count": len(memberships),
            "unmatched_headwords": unmatched_machine7,
        },
    }
    return ReferenceData(edges, tuple(memberships), facts)
