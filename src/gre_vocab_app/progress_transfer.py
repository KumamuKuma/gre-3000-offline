from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping


PROGRESS_SCHEMA = "gre-vocab-progress"
PROGRESS_VERSION = 1
_SYNC_SETTING_KEYS = (
    "study_list",
    "study_filter",
    "study_mode",
    "auto_speak",
    "quiz_wrong_star_up",
    "quiz_correct_star_down",
)


class ProgressFormatError(ValueError):
    """Raised when a progress transfer document is unsafe to import."""


@dataclass(frozen=True, slots=True)
class ImportSummary:
    star_count: int
    list_count: int


def export_progress(user: Any, content: Any) -> dict[str, Any]:
    word_ids = tuple(int(word_id) for word_id in content.ids_in_source_order())
    stars = {
        str(word_id): rating
        for word_id in word_ids
        if (rating := int(user.star_rating(word_id))) > 0
    }
    lists: dict[str, dict[str, int | None]] = {}
    for source_list in content.source_lists():
        key = str(source_list.key)
        queue = user.load_queue(f"source:list:{key}:all")
        current_word_id = (
            int(queue.word_ids[queue.position]) if queue.word_ids else None
        )
        lists[key] = {
            "completed_count": int(user.list_completion_count(key)),
            "current_word_id": current_word_id,
        }
    settings = {
        key: value
        for key in _SYNC_SETTING_KEYS
        if (value := user.load_setting(key)) is not None
    }
    return {
        "schema": PROGRESS_SCHEMA,
        "version": PROGRESS_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "stars": stars,
        "lists": lists,
        "settings": settings,
    }


def _require_mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ProgressFormatError(f"{label} 必须是对象。")
    if any(not isinstance(key, str) for key in value):
        raise ProgressFormatError(f"{label} 的键必须是文本。")
    return value


def import_progress(user: Any, content: Any, payload: object) -> ImportSummary:
    document = _require_mapping(payload, "进度文件")
    if document.get("schema") != PROGRESS_SCHEMA:
        raise ProgressFormatError("这不是 GRE 3000 学习进度文件。")
    if document.get("version") != PROGRESS_VERSION:
        raise ProgressFormatError("进度文件版本不受支持。")

    valid_word_ids = {
        int(word_id) for word_id in content.ids_in_source_order()
    }
    source_lists = {str(item.key): item for item in content.source_lists()}

    raw_stars = _require_mapping(document.get("stars"), "stars")
    stars: dict[int, int] = {}
    for raw_word_id, raw_rating in raw_stars.items():
        try:
            word_id = int(raw_word_id)
        except ValueError as error:
            raise ProgressFormatError("stars 包含无效的单词编号。") from error
        if str(word_id) != raw_word_id or word_id not in valid_word_ids:
            raise ProgressFormatError("stars 引用了不存在的单词。")
        if type(raw_rating) is not int or not 1 <= raw_rating <= 3:
            raise ProgressFormatError("星级必须是 1、2 或 3。")
        stars[word_id] = raw_rating

    raw_lists = _require_mapping(document.get("lists"), "lists")
    parsed_lists: dict[str, tuple[int, int | None]] = {}
    for key, raw_state in raw_lists.items():
        if key not in source_lists:
            raise ProgressFormatError(f"进度文件包含未知 List：{key}")
        state = _require_mapping(raw_state, f"lists.{key}")
        completed = state.get("completed_count")
        current_word_id = state.get("current_word_id")
        if type(completed) is not int or completed < 0:
            raise ProgressFormatError("List 已背次数必须是非负整数。")
        list_ids = tuple(int(value) for value in content.ids_for_section(key))
        if current_word_id is not None and (
            type(current_word_id) is not int or current_word_id not in list_ids
        ):
            raise ProgressFormatError(f"{key} 的当前位置不属于该 List。")
        parsed_lists[key] = (completed, current_word_id)

    raw_settings = _require_mapping(document.get("settings", {}), "settings")
    settings: dict[str, str] = {}
    for key, value in raw_settings.items():
        if key not in _SYNC_SETTING_KEYS or not isinstance(value, str):
            raise ProgressFormatError("settings 包含不受支持的设置。")
        settings[key] = value
    if "study_mode" in settings and settings["study_mode"] not in {
        "reading",
        "brief",
        "recall",
        "quiz",
    }:
        raise ProgressFormatError("默认学习模式无效。")
    boolean_settings = {
        "auto_speak": "自动朗读",
        "quiz_wrong_star_up": "答错自动加星",
        "quiz_correct_star_down": "答对自动减星",
    }
    for key, label in boolean_settings.items():
        if key in settings and settings[key] not in {"0", "1"}:
            raise ProgressFormatError(f"{label}设置无效。")
    if "study_list" in settings and settings["study_list"] not in source_lists:
        raise ProgressFormatError("默认 List 无效。")
    if "study_filter" in settings and settings["study_filter"] not in {
        "all",
        "star:0",
        "star:1",
        "star:2",
        "star:3",
    }:
        raise ProgressFormatError("星级筛选设置无效。")

    for word_id in valid_word_ids:
        desired = stars.get(word_id, 0)
        if int(user.star_rating(word_id)) != desired:
            user.set_star_rating(word_id, desired)
    for key in source_lists:
        completed, current_word_id = parsed_lists.get(key, (0, None))
        user.set_list_completion_count(key, completed)
        word_ids = tuple(int(value) for value in content.ids_for_section(key))
        position = (
            word_ids.index(current_word_id) if current_word_id is not None else 0
        )
        user.save_queue(
            f"source:list:{key}:all",
            word_ids,
            position=position,
            seed=0,
        )
    for key, value in settings.items():
        user.save_setting(key, value)

    return ImportSummary(star_count=len(stars), list_count=len(parsed_lists))
