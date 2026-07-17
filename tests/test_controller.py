import json
import random

from PySide6.QtCore import QObject, Qt, Signal

from gre_vocab_app.controller import ApplicationController
from gre_vocab_app.db.user import QueueState, UserRepository
from gre_vocab_app.domain import BrowseOrder, StudyMode, WordEntry
from gre_vocab_app.services.search import SearchService
from gre_vocab_app.services.study import StudySession
from gre_vocab_app.ui.main_window import MainWindow


class FakeContent:
    def __init__(self, count=3):
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
            for word_id in range(1, count + 1)
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
    availabilityChanged = Signal(bool)

    def __init__(self, *, available=True, notice=None, voices=("Microsoft Zira",)):
        super().__init__()
        self.spoken = []
        self.rate = 0.0
        self.selected = ""
        self._available = available
        self._notice = notice
        self._voices = voices

    @property
    def available(self):
        return self._available

    @property
    def using_default_voice(self):
        return self._available and not self._voices

    def voice_names(self):
        return self._voices

    def select_voice(self, name):
        self.selected = name
        return name == "Microsoft Zira"

    def set_rate(self, value):
        self.rate = value

    def speak(self, word):
        if not self._available:
            return False
        self.spoken.append(word)
        return True

    def take_availability_notice(self):
        notice = self._notice
        self._notice = None
        return notice


def make_controller(qtbot, *, user=None, word_count=3, speech=None):
    content = FakeContent(word_count)
    user = user or FakeUser()
    speech = speech or FakeSpeech()
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
    assert window.stack.currentWidget() is window.home_page
    window.home_page.results.itemActivated.emit(window.home_page.results.item(0))
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


def test_global_ctrl_f_returns_home_preserving_query_selection_and_scroll(qtbot):
    _controller, window, _content, _user, _speech = make_controller(
        qtbot, word_count=80
    )
    window.resize(680, 520)
    window.show()
    window.home_page.search_edit.setText("word")
    assert window.home_page.results.count() == 50
    selected_row = 40
    window.home_page.results.setCurrentRow(selected_row)
    window.home_page.results.scrollToItem(
        window.home_page.results.item(selected_row)
    )
    scroll_value = window.home_page.results.verticalScrollBar().value()
    window.home_page.results.itemActivated.emit(
        window.home_page.results.item(selected_row)
    )
    assert window.stack.currentWidget() is window.study_page

    window.activateWindow()
    qtbot.waitUntil(window.isActiveWindow)
    qtbot.waitUntil(window.study_page.isVisible)
    window.study_page.setFocus()
    qtbot.waitUntil(window.study_page.hasFocus)
    qtbot.keyClick(window.study_page, Qt.Key_F, Qt.ControlModifier)

    qtbot.waitUntil(lambda: window.stack.currentWidget() is window.home_page)
    qtbot.waitUntil(window.home_page.search_edit.hasFocus)
    assert window.home_page.search_edit.text() == "word"
    assert window.home_page.results.currentRow() == selected_row
    assert window.home_page.results.verticalScrollBar().value() == scroll_value


def test_detail_return_preserves_home_query_selection_and_scroll(qtbot):
    _controller, window, _content, _user, _speech = make_controller(
        qtbot, word_count=80
    )
    window.resize(680, 520)
    window.show()
    window.home_page.search_edit.setText("word")
    selected_row = 40
    window.home_page.results.setCurrentRow(selected_row)
    window.home_page.results.scrollToItem(
        window.home_page.results.item(selected_row)
    )
    scroll_value = window.home_page.results.verticalScrollBar().value()
    window.home_page.results.itemActivated.emit(
        window.home_page.results.item(selected_row)
    )

    window.study_page.back_button.click()

    assert window.stack.currentWidget() is window.home_page
    assert window.home_page.search_edit.text() == "word"
    assert window.home_page.results.currentRow() == selected_row
    assert window.home_page.results.verticalScrollBar().value() == scroll_value


def test_controller_restores_and_persists_window_geometry_through_user_store(
    qtbot, tmp_path
):
    path = tmp_path / "user.db"
    with UserRepository(path) as user:
        user.save_setting(
            "window_geometry",
            json.dumps({"x": 100000, "y": 100000, "width": 500, "height": 400}),
        )
        _controller, window, _content, _user, _speech = make_controller(
            qtbot, user=user
        )
        assert (window.width(), window.height()) == (980, 760)
        window.setGeometry(30, 40, 900, 700)
        window.close()

    with UserRepository(path) as reopened:
        assert json.loads(reopened.load_setting("window_geometry")) == {
            "x": 30,
            "y": 40,
            "width": 900,
            "height": 700,
        }


def test_controller_surfaces_failed_navigation_and_next_mutation_retries(
    qtbot, tmp_path
):
    path = tmp_path / "user.db"
    with UserRepository(path) as user:
        _controller, window, _content, _user, _speech = make_controller(
            qtbot, user=user
        )
        window.home_page.source_button.click()
        user.db.execute(
            """
            create trigger fail_seen before insert on word_progress
            when new.word_id = 2
            begin
              select raise(abort, 'synthetic controller failure');
            end
            """
        )

        window.study_page.next_button.click()

        assert window.study_page.snapshot.index == 1
        assert user.has_pending_writes
        assert "暂时无法保存" in window.statusBar().currentMessage()

        user.db.execute("drop trigger fail_seen")
        window.study_page.recall_button.click()
        assert not user.has_pending_writes

    with UserRepository(path) as reopened:
        assert reopened.load_queue("source").position == 1
        assert reopened.seen_word_count() == 2
        assert reopened.load_setting("study_mode") == "recall"


def test_controller_propagates_initial_and_async_speech_unavailability(qtbot):
    speech = FakeSpeech(
        available=False,
        notice="未检测到可用的语音引擎，朗读功能已禁用。",
    )
    _controller, window, _content, _user, _speech = make_controller(
        qtbot, speech=speech
    )
    assert "朗读功能已禁用" in window.statusBar().currentMessage()
    window.home_page.source_button.click()
    assert not window.study_page.word_detail.speech_button.isEnabled()
    assert not window.study_page.speech_shortcut.isEnabled()

    speech._available = True
    speech.availabilityChanged.emit(True)
    assert window.study_page.word_detail.speech_button.isEnabled()

    speech._available = False
    speech.availabilityChanged.emit(False)
    assert not window.study_page.word_detail.speech_button.isEnabled()
    assert "朗读" in window.statusBar().currentMessage()
