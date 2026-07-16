from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TextSpan:
    x0: float
    y0: float
    x1: float
    y1: float
    text: str
    size: float


@dataclass(frozen=True, slots=True)
class RawWordRow:
    source_page: int
    source_order: int
    source_section: str
    columns: tuple[str, str, str, str, str]
    flags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ParserState:
    next_order: int
    section: str
