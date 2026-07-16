import random

from PySide6.QtCore import QObject, Signal

from gre_vocab_app.controller import ApplicationController
from gre_vocab_app.db.user import QueueState
from gre_vocab_app.domain import BrowseOrder, StudyMode, WordEntry
from gre_vocab_app.services.search import SearchService
from gre_vocab_app.services.study import StudySession
from gre_vocab_app.ui.main_window import MainWindow


class FakeContent:
    def __init__(self):
        self.words = {
            word_id: WordEntry(
                id=word_id,
                source_order=word_id,
                source_section="list1",
                source_page=5,
                headword=f"word{word_id}",
                phonetic="[x]",
                definition_en="adj. sample",
                definition_zh=f"示例{word_id}",
                synonyms="",
                example_en="",
                example_zh="",
                raw_definition="adj. sample 示例",
                raw_example="",
            )
            for word_id in range(1, 4)
        }

    def count(self):
        return len(self.words)

    def get(self, word_id):
        return self.words[word_id]

    def ids_in_source_order(self):
        return tuple(self.words)

    def list_by_ids(self, ids):
        return [self.words[word_id] for word_id in ids]

    def search(self, query, limit=50):
        value = query.casefold()
        return [
            word for word in self.words.values() if value in word.headword.casefold()
        ][:limit]


class FakeUser:
    def __init__(self):
        self.settings = {}
        self.queues = {}
        self.favorites = set()
        self.seen = {}

    def load_setting(self, key):
        return self.settings.get(key)

    def save_setting(self, key, value):
        self.settings[key] = value

    def load_queue(self, name):
        return self.queues.get(name, QueueState((), 0, 0))

    def save_queue(self, name, word_ids, *, position, seed):
        self.queues[name] = QueueState(tuple(word_ids), position, seed)

    def reset_position(self, name):
        if name in self.queues:
            state = self.queues[name]
            self.queues[name] = QueueState(state.word_ids, 0, state.seed)

    def is_favorite(self, word_id):
        return word_id in self.favorites

    def set_favorite(self, word_id, value):
        self.favorites.discard(word_id)
        if value:
            self.favorites.add(word_id)

    def favorite_ids(self):
        return tuple(sorted(self.favorites, reverse=True))

    def record_seen(self, word_id):
        self.seen[word_id] = self.seen.get(word_id, 0) + 1

    def seen_word_count(self):
        return len(self.seen)

    def clear_all(self):
        self.settings.clear()
        self.queues.clear()
        self.favorites.clear()
        self.seen.clear()


class FakeSpeech(QObject):
    errorOccurred = Signal(str, str)

    def __init__(self):
        super().__init__()
        self.spoken = []
        self.rate = 0.0
        self.selected = ""

    @property
    def available(self):
        return True

    def voice_names(self):
        return ("Microsoft Zira",)

    def select_voice(self, name):
        self.selected = name
        return name == "Microsoft Zira"

    def set_rate(self, value):
        self.rate = value

    def speak(self, word):
        self.spoken.append(word)
        return True


def make_controller(qtbot):
    content = FakeContent()
    user = FakeUser()
    speech = FakeSpeech()
    study = StudySession(content, user, random.Random(5))
    window = MainWindow()
    qtbot.addWidget(window)
    controller = ApplicationController(
        window=window,
        content_repository=content,
        user_repository=user,
        study_session=study,
        search_service=SearchService(content),
        speech_service=speech,
    )
    controller.start()
    return controller, window, content, user, speech


def test_controller_connects_source_dual_mode_navigation_and_favorite(qtbot):
    _controller, window, _content, user, _speech = make_controller(qtbot)
    assert window.stack.currentWidget() is window.home_page
    assert window.home_page.total_value.text() == "3"

    window.home_page.source_button.click()
    assert window.stack.currentWidget() is window.study_page
    first_id = window.study_page.snapshot.word.id

    window.study_page.recall_button.click()
    assert window.study_page.snapshot.word.id == first_id
    assert user.settings["study_mode"] == "recall"

    window.study_page.next_button.click()
    assert window.study_page.snapshot.index == 1
    assert window.home_page.seen_value.text() == "2"

    window.study_page.favorite_button.click()
    assert window.study_page.snapshot.favorite is True
    assert window.home_page.favorites_value.text() == "1"


def test_controller_search_detail_speech_settings_and_errors(qtbot):
    _controller, window, _content, user, speech = make_controller(qtbot)
    window.home_page.search_edit.setText("word2")
    assert window.home_page.results.count() == 1
    window.home_page.results.setCurrentRow(0)
    assert window.stack.currentWidget() is window.study_page
    assert window.study_page.snapshot.word.id == 2

    window.study_page.word_detail.speech_button.click()
    assert speech.spoken == ["word2"]

    window.settings_dialog.rate_slider.setValue(3)
    assert speech.rate == 0.3
    assert user.settings["speech_rate"] == "0.3"

    speech.errorOccurred.emit("朗读暂不可用", "technical detail")
    assert window.statusBar().currentMessage() == "朗读暂不可用"


def test_controller_favorites_reset_and_clear(qtbot, monkeypatch):
    _controller, window, _content, user, _speech = make_controller(qtbot)
    user.set_favorite(1, True)
    user.set_favorite(2, True)
    window.home_page.favorites_button.click()
    assert window.stack.currentWidget() is window.favorites_page
    assert window.favorites_page.words_list.count() == 2

    window.favorites_page.words_list.setCurrentRow(0)
    word_id = window.favorites_page.words_list.currentItem().data(0x0100).id
    window.favorites_page.remove_button.click()
    assert word_id not in user.favorites

    window.home_page.source_button.click()
    window.study_page.next_button.click()
    window.settings_dialog.reset_button.click()
    assert user.queues["source"].position == 0

    window.settings_dialog.clearAllRequested.emit()
    assert user.favorites == set()
    assert user.seen == {}
    assert user.settings == {}
    assert window.stack.currentWidget() is window.home_page
