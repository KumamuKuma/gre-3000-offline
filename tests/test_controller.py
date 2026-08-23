import json
import random
import sqlite3
from unittest.mock import Mock

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QMessageBox

from gre_vocab_app.controller import ApplicationController
from gre_vocab_app.db.user import QueueState, UserRepository
from gre_vocab_app.domain import BrowseOrder, SourceList, StudyMode, WordEntry
from gre_vocab_app.services.search import SearchService
from gre_vocab_app.services.dictionary import LookupResult
from gre_vocab_app.services.long_sentences import LongSentence, LongSentenceNote
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

    def ids_for_section(self, key):
        if key != "list1" or not self.words:
            raise KeyError(key)
        return tuple(self.words)

    def source_lists(self):
        if not self.words:
            return ()
        return (SourceList("list1", "List 1", len(self.words), 1, len(self.words)),)

    def source_list(self, key):
        if key != "list1" or not self.words:
            raise KeyError(key)
        return self.source_lists()[0]

    def root_families(self, _word_id):
        return ()

    def lookalikes(self, _word_id):
        return ()

    def in_machine7(self, word_id):
        return word_id % 2 == 1

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
        self.stars = {}
        self.review_counts = {}
        self.completions = {}

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

    def reset_all_positions(self):
        for name in tuple(self.queues):
            self.reset_position(name)
        return True

    def is_favorite(self, word_id):
        return word_id in self.favorites

    def set_favorite(self, word_id, value):
        self.favorites.discard(word_id)
        if value:
            self.favorites.add(word_id)

    def favorite_ids(self):
        return tuple(sorted(self.favorites, reverse=True))

    def star_rating(self, word_id):
        return self.stars.get(word_id, 0)

    def set_star_rating(self, word_id, value):
        self.stars[word_id] = value
        return True

    def cycle_star_rating(self, word_id):
        value = (self.star_rating(word_id) + 1) % 4
        self.set_star_rating(word_id, value)
        return value

    def manual_review_count(self, word_id):
        return self.review_counts.get(word_id, 0)

    def set_manual_review_count(self, word_id, value):
        self.review_counts[word_id] = value
        return True

    def adjust_manual_review_count(self, word_id, delta):
        value = max(0, self.manual_review_count(word_id) + delta)
        self.set_manual_review_count(word_id, value)
        return value

    def star_counts(self, word_ids):
        counts = {rating: 0 for rating in range(4)}
        for word_id in dict.fromkeys(word_ids):
            counts[self.star_rating(word_id)] += 1
        return counts

    def record_seen(self, word_id):
        self.seen[word_id] = self.seen.get(word_id, 0) + 1

    def seen_word_count(self):
        return len(self.seen)

    def list_completion_count(self, key):
        return self.completions.get(key, 0)

    def list_completion_counts(self):
        return dict(self.completions)

    def increment_list_completion(self, key):
        return self.adjust_list_completion(key, 1)

    def adjust_list_completion(self, key, delta):
        self.completions[key] = max(0, self.completions.get(key, 0) + delta)
        return self.completions[key]

    def clear_all(self):
        self.settings.clear()
        self.queues.clear()
        self.favorites.clear()
        self.seen.clear()
        self.stars.clear()
        self.review_counts.clear()
        self.completions.clear()


def test_controller_migrates_old_list_scopes_without_changing_normal_study():
    controller = ApplicationController.__new__(ApplicationController)
    controller.user = FakeUser()
    controller._source_lists = (
        SourceList("list1", "List 1", 3, 1, 3),
        SourceList("list2", "List 2", 2, 4, 5),
    )
    controller.user.settings.update(
        {
            "study_list": "list1",
            "study_star_lists": "all",
            "study_filter": "all",
        }
    )
    assert controller._saved_list_keys() == ("list1",)

    controller.user.settings["study_filter"] = "star:2"
    assert controller._saved_list_keys() == ("list1", "list2")

    controller.user.settings["study_lists"] = "list2"
    assert controller._saved_list_keys() == ("list2",)


class FakeSpeech(QObject):
    errorOccurred = Signal(str, str)
    availabilityChanged = Signal(bool)

    def __init__(self, *, available=True, notice=None, voices=("Microsoft Zira",)):
        super().__init__()
        self.spoken = []
        self.online_spoken = []
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

    def speak_with_voice(self, text, voice_name):
        if not self._available or voice_name not in self._voices:
            return False
        self.spoken.append((text, voice_name))
        return True

    def speak_online(self, text):
        self.online_spoken.append(text)
        return True

    def take_availability_notice(self):
        notice = self._notice
        self._notice = None
        return notice


def make_controller(
    qtbot,
    *,
    user=None,
    word_count=3,
    speech=None,
    long_sentence_service=None,
    dictionary_service=None,
):
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
        long_sentence_service=long_sentence_service,
        dictionary_service=dictionary_service,
    )
    controller.start()
    return controller, window, content, user, speech


def test_controller_opens_long_sentences_and_reuses_dictionary_lookup(qtbot):
    long_sentence_service = Mock()
    long_sentence_service.load.return_value = (
        LongSentence(
            1,
            1,
            "Although it was difficult, we continued.",
            (4,),
            (LongSentenceNote("解释", "The difficult clause is concessive."),),
        ),
    )
    dictionary_service = Mock()
    dictionary_service.lookup.return_value = LookupResult(
        query="Although",
        normalized="although",
        kind="word",
        source="本地词典",
        headword="although",
        offline_translation="虽然；尽管",
    )
    controller, window, _content, _user, _speech = make_controller(
        qtbot,
        long_sentence_service=long_sentence_service,
        dictionary_service=dictionary_service,
    )

    window.home_page.long_sentence_button.click()
    assert window.stack.currentWidget() is window.long_sentence_page
    assert window.long_sentence_page.sentence_label.text().startswith("Although")
    long_sentence_service.load.assert_called_once_with()

    window.long_sentence_page.sentence_label._activate_link("lookup:Although")
    dictionary_service.lookup.assert_called_once_with("Although")
    assert window.lookup_dialog.query_label.text() == "although"

    dictionary_service.reset_mock()
    window.long_sentence_page.note_labels[0]._activate_link("lookup:concessive")
    dictionary_service.lookup.assert_called_once_with("concessive")

    window.long_sentence_page.back_button.click()
    assert window.stack.currentWidget() is window.home_page


def test_controller_shows_friendly_long_sentence_loading_error(qtbot):
    service = Mock()
    service.load.side_effect = ValueError("invalid fixture")
    _controller, window, _content, _user, _speech = make_controller(
        qtbot, long_sentence_service=service
    )

    window.home_page.long_sentence_button.click()

    assert window.stack.currentWidget() is window.long_sentence_page
    assert "暂时无法读取" in window.long_sentence_page.empty_state.text()
    assert "invalid fixture" not in window.long_sentence_page.empty_state.text()


def test_controller_connects_selected_list_modes_and_navigation(qtbot):
    _controller, window, _content, user, _speech = make_controller(qtbot)
    assert window.stack.currentWidget() is window.home_page
    assert window.home_page.total_value.text() == "3"

    window.home_page.start_button.click()
    assert window.stack.currentWidget() is window.study_page
    first_id = window.study_page.snapshot.word.id

    window.study_page.recall_button.click()
    assert window.study_page.snapshot.word.id == first_id
    assert user.settings["study_mode"] == "recall"

    window.study_page.next_button.click()
    assert window.study_page.snapshot.index == 1
    assert not hasattr(window.home_page, "seen_value")

    assert window.study_page.snapshot.list_key == "list1"
    assert not hasattr(window.study_page, "favorite_button")


def test_controller_machine7_filter_persists_and_keeps_source_order(qtbot):
    controller, window, _content, user, _speech = make_controller(
        qtbot, word_count=6
    )

    window.home_page.machine7_only_checkbox.click()
    assert user.settings["study_machine7_only"] == "1"
    assert window.home_page.machine7_only()
    assert window.home_page.star_scope_button.text() == "全部星级（3 词）"
    window.home_page.start_button.click()

    first = window.study_page.snapshot
    assert first.machine7_only
    assert first.word.id == 1
    assert first.total == 3
    assert not first.can_complete_round
    window.study_page.next_button.click()
    assert window.study_page.snapshot.word.id == 3
    window.study_page.last_button.click()
    assert window.study_page.snapshot.word.id == 5
    assert not window.study_page.snapshot.can_complete_round

    window.study_page.back_button.click()
    controller._configure_home_scope()
    assert window.home_page.machine7_only_checkbox.isChecked()


def test_controller_word_list_machine7_filter_is_independent_and_persisted(
    qtbot,
):
    controller, window, _content, user, _speech = make_controller(
        qtbot, word_count=6
    )
    window.word_list_action.trigger()
    page = window.word_list_page
    page.machine7_only_checkbox.click()

    assert user.settings["word_list_machine7_only"] == "1"
    assert page.count_label.text() == "3 / 6 词"
    assert not page.machine7_only_checkbox.isHidden()

    page.set_machine7_only(False)
    controller._refresh_word_list()
    assert page.machine7_only_checkbox.isChecked()
    assert page.count_label.text() == "3 / 6 词"


def test_controller_cycles_stars_studies_a_rating_in_source_order_and_quizzes(
    qtbot,
):
    controller, window, _content, user, _speech = make_controller(
        qtbot, word_count=6
    )
    window.home_page.start_button.click()
    assert window.study_page.snapshot.word.id == 1

    window.study_page.star_button.click()
    window.study_page.star_button.click()
    assert user.stars[1] == 2
    assert window.study_page.star_button.text() == "★★☆"
    user.set_star_rating(4, 2)

    window.study_page.back_button.click()
    controller._refresh_stats()
    assert window.home_page.set_selected_star_ratings((2,))
    window.home_page.starFiltersChanged.emit((2,))
    assert "2 星" in window.home_page.star_scope_button.text()
    window.home_page.start_button.click()

    assert window.study_page.snapshot.star_filter == 2
    assert window.study_page.snapshot.total == 2
    assert window.study_page.snapshot.word.id == 1
    window.study_page.next_button.click()
    assert window.study_page.snapshot.word.id == 4

    window.study_page.quiz_button.click()
    quiz = window.study_page.snapshot
    assert quiz.mode is StudyMode.QUIZ
    assert len(quiz.quiz_choices) == 4
    assert len({choice.text for choice in quiz.quiz_choices}) == 4
    selected_word_id = quiz.word.id
    window.study_page.word_detail.quiz_buttons[quiz.quiz_correct_index].click()
    answered = window.study_page.snapshot
    assert answered.word.id == selected_word_id
    assert answered.quiz_selected_index == answered.quiz_correct_index
    assert "回答正确" in window.study_page.word_detail.quiz_feedback_label.text()

    window.study_page.back_button.click()
    window.home_page.start_button.click()
    assert window.study_page.snapshot.star_filter == 2


def test_controller_quiz_auto_star_adjustments_are_independent_and_persisted(
    qtbot,
):
    _controller, window, _content, user, _speech = make_controller(
        qtbot, word_count=6
    )
    window.home_page.start_button.click()
    window.study_page.quiz_button.click()
    window.study_page.quiz_wrong_star_up_checkbox.setChecked(True)
    assert user.settings["quiz_wrong_star_up"] == "1"
    assert user.settings.get("quiz_correct_star_down") is None

    first_quiz = window.study_page.snapshot
    wrong_index = next(
        index
        for index in range(len(first_quiz.quiz_choices))
        if index != first_quiz.quiz_correct_index
    )
    window.study_page.word_detail.quiz_buttons[wrong_index].click()
    assert user.stars[first_quiz.word.id] == 1
    assert window.study_page.snapshot.star_rating == 1
    assert window.study_page.snapshot.quiz_attempt_count == 1
    assert not window.study_page.quiz_retry_button.isHidden()

    window.study_page.quiz_correct_star_down_checkbox.setChecked(True)
    assert user.settings["quiz_correct_star_down"] == "1"
    window.study_page.quiz_retry_button.click()
    assert window.study_page.snapshot.quiz_selected_index is None
    assert window.study_page.snapshot.quiz_attempt_count == 1
    window.study_page.word_detail.quiz_buttons[
        first_quiz.quiz_correct_index
    ].click()
    assert window.study_page.snapshot.quiz_attempt_count == 2
    assert user.stars[first_quiz.word.id] == 1
    assert window.study_page.snapshot.star_rating == 1

    window.study_page.next_button.click()
    second_quiz = window.study_page.snapshot
    user.set_star_rating(second_quiz.word.id, 2)
    window.study_page.render(_controller.study.current())
    assert user.settings["quiz_correct_star_down"] == "1"
    window.study_page.word_detail.quiz_buttons[
        second_quiz.quiz_correct_index
    ].click()
    assert user.stars[second_quiz.word.id] == 1
    assert window.study_page.snapshot.star_rating == 1

    window.study_page.quiz_wrong_star_up_checkbox.setChecked(False)
    assert user.settings["quiz_wrong_star_up"] == "0"


def test_quiz_choice_gre_entry_returns_to_the_same_retry_state(qtbot):
    controller, window, _content, user, _speech = make_controller(
        qtbot, word_count=6
    )
    window.home_page.start_button.click()
    window.study_page.quiz_button.click()
    window.study_page.quiz_wrong_star_up_checkbox.setChecked(True)

    question = window.study_page.snapshot
    wrong_index = next(
        index
        for index in range(len(question.quiz_choices))
        if index != question.quiz_correct_index
    )
    target_word_id = question.quiz_choices[wrong_index].word_id
    window.study_page.word_detail.quiz_buttons[wrong_index].click()
    assert window.study_page.snapshot.quiz_selected_index == wrong_index
    assert window.study_page.snapshot.quiz_attempt_count == 1
    assert user.stars[question.word.id] == 1

    window.study_page.word_detail.quiz_word_buttons[wrong_index].click()
    preview = window.study_page.snapshot
    assert preview.word.id == target_word_id
    assert preview.mode is StudyMode.READING
    assert controller._detail_origin == "quiz_word"

    window.study_page.back_button.click()
    restored = window.study_page.snapshot
    assert restored.word.id == question.word.id
    assert restored.quiz_selected_index == wrong_index
    assert restored.quiz_attempt_count == 1
    assert not window.study_page.quiz_retry_button.isHidden()

    window.study_page.quiz_retry_button.click()
    assert window.study_page.snapshot.quiz_selected_index is None
    assert window.study_page.snapshot.quiz_attempt_count == 1
    window.study_page.word_detail.quiz_word_buttons[
        question.quiz_correct_index
    ].click()
    assert window.study_page.snapshot.mode is StudyMode.READING
    window.study_page.back_button.click()
    assert window.study_page.snapshot.quiz_selected_index is None
    assert window.study_page.snapshot.quiz_attempt_count == 1
    window.study_page.word_detail.quiz_buttons[
        question.quiz_correct_index
    ].click()
    assert window.study_page.snapshot.quiz_attempt_count == 2
    assert user.stars[question.word.id] == 1


def test_quiz_choice_gre_entry_restores_a_word_list_detail_quiz(qtbot):
    controller, window, content, user, _speech = make_controller(
        qtbot, word_count=6
    )
    user.settings["study_mode"] = "quiz"
    controller._open_detail(content.get(1), "word_list")
    question = window.study_page.snapshot
    wrong_index = next(
        index
        for index in range(len(question.quiz_choices))
        if index != question.quiz_correct_index
    )
    window.study_page.word_detail.quiz_buttons[wrong_index].click()
    answered = window.study_page.snapshot

    window.study_page.word_detail.quiz_word_buttons[wrong_index].click()
    assert window.study_page.snapshot.mode is StudyMode.READING
    window.study_page.back_button.click()

    restored = window.study_page.snapshot
    assert restored.word.id == answered.word.id
    assert restored.quiz_choices == answered.quiz_choices
    assert restored.quiz_selected_index == answered.quiz_selected_index
    assert restored.quiz_attempt_count == answered.quiz_attempt_count
    assert controller._detail_origin == "word_list"


def test_quiz_choice_gre_entry_restores_latest_rating_before_auto_adjustment(
    qtbot,
):
    controller, window, content, user, _speech = make_controller(
        qtbot, word_count=6
    )
    user.settings["study_mode"] = "quiz"
    controller._open_detail(content.get(1), "word_list")
    question = window.study_page.snapshot
    wrong_index = next(
        index
        for index in range(len(question.quiz_choices))
        if index != question.quiz_correct_index
    )

    window.study_page.word_detail.quiz_word_buttons[
        question.quiz_correct_index
    ].click()
    assert window.study_page.snapshot.word.id == question.word.id
    window.study_page.star_button.click()
    window.study_page.star_button.click()
    assert user.stars[question.word.id] == 2

    window.study_page.back_button.click()
    restored = window.study_page.snapshot
    assert restored.word.id == question.word.id
    assert restored.star_rating == 2
    assert restored.quiz_selected_index is None
    assert restored.quiz_attempt_count == 0

    window.study_page.quiz_wrong_star_up_checkbox.setChecked(True)
    window.study_page.word_detail.quiz_buttons[wrong_index].click()
    assert user.stars[question.word.id] == 3
    assert window.study_page.snapshot.star_rating == 3


def test_controller_word_list_updates_rating_and_returns_from_detail(
    qtbot, monkeypatch
):
    _controller, window, _content, user, _speech = make_controller(
        qtbot, word_count=6
    )

    window.word_list_action.trigger()
    assert window.stack.currentWidget() is window.word_list_page
    page = window.word_list_page
    assert page.words_table.rowCount() == 6
    page.words_table.setCurrentCell(0, 0)
    full_rebuild = Mock(wraps=page.set_words)
    monkeypatch.setattr(page, "set_words", full_rebuild)

    page.star_button.click()
    page.star_button.click()
    assert full_rebuild.call_count == 0
    assert user.stars[1] == 2
    assert page.words_table.item(0, 5).text() == "2 星"

    page.open_button.click()
    assert window.stack.currentWidget() is window.study_page
    assert window.study_page.snapshot.star_rating == 2
    window.study_page.back_button.click()
    assert window.stack.currentWidget() is window.word_list_page


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
    assert window.study_page.word_detail.secondary_speech_button.isEnabled()
    assert "在线自然音" in window.settings_dialog.secondary_voice_combo.currentText()
    window.study_page.word_detail.secondary_speech_button.click()
    assert speech.online_spoken == ["word2"]

    window.settings_dialog.rate_slider.setValue(3)
    assert speech.rate == 0.3
    assert user.settings["speech_rate"] == "0.3"

    speech.errorOccurred.emit("朗读暂不可用", "technical detail")
    assert window.statusBar().currentMessage() == "朗读暂不可用"


def test_controller_auto_speaks_only_after_moving_to_next_word(qtbot):
    _controller, window, _content, user, speech = make_controller(qtbot)
    window.settings_dialog.auto_speak_checkbox.setChecked(True)
    assert user.settings["auto_speak"] == "1"
    window.home_page.start_button.click()
    assert speech.spoken == []
    window.study_page.next_button.click()
    assert speech.spoken == ["word2"]
    window.study_page.previous_button.click()
    assert speech.spoken == ["word2"]


def test_controller_records_list_completion_resets_and_clears(qtbot):
    _controller, window, _content, user, _speech = make_controller(qtbot)
    window.home_page.increase_rounds_button.click()
    assert user.completions == {"list1": 1}
    assert window.home_page.rounds_value_label.text() == "1"
    window.home_page.decrease_rounds_button.click()
    assert user.completions == {"list1": 0}
    window.home_page.start_button.click()
    window.study_page.next_button.click()
    window.study_page.next_button.click()
    assert window.study_page.next_button.text() == "完成本轮"
    window.study_page.next_button.click()
    assert user.completions == {"list1": 1}
    assert window.home_page.rounds_value.text() == "1"

    window.home_page.start_button.click()
    window.study_page.next_button.click()
    window.settings_dialog.reset_button.click()
    assert window.study_page.snapshot.index == 0
    assert user.queues["source:list:list1:all"].position == 0

    window.study_page.star_button.click()
    window.settings_dialog.clearAllRequested.emit()
    assert user.completions == {}
    assert user.seen == {}
    assert user.stars == {}
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
        available = QGuiApplication.primaryScreen().availableGeometry()
        assert (window.width(), window.height()) == (
            min(980, available.width()),
            min(760, available.height()),
        )
        assert available.contains(window.geometry())
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
        window.home_page.start_button.click()
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
        assert reopened.load_queue("source:list:list1:all").position == 1
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
    window.home_page.start_button.click()
    assert not window.study_page.word_detail.speech_button.isEnabled()
    assert not window.study_page.speech_shortcut.isEnabled()

    speech._available = True
    speech.availabilityChanged.emit(True)
    assert window.study_page.word_detail.speech_button.isEnabled()

    speech._available = False
    speech.availabilityChanged.emit(False)
    assert not window.study_page.word_detail.speech_button.isEnabled()
    assert "朗读" in window.statusBar().currentMessage()


def test_locked_database_close_keeps_window_and_retries_all_pending_writes(
    qtbot, tmp_path, monkeypatch
):
    path = tmp_path / "user.db"
    user = UserRepository(path)
    _controller, window, _content, _user, _speech = make_controller(
        qtbot, user=user
    )
    window.show()
    qtbot.waitUntil(window.isVisible)

    lock = sqlite3.connect(path)
    lock.execute("begin exclusive")
    try:
        assert user.save_setting("study_mode", "recall") is False
        choices = iter((QMessageBox.Retry, QMessageBox.Cancel))
        monkeypatch.setattr(
            window,
            "confirm_pending_writes",
            lambda: next(choices),
            raising=False,
        )

        assert window.close() is False
        assert window.isVisible()
        assert user.has_pending_writes
    finally:
        lock.rollback()
        lock.close()

    assert window.close() is True
    assert not window.isVisible()
    assert not user.has_pending_writes
    assert user.close() is True

    with UserRepository(path) as reopened:
        assert reopened.load_setting("study_mode") == "recall"
        assert reopened.load_setting("window_geometry") is not None


def test_locked_database_close_allows_only_explicit_discard(qtbot, tmp_path, monkeypatch):
    path = tmp_path / "user.db"
    user = UserRepository(path)
    _controller, window, _content, _user, _speech = make_controller(
        qtbot, user=user
    )
    window.show()
    qtbot.waitUntil(window.isVisible)

    lock = sqlite3.connect(path)
    lock.execute("begin exclusive")
    try:
        assert user.save_setting("study_mode", "recall") is False
        monkeypatch.setattr(
            window,
            "confirm_pending_writes",
            lambda: QMessageBox.Discard,
            raising=False,
        )

        assert window.close() is True
        assert not window.isVisible()
        assert not user.has_pending_writes
    finally:
        lock.rollback()
        lock.close()

    assert user.close() is True
    with UserRepository(path) as reopened:
        assert reopened.load_setting("study_mode") is None


def test_controller_shutdown_contains_resource_close_errors(qtbot, caplog):
    controller, _window, _content, _user, _speech = make_controller(qtbot)

    class FailingResource:
        def close(self):
            raise sqlite3.OperationalError("synthetic close failure")

    original_content = controller.content
    original_user = controller.user
    try:
        controller.content = FailingResource()
        controller.user = FailingResource()

        assert hasattr(controller, "shutdown")
        controller.shutdown()
        assert "synthetic close failure" in caplog.text
    finally:
        controller.content = original_content
        controller.user = original_user


def test_window_close_after_repository_shutdown_does_not_prompt(qtbot, tmp_path, monkeypatch):
    user = UserRepository(tmp_path / "user.db")
    _controller, window, _content, _user, _speech = make_controller(
        qtbot, user=user
    )
    window.show()
    qtbot.waitUntil(window.isVisible)
    assert user.close() is True
    prompts = []
    monkeypatch.setattr(
        window,
        "confirm_pending_writes",
        lambda: prompts.append(True) or QMessageBox.Discard,
    )

    assert window.close() is True
    assert prompts == []
