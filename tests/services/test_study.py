import random

import pytest

from gre_vocab_app.db.user import QueueState, UserRepository
from gre_vocab_app.domain import (
    BrowseOrder,
    RelatedWord,
    RootFamily,
    SourceList,
    StudyMode,
    WordEntry,
)
from gre_vocab_app.services.study import StudySession


class FakeContent:
    def __init__(self, count: int = 10, *, duplicate_chinese: bool = False):
        split = max(1, count // 2)
        self.words = {
            word_id: WordEntry(
                id=word_id,
                source_order=word_id,
                source_section="list1" if word_id <= split else "list2",
                source_page=5,
                headword=f"word{word_id}",
                phonetic="[x]",
                definition_en=f"English definition {word_id}",
                definition_zh=(
                    "相同释义" if duplicate_chinese else f"中文释义{word_id}"
                ),
                synonyms="",
                example_en="",
                example_zh="",
                raw_definition=f"definition {word_id}",
                raw_example="",
            )
            for word_id in range(1, count + 1)
        }

    def ids_in_source_order(self):
        return tuple(self.words)

    def ids_for_section(self, key):
        ids = tuple(
            word.id for word in self.words.values() if word.source_section == key
        )
        if not ids:
            raise KeyError(key)
        return ids

    def source_list(self, key):
        ids = self.ids_for_section(key)
        return SourceList(key, "List 1" if key == "list1" else "List 2", len(ids), ids[0], ids[-1])

    def source_lists(self):
        result = []
        for key, label in (("list1", "List 1"), ("list2", "List 2")):
            try:
                ids = self.ids_for_section(key)
            except KeyError:
                continue
            result.append(SourceList(key, label, len(ids), ids[0], ids[-1]))
        return tuple(result)

    def get(self, word_id):
        return self.words[word_id]

    def root_families(self, word_id):
        if word_id != 1 or 2 not in self.words:
            return ()
        related = self.words[2]
        return (
            RootFamily(
                "word（同族）",
                (RelatedWord(2, related.headword, related.definition_zh),),
            ),
        )

    def lookalikes(self, word_id):
        if word_id != 1 or 3 not in self.words:
            return ()
        related = self.words[3]
        return (RelatedWord(3, related.headword, related.definition_zh),)

    def equivalents(self, word_id):
        if word_id != 1 or 4 not in self.words:
            return ()
        related = self.words[4]
        return (RelatedWord(4, related.headword, related.definition_zh),)

    def in_machine7(self, word_id):
        return word_id == 1


class FakeUser:
    def __init__(self):
        self.settings = {}
        self.queues = {}
        self.seen = []
        self.ratings = {}
        self.completions = {}

    def load_setting(self, key):
        return self.settings.get(key)

    def save_setting(self, key, value):
        self.settings[key] = value
        return True

    def load_queue(self, name):
        return self.queues.get(name)

    def save_queue(self, name, word_ids, *, position, seed):
        self.queues[name] = QueueState(tuple(word_ids), position, seed)
        return True

    def save_navigation(
        self,
        name,
        word_ids,
        *,
        position,
        seed,
        seen_word_id,
        event_id,
    ):
        del event_id
        self.save_queue(name, word_ids, position=position, seed=seed)
        self.seen.append(seen_word_id)
        return True

    def star_rating(self, word_id):
        return self.ratings.get(word_id, 0)

    def set_star_rating(self, word_id, value):
        self.ratings[word_id] = value
        return True

    def cycle_star_rating(self, word_id):
        value = (self.star_rating(word_id) + 1) % 4
        self.set_star_rating(word_id, value)
        return value

    def increment_list_completion(self, key):
        self.completions[key] = self.completions.get(key, 0) + 1
        return self.completions[key]

    def reset_position(self, name):
        state = self.queues[name]
        self.queues[name] = QueueState(state.word_ids, 0, state.seed)
        return True


@pytest.fixture
def user_repo():
    return FakeUser()


@pytest.fixture
def session(user_repo):
    return StudySession(FakeContent(), user_repo, random.Random(1234))


def start(session, **kwargs):
    return session.start(source_section="list1", **kwargs)


def test_all_modes_keep_word_and_only_navigation_resets_recall_answer(
    session, user_repo
):
    first = start(session)
    seen_after_start = list(user_repo.seen)
    assert session.set_mode(StudyMode.BRIEF).word.id == first.word.id
    session.set_mode(StudyMode.RECALL)
    session.toggle_answer()
    assert session.current().answer_visible
    assert session.set_mode("full").mode is StudyMode.READING
    session.set_mode(StudyMode.RECALL)
    assert session.current().answer_visible
    assert user_repo.seen == seen_after_start
    after = session.next()
    assert after.word.id != first.word.id
    assert not after.answer_visible


def test_selected_list_queue_preserves_order_and_restores_position(user_repo):
    content = FakeContent(10)
    session = StudySession(content, user_repo, random.Random(1))
    assert start(session).word.id == 1
    assert session.next().word.id == 2
    assert session.next().word.id == 3
    name = "source:list:list1:all"
    assert user_repo.load_queue(name) == QueueState((1, 2, 3, 4, 5), 2, 0)

    restored = StudySession(content, user_repo, random.Random(999))
    snapshot = start(restored, order=BrowseOrder.SOURCE)
    assert snapshot.word.id == 3
    assert snapshot.list_key == "list1"
    assert snapshot.list_label == "List 1"
    assert snapshot.total == 5
    assert user_repo.settings["study_list"] == "list1"


def test_user_can_choose_a_different_list(user_repo):
    session = StudySession(FakeContent(10), user_repo, random.Random(1))
    snapshot = session.start(source_section="list2")
    assert snapshot.word.id == 6
    assert snapshot.total == 5
    assert snapshot.list_label == "List 2"


def test_invalid_order_and_source_section_are_rejected(session):
    with pytest.raises(ValueError, match="source-order"):
        session.start("random", source_section="list1")
    with pytest.raises(ValueError, match="unknown source section"):
        session.start(source_section="missing")
    assert not hasattr(session, "reshuffle")


def test_boundaries_do_not_wrap_or_record_duplicate_navigation(session, user_repo):
    first = start(session)
    assert session.previous() == first
    for _ in range(20):
        last = session.next()
    assert last.at_end and last.index == 4
    assert len(user_repo.seen) == 5
    assert session.next() == last
    assert len(user_repo.seen) == 5


def test_jump_to_first_and_last_keeps_source_order_and_saves_position(session, user_repo):
    start(session)
    last = session.last()
    assert last.word.id == 5 and last.at_end and last.index == 4
    assert user_repo.load_queue("source:list:list1:all").position == 4

    first = session.first()
    assert first.word.id == 1 and first.at_start and first.index == 0
    assert user_repo.load_queue("source:list:list1:all").position == 0


def test_star_filter_is_list_scoped_source_order_and_restores_position(user_repo):
    user_repo.ratings.update({1: 3, 3: 3, 5: 3, 6: 3})
    content = FakeContent(10)
    session = StudySession(content, user_repo, random.Random(1))
    first = start(session, star_rating=3)
    assert first.word.id == 1 and first.total == 3
    assert session.next().word.id == 3
    assert session.next().word.id == 5
    name = "source:list:list1:star:3"
    assert user_repo.load_queue(name) == QueueState((1, 3, 5), 2, 0)

    restored = StudySession(content, user_repo, random.Random(2))
    assert start(restored, star_rating=3).word.id == 5


def test_star_filter_can_merge_multiple_or_all_lists_in_source_order(user_repo):
    user_repo.ratings.update({1: 2, 3: 2, 6: 2, 8: 2})
    content = FakeContent(10)
    session = StudySession(content, user_repo, random.Random(1))
    first = session.start(
        source_sections=("list2", "list1"),
        star_rating=2,
    )
    assert first.word.id == 1
    assert first.total == 4
    assert first.list_keys == ("list1", "list2")
    assert first.list_key is None
    assert first.list_label == "全部 List"
    assert not first.can_complete_round
    assert [session.next().word.id for _ in range(3)] == [3, 6, 8]
    name = "source:lists:all:star:2"
    assert user_repo.load_queue(name) == QueueState((1, 3, 6, 8), 3, 0)
    assert user_repo.settings["study_star_lists"] == "all"
    assert user_repo.settings["study_star_current_word_id"] == "8"

    restored = StudySession(content, user_repo, random.Random(2))
    assert restored.start(
        source_sections=("list1", "list2"),
        star_rating=2,
    ).word.id == 8

    user_repo.queues.clear()
    restored_from_synced_anchor = StudySession(
        content, user_repo, random.Random(3)
    )
    assert restored_from_synced_anchor.start(
        source_sections=("list1", "list2"),
        star_rating=2,
    ).word.id == 8


def test_multiple_lists_require_a_specific_star_filter(user_repo):
    session = StudySession(FakeContent(10), user_repo, random.Random(1))
    with pytest.raises(ValueError, match="require a star"):
        session.start(source_sections=("list1", "list2"))


def test_star_filter_membership_change_keeps_source_anchor(user_repo):
    user_repo.ratings.update({1: 2, 3: 2, 5: 2})
    session = StudySession(FakeContent(10), user_repo, random.Random(1))
    assert start(session, star_rating=2).word.id == 1
    assert session.next().word.id == 3
    assert session.set_star_rating(3).star_rating == 3
    restored = StudySession(FakeContent(10), user_repo, random.Random(2))
    snapshot = start(restored, star_rating=2)
    assert snapshot.word.id == 5 and snapshot.index == 1


@pytest.mark.parametrize("value", [-1, 4, True, 1.5, "3"])
def test_start_rejects_invalid_star_filter(value):
    session = StudySession(FakeContent(), FakeUser(), random.Random(1))
    with pytest.raises(ValueError, match="star rating"):
        session.start(source_section="list1", star_rating=value)


def test_empty_star_filter_fails_without_creating_queue_or_seen_event(user_repo):
    session = StudySession(FakeContent(8), user_repo, random.Random(1))
    with pytest.raises(ValueError, match="no words match"):
        start(session, star_rating=3)
    assert user_repo.queues == {}
    assert user_repo.seen == []


def test_quiz_has_four_unique_choices_and_locks_first_answer(session):
    first = start(session)
    quiz = session.set_mode(StudyMode.QUIZ)
    assert len(quiz.quiz_choices) == 4
    assert len(set(quiz.quiz_choices)) == 4
    assert quiz.quiz_choices[quiz.quiz_correct_index] == first.word.definition_zh
    answered = session.answer_quiz(quiz.quiz_correct_index)
    assert session.set_mode(StudyMode.QUIZ) == answered
    assert session.answer_quiz((quiz.quiz_correct_index + 1) % 4) == answered
    assert session.next().quiz_selected_index is None


def test_quiz_falls_back_to_english_when_chinese_choices_duplicate():
    content = FakeContent(10, duplicate_chinese=True)
    session = StudySession(content, FakeUser(), random.Random(8))
    quiz = session.start(source_section="list1")
    quiz = session.set_mode(StudyMode.QUIZ)
    assert len(set(quiz.quiz_choices)) == 4
    assert sum(choice.startswith("English") for choice in quiz.quiz_choices) == 3


def test_detail_snapshot_includes_star_and_word_relations(user_repo):
    content = FakeContent(10)
    user_repo.ratings[1] = 3
    session = StudySession(content, user_repo, random.Random(3))
    snapshot = session.detail_snapshot(content.get(1), StudyMode.QUIZ)
    assert snapshot.star_rating == 3
    assert snapshot.list_key is None
    assert snapshot.root_families[0].words[0].word_id == 2
    assert snapshot.lookalikes[0].word_id == 3
    assert snapshot.equivalents[0].word_id == 4
    assert snapshot.in_machine7 is True
    assert snapshot.quiz_choices[snapshot.quiz_correct_index] == "中文释义1"
    answered = session.answer_detail_quiz(snapshot, 0)
    assert session.answer_detail_quiz(answered, 1) == answered


def test_star_cycle_is_zero_through_three(session):
    assert start(session).star_rating == 0
    assert session.set_star_rating(2).star_rating == 2
    assert session.cycle_star_rating().star_rating == 3
    assert session.cycle_star_rating().star_rating == 0


def test_complete_round_counts_only_full_list_and_resets_position(user_repo):
    session = StudySession(FakeContent(10), user_repo, random.Random(1))
    start(session)
    with pytest.raises(RuntimeError, match="final word"):
        session.complete_round()
    while not session.current().at_end:
        session.next()
    assert session.current().can_complete_round
    assert session.complete_round() == 1
    assert user_repo.queues["source:list:list1:all"].position == 0

    filtered = StudySession(FakeContent(10), user_repo, random.Random(2))
    user_repo.ratings[1] = 1
    filtered.start(source_section="list1", star_rating=1)
    with pytest.raises(RuntimeError, match="unfiltered"):
        filtered.complete_round()


def test_navigation_keeps_memory_intent_and_retries_atomically(tmp_path):
    path = tmp_path / "user.db"
    with UserRepository(path) as user:
        session = StudySession(FakeContent(6), user, random.Random(1))
        first = session.start(source_section="list1")
        assert first.index == 0
        user.db.execute(
            """
            create trigger fail_seen before insert on word_progress
            when new.word_id = 2
            begin
              select raise(abort, 'synthetic navigation failure');
            end
            """
        )
        second = session.next()
        name = "source:list:list1:all"
        assert second.word.id == 2
        assert user.load_queue(name).position == 1
        assert user.has_pending_writes
        user.db.execute("drop trigger fail_seen")
        session.set_mode(StudyMode.RECALL)
        assert not user.has_pending_writes

    with UserRepository(path) as persisted:
        assert persisted.load_queue("source:list:list1:all").position == 1
