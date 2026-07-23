from dataclasses import dataclass
from enum import StrEnum


class StudyMode(StrEnum):
    READING = "reading"
    BRIEF = "brief"
    RECALL = "recall"
    QUIZ = "quiz"


class BrowseOrder(StrEnum):
    SOURCE = "source"


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
class SourceList:
    key: str
    label: str
    word_count: int
    first_order: int
    last_order: int


@dataclass(frozen=True, slots=True)
class RelatedWord:
    word_id: int
    headword: str
    definition: str


@dataclass(frozen=True, slots=True)
class RootFamily:
    root: str
    words: tuple[RelatedWord, ...]


@dataclass(frozen=True, slots=True)
class SessionSnapshot:
    word: WordEntry
    index: int
    total: int
    mode: StudyMode
    order: BrowseOrder
    answer_visible: bool
    at_start: bool
    at_end: bool
    star_rating: int = 0
    star_filter: int | None = None
    list_key: str | None = None
    list_keys: tuple[str, ...] = ()
    list_label: str = ""
    can_complete_round: bool = False
    root_families: tuple[RootFamily, ...] = ()
    lookalikes: tuple[RelatedWord, ...] = ()
    equivalents: tuple[RelatedWord, ...] = ()
    in_machine7: bool = False
    quiz_choices: tuple[str, ...] = ()
    quiz_correct_index: int | None = None
    quiz_selected_index: int | None = None
