from __future__ import annotations

import random

import pytest

from gre_vocab_app.db.user import UserRepository
from gre_vocab_app.domain import SourceList, WordEntry
from gre_vocab_app.progress_transfer import (
    ProgressFormatError,
    export_progress,
    import_progress,
)
from gre_vocab_app.services.study import StudySession


class FakeContent:
    def __init__(self):
        self._ids = {"list1": (1, 2, 3), "list2": (4, 5)}
        self._words = {
            word_id: WordEntry(
                id=word_id,
                source_order=word_id,
                source_section="list1" if word_id <= 3 else "list2",
                source_page=1,
                headword=f"word{word_id}",
                phonetic="[wɜːd]",
                definition_en=f"n. definition {word_id}",
                definition_zh=f"释义 {word_id}",
                synonyms="",
                example_en="",
                example_zh="",
                raw_definition="",
                raw_example="",
            )
            for word_id in self.ids_in_source_order()
        }

    def ids_in_source_order(self):
        return (1, 2, 3, 4, 5)

    def ids_for_section(self, key):
        return self._ids[key]

    def source_lists(self):
        return (
            SourceList("list1", "List 1", 3, 1, 3),
            SourceList("list2", "List 2", 2, 4, 5),
        )

    def get(self, word_id):
        return self._words[word_id]

    def in_machine7(self, word_id):
        return word_id in {1, 4}


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
    source.save_setting("study_lists", "list1,list2")
    source.save_setting("study_star_lists", "list1,list2")
    source.save_setting("study_filter", "stars:1,3")
    source.save_setting("study_star_current_word_id", "4")
    source.save_setting("study_machine7_current_word_id", "4")
    source.save_setting("study_mode", "recall")
    source.save_setting("study_machine7_only", "1")
    source.save_setting("word_list_machine7_only", "1")
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
    assert target.load_setting("study_lists") == "list1,list2"
    assert target.load_setting("study_star_lists") == "list1,list2"
    assert target.load_setting("study_filter") == "stars:1,3"
    assert target.load_setting("study_star_current_word_id") == "4"
    assert target.load_setting("study_machine7_current_word_id") == "4"
    assert target.load_setting("study_machine7_only") == "1"
    assert target.load_setting("word_list_machine7_only") == "1"
    assert target.load_setting("quiz_wrong_star_up") == "1"
    assert target.load_setting("quiz_correct_star_down") == "1"
    assert target.load_setting("voice_name") is None


def test_imported_filtered_anchors_replace_stale_local_queues(tmp_path):
    content_repository = FakeContent()
    source = UserRepository(tmp_path / "source-filtered.db")
    target_path = tmp_path / "target-filtered.db"
    target = UserRepository(target_path)
    try:
        for word_id in (1, 4):
            source.set_star_rating(word_id, 2)
            target.set_star_rating(word_id, 2)
        source.save_setting("study_star_current_word_id", "4")
        source.save_setting("study_machine7_current_word_id", "4")
        payload = export_progress(source, content_repository)

        target.save_queue(
            "source:lists:all:machine7",
            (1, 4),
            position=0,
            seed=0,
        )
        target.save_queue(
            "source:lists:all:star:2",
            (1, 4),
            position=0,
            seed=0,
        )

        import_progress(target, content_repository, payload)
        assert target.close()
        target = UserRepository(target_path)
        assert not target.load_queue("source:lists:all:machine7").word_ids
        assert not target.load_queue("source:lists:all:star:2").word_ids

        machine_session = StudySession(
            content_repository,
            target,
            random.Random(1),
        )
        machine_snapshot = machine_session.start(
            source_sections=("list1", "list2"),
            machine7_only=True,
        )
        assert machine_snapshot.word.id == 4

        star_session = StudySession(
            content_repository,
            target,
            random.Random(2),
        )
        star_snapshot = star_session.start(
            source_sections=("list1", "list2"),
            star_rating=2,
        )
        assert star_snapshot.word.id == 4
    finally:
        assert source.close()
        assert target.close()


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
        ("study_lists", "list1,missing", "List 范围"),
        ("study_lists", "list1,list1", "List 范围"),
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


@pytest.mark.parametrize("value", ["stars:1,1", "stars:0,4", "stars:2", "stars:x,2"])
def test_progress_import_rejects_invalid_multi_star_filter(tmp_path, value):
    content_repository = FakeContent()
    user = UserRepository(tmp_path / "invalid-star-filter.db")
    payload = export_progress(user, content_repository)
    payload["settings"]["study_filter"] = value

    with pytest.raises(ProgressFormatError, match="星级筛选"):
        import_progress(user, content_repository, payload)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("study_machine7_only", "yes"),
        ("word_list_machine7_only", "2"),
    ],
)
def test_progress_import_rejects_invalid_machine7_boolean_settings(
    tmp_path, key, value
):
    content_repository = FakeContent()
    user = UserRepository(tmp_path / f"invalid-{key}.db")
    payload = export_progress(user, content_repository)
    payload["settings"][key] = value

    with pytest.raises(ProgressFormatError, match="机经 7.0"):
        import_progress(user, content_repository, payload)


@pytest.mark.parametrize("value", ["2", "999", "not-a-word"])
def test_progress_import_rejects_invalid_machine7_anchor(tmp_path, value):
    content_repository = FakeContent()
    user = UserRepository(tmp_path / "invalid-machine7-anchor.db")
    payload = export_progress(user, content_repository)
    payload["settings"]["study_machine7_current_word_id"] = value

    with pytest.raises(ProgressFormatError, match="机经 7.0 学习当前位置"):
        import_progress(user, content_repository, payload)
