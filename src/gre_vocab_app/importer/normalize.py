import re
import unicodedata
from dataclasses import dataclass, replace
from typing import Iterable

from .types import RawWordRow


CJK = re.compile(r"[\u3400-\u9fff]")
HORIZONTAL_SPACE = re.compile(r"[^\S\r\n]+")
PHONETIC = re.compile(r"(?:\[[^\[\]\r\n]+\]|/[^/\r\n]+/)")

VALIDATION_FLAGS = frozenset(
    {
        "missing_headword",
        "missing_phonetic",
        "invalid_phonetic",
        "incomplete_definition",
        "incomplete_example",
        "definition_en_contains_cjk",
        "example_en_contains_cjk",
    }
)


@dataclass(frozen=True, slots=True)
class WordDraft:
    source_order: int
    source_section: str
    source_page: int
    headword: str
    phonetic: str
    definition_en: str
    definition_zh: str
    synonyms: str
    example_en: str
    example_zh: str
    raw_definition: str
    raw_example: str
    quality_flags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DewrapEvent:
    field: str
    kind: str
    left: str
    right: str


@dataclass(frozen=True, slots=True)
class _ScriptPiece:
    script: str | None
    text: str
    line_index: int


def clean(text: str) -> str:
    return "\n".join(
        HORIZONTAL_SPACE.sub(" ", line).strip()
        for line in text.splitlines()
        if line.strip()
    )


def _clean_inline(text: str) -> str:
    return HORIZONTAL_SPACE.sub(" ", text).strip()


def _is_latin_letter(character: str) -> bool:
    return bool(character) and unicodedata.category(character).startswith(
        "L"
    ) and "LATIN" in unicodedata.name(character, "")


def _strong_script(character: str) -> str | None:
    if CJK.fullmatch(character):
        return "zh"
    if _is_latin_letter(character):
        return "en"
    return None


def _script_segments(line: str, line_index: int) -> list[_ScriptPiece]:
    scripts = [_strong_script(character) for character in line]
    previous: list[str | None] = []
    seen: str | None = None
    for script in scripts:
        if script is not None:
            seen = script
        previous.append(seen)
    following: list[str | None] = [None] * len(line)
    seen = None
    for index in range(len(line) - 1, -1, -1):
        if scripts[index] is not None:
            seen = scripts[index]
        following[index] = seen

    opening_punctuation = frozenset("([{（《〈【“‘")
    assigned = list(scripts)
    index = 0
    while index < len(line):
        if scripts[index] is not None:
            index += 1
            continue
        start = index
        while index < len(line) and scripts[index] is None:
            index += 1
        end = index
        before = previous[start]
        after = following[end - 1]
        neutral_run = line[start:end]
        if before is None:
            chosen = after
        elif after is None or before == after:
            chosen = before
        elif neutral_run.lstrip()[:1] in opening_punctuation:
            chosen = after
        else:
            chosen = before
        assigned[start:end] = [chosen] * (end - start)

    pieces: list[_ScriptPiece] = []
    for character, script in zip(line, assigned):
        if pieces and pieces[-1].script == script:
            previous_piece = pieces[-1]
            pieces[-1] = _ScriptPiece(
                script,
                previous_piece.text + character,
                line_index,
            )
        else:
            pieces.append(_ScriptPiece(script, character, line_index))
    return pieces


def _resolve_neutral_pieces(pieces: list[_ScriptPiece]) -> list[_ScriptPiece]:
    result: list[_ScriptPiece] = []
    for index, piece in enumerate(pieces):
        if piece.script is not None:
            result.append(piece)
            continue
        before = next(
            (item.script for item in reversed(pieces[:index]) if item.script),
            None,
        )
        after = next(
            (item.script for item in pieces[index + 1 :] if item.script),
            None,
        )
        result.append(_ScriptPiece(after or before or "en", piece.text, piece.line_index))
    return result


def _boundary_join(
    value: str,
    left_raw: str,
    right_raw: str,
    right_value: str,
    *,
    field: str,
    events: list[DewrapEvent],
    record_event: bool,
) -> str:
    left_trimmed = left_raw.rstrip()
    right_trimmed = right_raw.lstrip()
    has_boundary_space = bool(
        left_raw[-1:].isspace() or right_raw[:1].isspace()
    )
    if (
        record_event
        and left_trimmed
        and right_trimmed
        and _is_latin_letter(left_trimmed[-1])
        and _is_latin_letter(right_trimmed[0])
    ):
        events.append(
            DewrapEvent(
                field=field,
                kind="normal_space" if has_boundary_space else "hard_join",
                left=left_trimmed,
                right=right_trimmed,
            )
        )
    separator = " " if has_boundary_space else ""
    return value + separator + right_value


def _join_raw_lines(
    lines: Iterable[str], field: str, events: list[DewrapEvent]
) -> str:
    usable = [line for line in lines if line.strip()]
    if not usable:
        return ""
    value = usable[0].strip()
    previous_raw = usable[0]
    for raw in usable[1:]:
        value = _boundary_join(
            value,
            previous_raw,
            raw,
            raw.strip(),
            field=field,
            events=events,
            record_event=True,
        )
        previous_raw = raw
    return _clean_inline(value)


def _split_definition(
    text: str, events: list[DewrapEvent]
) -> tuple[str, str]:
    lines = [line for line in text.splitlines() if line.strip()]
    pieces = _resolve_neutral_pieces(
        [
            piece
            for line_index, line in enumerate(lines)
            for piece in _script_segments(line, line_index)
            if piece.text
        ]
    )

    english = ""
    previous_english: tuple[int, _ScriptPiece] | None = None
    chinese_parts: list[str] = []
    for piece_index, piece in enumerate(pieces):
        rendered = piece.text.strip()
        if not rendered:
            continue
        if piece.script == "zh":
            chinese_parts.append(rendered)
            continue
        if not english:
            english = rendered
        else:
            assert previous_english is not None
            previous_index, previous_piece = previous_english
            consecutive = (
                piece_index == previous_index + 1
                and piece.line_index == previous_piece.line_index + 1
            )
            if consecutive:
                english = _boundary_join(
                    english,
                    previous_piece.text,
                    piece.text,
                    rendered,
                    field="definition",
                    events=events,
                    record_event=True,
                )
            else:
                english += " " + rendered
        previous_english = (piece_index, piece)
    return _clean_inline(english), _clean_inline("".join(chinese_parts))


def _line_script(line: str) -> str | None:
    if CJK.search(line):
        return "zh"
    if any(_is_latin_letter(character) for character in line):
        return "en"
    return None


def _join_chinese_lines(
    lines: Iterable[str], field: str, events: list[DewrapEvent]
) -> str:
    usable = [line for line in lines if line.strip()]
    if not usable:
        return ""
    value = usable[0].strip()
    previous_raw = usable[0]
    for raw in usable[1:]:
        left = previous_raw.rstrip()
        right = raw.lstrip()
        if (
            left
            and right
            and _is_latin_letter(left[-1])
            and _is_latin_letter(right[0])
        ):
            value = _boundary_join(
                value,
                previous_raw,
                raw,
                raw.strip(),
                field=field,
                events=events,
                record_event=True,
            )
        else:
            value += raw.strip()
        previous_raw = raw
    return _clean_inline(value)


def _split_example(text: str, events: list[DewrapEvent]) -> tuple[str, str]:
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return "", ""
    labels = [_line_script(line) for line in lines]
    for index, label in enumerate(labels):
        if label is not None:
            continue
        following = next((item for item in labels[index + 1 :] if item), None)
        previous = next((item for item in reversed(labels[:index]) if item), None)
        labels[index] = following or previous or "en"

    first_chinese = next(
        (index for index, label in enumerate(labels) if label == "zh"),
        len(lines),
    )
    english_lines = lines[:first_chinese]
    chinese_lines: list[str] = []

    if first_chinese < len(lines):
        transition = lines[first_chinese]
        transition_pieces = _resolve_neutral_pieces(
            _script_segments(transition, first_chinese)
        )
        first_zh_piece = next(
            (
                index
                for index, piece in enumerate(transition_pieces)
                if piece.script == "zh"
            ),
            0,
        )
        english_prefix = "".join(
            piece.text for piece in transition_pieces[:first_zh_piece]
        )
        if english_prefix.strip():
            english_lines.append(english_prefix)
        chinese_lines.append(
            "".join(piece.text for piece in transition_pieces[first_zh_piece:])
        )
        chinese_lines.extend(lines[first_chinese + 1 :])

    english = _join_raw_lines(english_lines, "example", events)
    chinese = _join_chinese_lines(chinese_lines, "example", events)
    return english, chinese


def split_bilingual(text: str) -> tuple[str, str]:
    return _split_definition(text, [])


def validation_flags(
    draft: WordDraft, *, extra_flags: Iterable[str] = ()
) -> tuple[str, ...]:
    flags = set(extra_flags)
    if not draft.headword.strip():
        flags.add("missing_headword")
    phonetic = draft.phonetic.strip()
    if not phonetic:
        flags.add("missing_phonetic")
    elif (
        phonetic.casefold() == draft.headword.strip().casefold()
        or PHONETIC.fullmatch(phonetic) is None
        or CJK.search(phonetic)
    ):
        flags.add("invalid_phonetic")
    if not draft.definition_en or not draft.definition_zh:
        flags.add("incomplete_definition")
    if draft.raw_example and (not draft.example_en or not draft.example_zh):
        flags.add("incomplete_example")
    if CJK.search(draft.definition_en):
        flags.add("definition_en_contains_cjk")
    if CJK.search(draft.example_en):
        flags.add("example_en_contains_cjk")
    return tuple(sorted(flags))


def normalize_row_with_diagnostics(
    row: RawWordRow,
) -> tuple[WordDraft, tuple[DewrapEvent, ...]]:
    headword, phonetic, raw_definition, synonyms, raw_example = row.columns
    events: list[DewrapEvent] = []
    definition_en, definition_zh = _split_definition(raw_definition, events)
    normalized_synonyms = _join_raw_lines(
        synonyms.splitlines(), "synonyms", events
    )
    example_en, example_zh = _split_example(raw_example, events)

    draft = WordDraft(
        source_order=row.source_order,
        source_section=row.source_section,
        source_page=row.source_page,
        headword=clean(headword).replace("\n", " "),
        phonetic=clean(phonetic).replace("\n", ""),
        definition_en=definition_en,
        definition_zh=definition_zh,
        synonyms=normalized_synonyms,
        example_en=example_en,
        example_zh=example_zh,
        raw_definition=clean(raw_definition),
        raw_example=clean(raw_example),
        quality_flags=(),
    )
    return (
        replace(draft, quality_flags=validation_flags(draft, extra_flags=row.flags)),
        tuple(events),
    )


def normalize_row(row: RawWordRow) -> WordDraft:
    return normalize_row_with_diagnostics(row)[0]
