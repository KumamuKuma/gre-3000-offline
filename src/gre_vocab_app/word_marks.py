"""Decimal-text counters avoid SQLite, JavaScript and Python integer limits."""

import re

from gre_vocab_app.word_notes import note_key


def validate_marks(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError("累计标记必须是对象。")
    result = {}
    for key, count in value.items():
        if (
            not isinstance(key, str) or not key or len(key) > 500
            or note_key(key) != key or not isinstance(count, str)
            or re.fullmatch(r"0|[1-9][0-9]*", count) is None
        ):
            raise ValueError("累计标记必须使用非负十进制整数字符串。")
        if count != "0":
            result[key] = count
    return result


def adjust_count(count: str, delta: int) -> str:
    if type(delta) is not int or delta not in (-1, 1):
        raise ValueError("标记每次只能增加或减少一次。")
    validate_marks({"word": count})
    if delta == -1 and count == "0":
        return "0"
    digits = list(count)
    for index in range(len(digits) - 1, -1, -1):
        digit = ord(digits[index]) - 48 + delta
        if 0 <= digit <= 9:
            digits[index] = chr(48 + digit)
            break
        digits[index] = "0" if delta == 1 else "9"
    else:
        if delta == 1:
            digits.insert(0, "1")
    return "".join(digits).lstrip("0") or "0"
