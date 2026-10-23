"""Portable word-note keys shared by every learning surface."""

import unicodedata

MAX_NOTE_LENGTH = 4000


def note_key(word: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", word).replace("’", "'").split()).lower()


def validate_notes(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError("备注必须是对象。")
    notes = {}
    for key, text in value.items():
        if (
            not isinstance(key, str)
            or not key
            or len(key) > 500
            or note_key(key) != key
            or not isinstance(text, str)
            or len(text) > MAX_NOTE_LENGTH
        ):
            raise ValueError("备注包含无效的单词或内容（每词最多 4000 字）。")
        if text:
            notes[key] = text
    return notes
