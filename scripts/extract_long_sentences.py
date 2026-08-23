from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

import fitz
from pypdf import PdfReader


SCHEMA = "gre-long-sentences"
SCHEMA_VERSION = 2
SOURCE_TITLE = "杨鹏阅读长难句"
EXPECTED_FILE_SHA256 = (
    "50b594880839f5733cfb07304706d4ca93e691a025590b768b0de0c8534d6a02"
)
EXPECTED_PAGE_COUNT = 44
MISSING_SOURCE_NUMBERS = frozenset({70})
EXPECTED_SOURCE_NUMBERS = tuple(
    number
    for number in range(1, 133)
    if number not in MISSING_SOURCE_NUMBERS
)

DIFFICULTY_MARKER = re.compile(
    r"[（(]\s*(?:难度系数\s*)?[0-9][0-9+\-\s]*"
    r"(?:，下同)?\s*(?:[）)]|(?=\n))"
)

NOTE_HEADING = re.compile(
    r"(?m)^(?:"
    r"(?P<named>难句类型|难免类型|译文|解释|意群训练|训练)\s*[：:；;]\s*"
    r"|(?P<point>[A-Z])\s*[、．.]\s*"
    r"|(?P<lower>[a-z])(?=[\u3400-\u9fff])"
    r"|(?P<number>[1-9一二三四五六七八九十])\s*[、．]\s*"
    r")"
)

NOTE_LABEL_NORMALIZATION = {
    "难免类型": "难句类型",
    "训练": "意群训练",
}


@dataclass(frozen=True, slots=True)
class PageText:
    number: int
    text: str
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class EntryMarker:
    source_number: int
    start: int
    content_start: int


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _strip_page_footer(text: str, page_number: int) -> str:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    while lines and not lines[-1].strip():
        lines.pop()
    if lines and lines[-1].strip() == str(page_number):
        lines.pop()
    return "\n".join(lines).strip()


def _read_pages(document: fitz.Document) -> tuple[str, tuple[PageText, ...]]:
    combined_parts: list[str] = []
    pages: list[PageText] = []
    cursor = 0
    for index, page in enumerate(document):
        if combined_parts:
            separator = "\n\n"
            combined_parts.append(separator)
            cursor += len(separator)
        text = _strip_page_footer(page.get_text("text", sort=True), index + 1)
        start = cursor
        combined_parts.append(text)
        cursor += len(text)
        pages.append(PageText(index + 1, text, start, cursor))
    return "".join(combined_parts), tuple(pages)


def _read_unicode_pages(pdf_path: Path) -> str:
    """Read annotations through the PDF's complete ToUnicode mapping."""

    reader = PdfReader(str(pdf_path))
    parts: list[str] = []
    for page_number, page in enumerate(reader.pages, 1):
        text = page.extract_text(extraction_mode="layout") or ""
        parts.append(_strip_page_footer(text, page_number))
    return "\n\n".join(parts)


def _marker_pattern(source_number: int) -> re.Pattern[str]:
    if source_number == 27:
        # This PDF's embedded text layer is out of drawing order at the start
        # of sentence 27: ``27ls ... . The role ... detai feeling ...``.
        return re.compile(r"(?m)^\s*27ls of human behavior")
    if source_number == 129:
        # Sentence 129 follows the rewritten example for sentence 128 on the
        # same extracted line, so it cannot be restricted to a line start.
        return re.compile(r"(?<!\d)129\s*、\s*(?=To measure them properly)")
    return re.compile(
        rf"(?m)^\s*{source_number}\s*[.、]\s*"
        r"(?=[(（\"“―A-Z])"
    )


def _find_markers(text: str) -> tuple[EntryMarker, ...]:
    if _marker_pattern(70).search(text):
        raise ValueError(
            "source sentence 70 unexpectedly exists; review the pinned PDF "
            "numbering before changing the checked-in data"
        )
    markers: list[EntryMarker] = []
    cursor = 0
    for source_number in EXPECTED_SOURCE_NUMBERS:
        matches = list(_marker_pattern(source_number).finditer(text, cursor))
        if not matches:
            raise ValueError(f"source sentence {source_number} was not found")
        match = matches[0]
        markers.append(EntryMarker(source_number, match.start(), match.end()))
        cursor = match.end()
    return tuple(markers)


def _source_pages(
    pages: tuple[PageText, ...],
    *,
    start: int,
    end: int,
) -> list[int]:
    return [
        page.number
        for page in pages
        if start < page.end and end > page.start
    ]


def _raw_sentence(block: str, source_number: int) -> str:
    if source_number == 27:
        # Reconstructed from the visible PDF page. The source text layer puts
        # three fragments in the wrong order, but the rendered sentence is
        # unambiguous.
        return (
            "The role those anthropologists ascribe to evolution is not of "
            "dictating the details of human behavior but one of imposing "
            "constraints—ways of feeling, thinking, and acting that \"come "
            "naturally\" in archetypal situations in any culture."
        )
    if source_number in {119, 129}:
        ending = (
            "hitherto thought."
            if source_number == 119
            else "kept there for many months."
        )
        match = re.match(
            rf"\s*(.*?{re.escape(ending)})",
            block,
            flags=re.DOTALL,
        )
        if not match:
            raise ValueError(
                f"could not locate the end of source sentence {source_number}"
            )
        return match.group(1)

    difficulty_markers = list(DIFFICULTY_MARKER.finditer(block))
    if not difficulty_markers:
        raise ValueError(
            f"difficulty marker after source sentence {source_number} was not found"
        )
    # ``(15)`` inside sentence 63 is a question-number annotation, not its
    # difficulty marker. The actual ``(4+)`` marker is the second match; the
    # explanation later repeats ``(15)`` in its training copy.
    marker = (
        difficulty_markers[1]
        if source_number == 63
        else difficulty_markers[0]
    )
    return block[: marker.start()]


def _annotation_text(block: str, source_number: int) -> str:
    if source_number in {119, 129}:
        ending = (
            "hitherto thought."
            if source_number == 119
            else "kept there for many months."
        )
        match = re.match(
            rf"\s*.*?{re.escape(ending)}",
            block,
            flags=re.DOTALL,
        )
        if not match:
            raise ValueError(
                f"could not locate annotation start for source sentence "
                f"{source_number}"
            )
        return block[match.end() :]

    markers = list(DIFFICULTY_MARKER.finditer(block))
    if not markers:
        raise ValueError(
            f"difficulty marker after source sentence {source_number} was not found "
            "in the Unicode text layer"
        )
    marker = markers[1] if source_number == 63 else markers[0]
    return block[marker.start() :]


def _logical_note_text(text: str) -> str:
    lines = [
        re.sub(r"[ \t\u00a0]+", " ", line).strip()
        for line in text.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    ]
    return "\n".join(line for line in lines if line)


def _clean_note_text(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    cleaned = re.sub(
        r"(?<=[\u3400-\u9fff]) (?=[\u3400-\u9fff])",
        "",
        cleaned,
    )
    cleaned = re.sub(r"\s+([，。；：？！、）》”])", r"\1", cleaned)
    cleaned = re.sub(r"([《（“])\s+", r"\1", cleaned)
    return cleaned


def _audit_key(text: str) -> str:
    return re.sub(r"\s+", "", text)


def _split_first_line(text: str) -> tuple[str, str]:
    first, separator, rest = text.partition("\n")
    return first, rest if separator else ""


def _prefix_notes(
    text: str,
    source_number: int,
) -> list[tuple[str, str, str]]:
    if not text.strip():
        return []

    if source_number in {2, 25}:
        first, rest = _split_first_line(text)
        first_label = {
            2: "难句类型",
            25: "补充",
        }[source_number]
        notes = [(first_label, first, first)]
        if rest.strip():
            notes.append(("译文", rest, rest))
        return notes

    if source_number == 45:
        lines = text.splitlines()
        translation_start = next(
            (
                index
                for index, line in enumerate(lines)
                if line.startswith("这其中的一个新颖思想")
            ),
            None,
        )
        if translation_start is None or translation_start == 0:
            raise ValueError("source sentence 45 translation boundary was not found")
        supplement = "\n".join(lines[:translation_start])
        translation = "\n".join(lines[translation_start:])
        return [
            ("补充", supplement, supplement),
            ("译文", translation, translation),
        ]

    if source_number == 5:
        lines = text.splitlines()
        if len(lines) < 4:
            raise ValueError("source sentence 5 annotation layout changed")
        type_text = lines[0]
        translation_end = next(
            (
                index
                for index, line in enumerate(lines[1:], 1)
                if "每一个毛孔都充满了道德" in line
            ),
            None,
        )
        if translation_end is None or translation_end + 1 >= len(lines):
            raise ValueError("source sentence 5 translation boundary was not found")
        translation = "\n".join(lines[1 : translation_end + 1])
        explanation = "\n".join(lines[translation_end + 1 :])
        return [
            ("难句类型", type_text, type_text),
            ("译文", translation, translation),
            ("解释", explanation, explanation),
        ]

    return [("译文", text, text)]


def _parse_notes(
    annotation_text: str,
    source_number: int,
) -> tuple[list[dict[str, str]], int]:
    logical = _logical_note_text(annotation_text)
    if not logical:
        raise ValueError(f"source sentence {source_number} has no annotations")

    drafts: list[tuple[str, str, str]] = []
    remaining = logical
    difficulty = DIFFICULTY_MARKER.match(remaining)
    if difficulty:
        marker_text = difficulty.group(0)
        drafts.append(("难度", marker_text, marker_text))
        remaining = remaining[difficulty.end() :].lstrip("\n")

    headings = list(NOTE_HEADING.finditer(remaining))
    prefix_end = headings[0].start() if headings else len(remaining)
    prefix = remaining[:prefix_end].rstrip("\n")
    drafts.extend(_prefix_notes(prefix, source_number))

    for index, heading in enumerate(headings):
        section_end = (
            headings[index + 1].start()
            if index + 1 < len(headings)
            else len(remaining)
        )
        raw_label = (
            heading.group("named")
            or heading.group("point")
            or heading.group("lower")
            or heading.group("number")
        )
        label = NOTE_LABEL_NORMALIZATION.get(raw_label, raw_label)
        if heading.group("lower"):
            label = label.upper()
        body = remaining[heading.end() : section_end].rstrip("\n")
        source = remaining[heading.start() : section_end].rstrip("\n")
        drafts.append((label, body, source))

    notes: list[dict[str, str]] = []
    covered_sources: list[str] = []
    for label, body, source in drafts:
        clean_label = _clean_note_text(label)
        clean_body = _clean_note_text(body)
        if not clean_label or not clean_body:
            raise ValueError(
                f"source sentence {source_number} produced an empty note: "
                f"{label!r} / {body!r}"
            )
        notes.append({"label": clean_label, "text": clean_body})
        covered_sources.append(source)

    if _audit_key(logical) != _audit_key("".join(covered_sources)):
        raise ValueError(
            f"source sentence {source_number} annotation coverage audit failed"
        )
    return notes, len(_audit_key(logical))


_PUNCTUATION_TRANSLATION = str.maketrans(
    {
        "，": ",",
        "；": ";",
        "：": ":",
        "？": "?",
        "（": "(",
        "）": ")",
        "―": '"',
        "‖": '"',
        "\u00a0": " ",
        "\u00ad": "",
    }
)


# These repairs cover embedded-text ordering/spacing defects and a small set
# of unmistakable print typos whose intended forms are confirmed by the
# surrounding explanation or the repeated ``意群训练`` sentence in the PDF.
_LAYOUT_REPAIRS: dict[int, tuple[tuple[str, str], ...]] = {
    2: (("might give away abruptly", "might give way abruptly"),),
    8: (
        (
            "transmission of-and so was crucial in sustaining-the Black",
            "transmission of—and so was crucial in sustaining—the Black",
        ),
    ),
    10: (("competition, \"", "competition,\""),),
    14: (("psycho neural", "psychoneural"),),
    28: (("t he", "the"),),
    30: (("Perhaps the fact many", "Perhaps the fact that many"),),
    34: (("water within it the hydrologic cycle", "water within it with the hydrologic cycle"),),
    48: (("life-as-spectacle, \"", "life-as-spectacle,\""),),
    53: (("take over it a steadily", "take over in a steadily"),),
    55: (
        ("those of who hoped", "those of us who hoped"),
        ("Prou st’s", "Proust’s"),
    ),
    56: (("conquered people-a charter", "conquered people—a charter"),),
    57: (("Mrna’S", "mRNA’s"),),
    62: (("Family Bronte’s", "Emily Bronte’s"),),
    63: (("does (15) encourage", "does encourage"),),
    65: (("uniform is topic composition", "uniform isotopic composition"),),
    71: (
        ("United Stated", "United States"),
        ("basic factor \"", "basic factor\""),
    ),
    78: (("materia l", "material"),),
    79: (("t oward", "toward"),),
    80: (("(on the Mars)", "(on Mars)"),),
    82: (("rock interface are crossed", "rock interfaces are crossed"),),
    86: (("ha zards", "hazards"),),
    96: (("c laim", "claim"),),
    100: (("what manufactures and servicing", "what manufacturers and servicing"),),
    101: (("eighteen-century", "eighteenth-century"),),
    102: (("were caused by their.", "were caused by them."),),
    103: (
        (
            "the nature of human knowledge they believe, are",
            "the nature of human knowledge, they believe, are",
        ),
    ),
    104: (("philosophy, \"", "philosophy,\""),),
    107: (("1011 neurons", "10^11 neurons"),),
    109: (
        ("scientific-a valid", "scientific—a valid"),
        ("can perform-the definition", "can perform—the definition"),
    ),
    110: (
        (
            "women scholars-only now entering the academic profession in "
            "substantial numbers-will",
            "women scholars—only now entering the academic profession in "
            "substantial numbers—will",
        ),
    ),
    117: (("the alloys metal component", "the alloy’s metal component"),),
    121: (
        ("Waizer’s", "Walzer’s"),
        ("capitalism-namely", "capitalism—namely"),
    ),
    127: (("Valdez immediate source", "Valdez’s immediate source"),),
    130: (("S upreme", "Supreme"),),
    132: (
        ("s ome", "some"),
        ("refused to find, any", "refused to find any"),
        (
            "nonracial discriminations. Sexual discrimination in particular, are",
            "nonracial discriminations, sexual discrimination in particular, are",
        ),
    ),
}


def _clean_sentence(text: str, source_number: int) -> str:
    sentence = text.translate(_PUNCTUATION_TRANSLATION)
    sentence = re.sub(r"\s+", " ", sentence).strip()
    sentence = re.sub(r"\s*-\s*", "-", sentence)
    sentence = re.sub(r"\s*[–—]\s*", "—", sentence)
    sentence = re.sub(r"—{2,}", "—", sentence)
    sentence = re.sub(r"\s+([,.;:?!])", r"\1", sentence)
    sentence = re.sub(r"([,;:?!])(?=[A-Za-z\"(])", r"\1 ", sentence)
    sentence = re.sub(r"(?<=[A-Za-z0-9’])\(", " (", sentence)
    sentence = re.sub(r"\(\s+", "(", sentence)
    sentence = re.sub(r"\s+\)", ")", sentence)
    sentence = re.sub(r"\)(?=[A-Za-z0-9])", ") ", sentence)
    for before, after in _LAYOUT_REPAIRS.get(source_number, ()):
        sentence = sentence.replace(before, after)
    return re.sub(r"\s+", " ", sentence).strip()


def extract(pdf_path: Path) -> dict[str, object]:
    pdf_path = pdf_path.resolve()
    file_sha256 = _sha256(pdf_path)
    if file_sha256 != EXPECTED_FILE_SHA256:
        raise ValueError(
            "unexpected source PDF SHA-256: "
            f"expected {EXPECTED_FILE_SHA256}, got {file_sha256}"
        )

    with fitz.open(pdf_path) as document:
        if document.page_count != EXPECTED_PAGE_COUNT:
            raise ValueError(
                f"expected {EXPECTED_PAGE_COUNT} pages, got {document.page_count}"
            )
        document_text, pages = _read_pages(document)

    unicode_text = _read_unicode_pages(pdf_path)
    unicode_markers = _find_markers(unicode_text)
    unicode_blocks: dict[int, str] = {}
    for index, marker in enumerate(unicode_markers):
        next_start = (
            unicode_markers[index + 1].start
            if index + 1 < len(unicode_markers)
            else len(unicode_text)
        )
        unicode_blocks[marker.source_number] = unicode_text[
            marker.content_start : next_start
        ]

    markers = _find_markers(document_text)
    sentences: list[dict[str, object]] = []
    total_annotation_characters = 0
    for index, marker in enumerate(markers):
        next_start = (
            markers[index + 1].start
            if index + 1 < len(markers)
            else len(document_text)
        )
        block = document_text[marker.content_start : next_start]
        raw_sentence = _raw_sentence(block, marker.source_number)
        text = _clean_sentence(raw_sentence, marker.source_number)
        sentence_end = marker.content_start + len(raw_sentence)
        notes, annotation_characters = _parse_notes(
            _annotation_text(
                unicode_blocks[marker.source_number],
                marker.source_number,
            ),
            marker.source_number,
        )
        total_annotation_characters += annotation_characters
        sentences.append(
            {
                "id": index + 1,
                "source_number": marker.source_number,
                "text": text,
                "source_pages": _source_pages(
                    pages,
                    start=marker.start,
                    end=sentence_end,
                ),
                "notes": notes,
            }
        )

    note_counts = [len(sentence["notes"]) for sentence in sentences]
    total_notes = sum(note_counts)

    return {
        "schema": SCHEMA,
        "version": SCHEMA_VERSION,
        "source": {
            "title": SOURCE_TITLE,
            "file_name": pdf_path.name,
            "file_sha256": file_sha256,
            "page_count": EXPECTED_PAGE_COUNT,
            "missing_source_numbers": sorted(MISSING_SOURCE_NUMBERS),
            "notes_extraction": (
                "Embedded PDF Unicode text layer with rendered-page review"
            ),
            "notes_review": (
                "Windows Simplified Chinese OCR and 4x rendered-page spot checks"
            ),
            "notes_audit": {
                "coverage_percent": 100,
                "source_characters": total_annotation_characters,
                "note_count": total_notes,
                "sentences_with_notes": len(note_counts),
                "minimum_notes_per_sentence": min(note_counts),
                "maximum_notes_per_sentence": max(note_counts),
            },
        },
        "count": len(sentences),
        "sentences": sentences,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract numbered English sentences from 杨鹏阅读长难句 PDF."
    )
    parser.add_argument("pdf", type=Path, help="source PDF path")
    parser.add_argument("output", type=Path, help="output JSON path")
    args = parser.parse_args()

    payload = extract(args.pdf)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Wrote {payload['count']} sentences to {args.output} "
        f"from {payload['source']['page_count']} pages."
    )
    audit = payload["source"]["notes_audit"]
    print(
        "Annotation audit: "
        f"{audit['coverage_percent']}% coverage, "
        f"{audit['source_characters']} source characters, "
        f"{audit['note_count']} notes, "
        f"{audit['minimum_notes_per_sentence']}.."
        f"{audit['maximum_notes_per_sentence']} notes per sentence."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
