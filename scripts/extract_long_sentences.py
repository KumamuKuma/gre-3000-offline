from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

import fitz


SCHEMA = "gre-long-sentences"
SCHEMA_VERSION = 1
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
    r"[（(][ \t]*(?:难度系数[ \t]*)?[0-9][0-9+\- \t]*"
    r"(?:，下同)?[ \t]*(?:[）)]|(?=\n))"
)


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

    markers = _find_markers(document_text)
    sentences: list[dict[str, object]] = []
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
            }
        )

    return {
        "schema": SCHEMA,
        "version": SCHEMA_VERSION,
        "source": {
            "title": SOURCE_TITLE,
            "file_name": pdf_path.name,
            "file_sha256": file_sha256,
            "page_count": EXPECTED_PAGE_COUNT,
            "missing_source_numbers": sorted(MISSING_SOURCE_NUMBERS),
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
