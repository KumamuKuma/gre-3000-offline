import re
from dataclasses import dataclass

from .types import RawWordRow


CJK = re.compile(r"[\u3400-\u9fff]")
SPACE = re.compile(r"[ \t]+")


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


def clean(text: str) -> str:
    return "\n".join(
        SPACE.sub(" ", line).strip() for line in text.splitlines() if line.strip()
    )


def split_bilingual(text: str) -> tuple[str, str]:
    value = clean(text).replace("\n", " ")
    match = CJK.search(value)
    if not match:
        return value.strip(), ""
    return value[: match.start()].strip(), value[match.start() :].strip()


def normalize_row(row: RawWordRow) -> WordDraft:
    headword, phonetic, raw_definition, synonyms, raw_example = row.columns
    definition_en, definition_zh = split_bilingual(raw_definition)
    example_en, example_zh = split_bilingual(raw_example)

    flags = set(row.flags)
    if not headword.strip():
        flags.add("missing_headword")
    if not phonetic.strip():
        flags.add("missing_phonetic")
    if not definition_en or not definition_zh:
        flags.add("incomplete_definition")
    if raw_example and (not example_en or not example_zh):
        flags.add("incomplete_example")

    return WordDraft(
        source_order=row.source_order,
        source_section=row.source_section,
        source_page=row.source_page,
        headword=clean(headword).replace("\n", " "),
        phonetic=clean(phonetic).replace("\n", ""),
        definition_en=definition_en,
        definition_zh=definition_zh,
        synonyms=clean(synonyms).replace("\n", " "),
        example_en=example_en,
        example_zh=example_zh,
        raw_definition=clean(raw_definition),
        raw_example=clean(raw_example),
        quality_flags=tuple(sorted(flags)),
    )
