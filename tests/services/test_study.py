import random

import pytest

from gre_vocab_app.db.user import QueueState, UserRepository
from gre_vocab_app.domain import BrowseOrder, StudyMode, WordEntry
from gre_vocab_app.services.study import StudySession


class FakeContent:
    def __init__(self, count: int = 10):
        self.words = {
            word_id: WordEntry(
                id=word_id,
                source_order=word_id,
                source_section="list1",
                source_page=5,
                headword=f"word{word_id}",
                phonetic="[x]",
                definition_en="adj. sample",
                definition_zh="示例",
                synonyms="",
                example_en="",
                example_zh="",
                raw_definition="adj. sample 示例",
                raw_example="",
            )
            for word_id in range(1, count + 1)
        }

    def ids_in_source_order(self):
        return tuple(self.words)

    def get(self, word_id):
        return self.words[word_id]


class FakeUser:
    def __init__(self):
        self.settings = {}
        self.queues = {}
        self.favorites = set()
        self.seen = []

    def load_setting(self, key):
        return self.settings.get(key)

    def save_setting(self, key, value):
        self.settings[key] = value

    def load_queue(self, name):
        return self.queues.get(name)

    def save_queue(self, name, word_ids, *, position, seed):
        self.queues[name] = QueueState(tuple(word_ids), position, seed)

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
        self.record_seen(seen_word_id)

    def is_favorite(self, word_id):
        return word_id in self.favorites

    def set_favorite(self, word_id, value):
        self.favorites.discard(word_id)
        if value:
            self.favorites.add(word_id)

    def record_seen(self, word_id):
        self.seen.append(word_id)


@pytest.fixture
def user_repo():
    return FakeUser()


@pytest.fixture
def session(user_repo):
    return StudySession(FakeContent(), user_repo, random.Random(1234))


def test_mode_switch_keeps_word_and_only_navigation_resets_answer(session, user_repo):
    first = session.start(BrowseOrder.SOURCE)
    seen_after_start = list(user_repo.seen)

    session.set_mode(StudyMode.RECALL)
    assert session.current().word.id == first.word.id
    assert session.current().answer_visible is False
    assert user_repo.seen == seen_after_start

    session.toggle_answer()
    assert session.current().answer_visible is True
    session.set_mode(StudyMode.READING)
    session.set_mode(StudyMode.RECALL)
    assert session.current().answer_visible is True
    assert user_repo.seen == seen_after_start

    after = session.next()
    assert after.word.id != first.word.id
    assert after.mode is StudyMode.RECALL
    assert after.answer_visible is False
    assert user_repo.settings["study_mode"] == "recall"


def test_random_queue_has_no_repeat_and_persists_position(user_repo):
    session = StudySession(FakeContent(), user_repo, random.Random(1234))
    seen = [session.start(BrowseOrder.RANDOM).word.id]
    seen.extend(session.next().word.id for _ in range(9))

    assert len(seen) == len(set(seen)) == 10
    saved = user_repo.load_queue("random")
    assert saved.position == 9

    restored = StudySession(FakeContent(), user_repo, random.Random(999))
    snapshot = restored.start(BrowseOrder.RANDOM)
    assert snapshot.word.id == saved.word_ids[9]
    assert snapshot.index == 9


def test_invalid_saved_random_queue_is_rebuilt_from_current_content(user_repo):
    user_repo.queues["random"] = QueueState((1, 2, 999), 2, 44)
    session = StudySession(FakeContent(4), user_repo, random.Random(5))

    session.start(BrowseOrder.RANDOM)

    saved = user_repo.load_queue("random")
    assert set(saved.word_ids) == {1, 2, 3, 4}
    assert len(saved.word_ids) == 4
    assert saved.position == 0


def test_boundaries_do_not_wrap_or_record_duplicate_navigation(session, user_repo):
    first = session.start(BrowseOrder.SOURCE)
    assert session.previous() == first
    assert user_repo.seen == [first.word.id]

    for _ in range(20):
        last = session.next()
    assert last.at_end is True
    assert last.index == 9
    assert len(user_repo.seen) == 10
    assert session.next() == last
    assert len(user_repo.seen) == 10


def test_source_position_and_favorite_state_persist(user_repo):
    session = StudySession(FakeContent(3), user_repo, random.Random(1))
    session.start(BrowseOrder.SOURCE)
    session.next()
    session.set_favorite(True)
    assert session.current().favorite is True

    restored = StudySession(FakeContent(3), user_repo, random.Random(2))
    snapshot = restored.start(BrowseOrder.SOURCE)
    assert snapshot.index == 1
    assert snapshot.word.id == 2
    assert snapshot.favorite is True
    assert user_repo.settings["browse_order"] == "source"


def test_reshuffle_replaces_random_queue_and_returns_to_start(user_repo):
    session = StudySession(FakeContent(6), user_repo, random.Random(8))
    session.start(BrowseOrder.RANDOM)
    session.next()
    before = user_repo.load_queue("random")

    snapshot = session.reshuffle()

    after = user_repo.load_queue("random")
    assert snapshot.index == 0
    assert set(after.word_ids) == set(before.word_ids)
    assert (after.word_ids, after.seed) != (before.word_ids, before.seed)
    assert after.position == 0


def test_start_rejects_empty_content():
    session = StudySession(FakeContent(0), FakeUser(), random.Random(1))
    with pytest.raises(ValueError, match="empty"):
        session.start(BrowseOrder.SOURCE)


def test_navigation_keeps_memory_intent_and_retries_queue_and_seen_atomically(
    tmp_path,
):
    path = tmp_path / "user.db"
    with UserRepository(path) as user:
        session = StudySession(FakeContent(3), user, random.Random(1))
        first = session.start(BrowseOrder.SOURCE)
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

        assert second.index == 1
        assert second.word.id == 2
        assert user.load_queue("source").position == 1
        assert user.seen_word_count() == 2
        assert user.has_pending_writes
        assert user.take_persistence_issue() is not None

        with UserRepository(path) as observer:
            assert observer.load_queue("source").position == 0
            assert observer.seen_word_count() == 1

        user.db.execute("drop trigger fail_seen")
        session.set_mode(StudyMode.RECALL)
        assert not user.has_pending_writes

    with UserRepository(path) as persisted:
        assert persisted.load_queue("source").position == 1
        assert persisted.seen_word_count() == 2
        assert persisted.db.execute(
            "select seen_count from word_progress where word_id=2"
        ).fetchone()[0] == 1

