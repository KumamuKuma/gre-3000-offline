from dataclasses import dataclass
from enum import StrEnum


class StudyMode(StrEnum):
    READING = "reading"
    RECALL = "recall"


class BrowseOrder(StrEnum):
    SOURCE = "source"
    RANDOM = "random"


@dataclass(frozen=True, slots=True)
class WordEntry:
    id: int
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
    quality_flags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SessionSnapshot:
    word: WordEntry
    index: int
    total: int
    mode: StudyMode
    order: BrowseOrder
    answer_visible: bool
    favorite: bool
    at_start: bool
    at_end: bool
