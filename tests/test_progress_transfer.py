from __future__ import annotations

import pytest

from gre_vocab_app.db.user import UserRepository
from gre_vocab_app.domain import SourceList
from gre_vocab_app.progress_transfer import (
    ProgressFormatError,
    export_progress,
    import_progress,
)


class FakeContent:
    def __init__(self):
        self._ids = {"list1": (1, 2, 3), "list2": (4, 5)}

    def ids_in_source_order(self):
        return (1, 2, 3, 4, 5)

    def ids_for_section(self, key):
        return self._ids[key]

    def source_lists(self):
        return (
            SourceList("list1", "List 1", 3, 1, 3),
            SourceList("list2", "List 2", 2, 4, 5),
        )


def test_progress_round_trip_preserves_stars_lists_positions_and_settings(
    tmp_path
):
    content_repository = FakeContent()
    list_key = content_repository.source_lists()[0].key
    word_ids = content_repository.ids_for_section(list_key)
    source = UserRepository(tmp_path / "source.db")
    source.set_star_rating(word_ids[0], 3)
    source.set_list_completion_count(list_key, 4)
    source.save_queue(
        f"source:list:{list_key}:all",
        word_ids,
        position=2,
        seed=0,
    )
    source.save_setting("study_list", list_key)
    source.save_setting("study_star_lists", "list1,list2")
    source.save_setting("study_star_current_word_id", "4")
    source.save_setting("study_mode", "recall")
    source.save_setting("quiz_wrong_star_up", "1")
    source.save_setting("quiz_correct_star_down", "1")
    source.save_setting("voice_name", "device-only")

    payload = export_progress(source, content_repository)
    target = UserRepository(tmp_path / "target.db")
    summary = import_progress(target, content_repository, payload)

    assert summary.star_count == 1
    assert target.star_rating(word_ids[0]) == 3
    assert target.list_completion_count(list_key) == 4
    assert target.load_queue(f"source:list:{list_key}:all").position == 2
    assert target.load_setting("study_mode") == "recall"
    assert target.load_setting("study_star_lists") == "list1,list2"
    assert target.load_setting("study_star_current_word_id") == "4"
    assert target.load_setting("quiz_wrong_star_up") == "1"
    assert target.load_setting("quiz_correct_star_down") == "1"
    assert target.load_setting("voice_name") is None


def test_progress_import_validates_everything_before_mutating(
    tmp_path
):
    content_repository = FakeContent()
    user = UserRepository(tmp_path / "user.db")
    word_id = content_repository.ids_in_source_order()[0]
    user.set_star_rating(word_id, 2)
    payload = export_progress(user, content_repository)
    payload["lists"]["not-a-list"] = {
        "completed_count": 1,
        "current_word_id": word_id,
    }

    with pytest.raises(ProgressFormatError, match="未知 List"):
        import_progress(user, content_repository, payload)

    assert user.star_rating(word_id) == 2


@pytest.mark.parametrize(
    ("key", "value", "message"),
    [
        ("study_star_lists", "list1,missing", "List 范围"),
        ("study_star_lists", "list1,list1", "List 范围"),
        ("study_star_current_word_id", "999", "当前位置"),
        ("study_star_current_word_id", "not-a-word", "当前位置"),
    ],
)
def test_progress_import_rejects_invalid_multi_list_scope_settings(
    tmp_path, key, value, message
):
    content_repository = FakeContent()
    user = UserRepository(tmp_path / f"{key}-{value}.db")
    payload = export_progress(user, content_repository)
    payload["settings"][key] = value

    with pytest.raises(ProgressFormatError, match=message):
        import_progress(user, content_repository, payload)
