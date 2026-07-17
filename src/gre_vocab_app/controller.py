from __future__ import annotations

import logging
from dataclasses import replace
from typing import Any

from PySide6.QtWidgets import QMessageBox

from gre_vocab_app.domain import BrowseOrder, SessionSnapshot, StudyMode, WordEntry
from gre_vocab_app.ui.main_window import MainWindow


LOGGER = logging.getLogger(__name__)


class ApplicationController:
    def __init__(
        self,
        *,
        window: MainWindow,
        content_repository: Any,
        user_repository: Any,
        study_session: Any,
        search_service: Any,
        speech_service: Any,
    ):
        self.window = window
        self.content = content_repository
        self.user = user_repository
        self.study = study_session
        self.search = search_service
        self.speech = speech_service
        self._detail_snapshot: SessionSnapshot | None = None
        self._detail_origin = "home"
        self._connect()

    def _connect(self) -> None:
        home = self.window.home_page
        study_page = self.window.study_page
        favorites = self.window.favorites_page
        settings = self.window.settings_dialog

        home.searchRequested.connect(self._search_home)
        home.continueRequested.connect(self._continue_study)
        home.sourceRequested.connect(lambda: self._open_study(BrowseOrder.SOURCE))
        home.randomRequested.connect(lambda: self._open_study(BrowseOrder.RANDOM))
        home.favoriteRequested.connect(self._open_favorites)
        home.wordSelected.connect(lambda word: self._open_detail(word, "home"))

        study_page.backRequested.connect(self._back_from_study)
        study_page.previousRequested.connect(self._previous)
        study_page.nextRequested.connect(self._next)
        study_page.modeRequested.connect(self._set_mode)
        study_page.answerToggleRequested.connect(self._toggle_answer)
        study_page.speechRequested.connect(self._speak)
        study_page.favoriteRequested.connect(self._set_favorite)
        study_page.reshuffleRequested.connect(self._reshuffle)

        favorites.searchRequested.connect(self._filter_favorites)
        favorites.wordSelected.connect(
            lambda word: self._open_detail(word, "favorites")
        )
        favorites.favoriteRemoved.connect(self._remove_favorite)

        self.window.homeRequested.connect(self._show_home)
        self.window.findRequested.connect(self._find_home)
        self.window.closing.connect(self._handle_close)
        self.window.enable_close_guard()
        settings.voiceSelected.connect(self._select_voice)
        settings.rateChanged.connect(self._set_rate)
        settings.defaultModeChanged.connect(self._set_default_mode)
        settings.resetPositionRequested.connect(self._reset_positions)
        settings.clearAllRequested.connect(self._clear_all)

        backend_error = getattr(self.speech, "errorOccurred", None)
        if backend_error is not None and hasattr(backend_error, "connect"):
            backend_error.connect(self._speech_error)
        availability_changed = getattr(self.speech, "availabilityChanged", None)
        if availability_changed is not None and hasattr(
            availability_changed, "connect"
        ):
            availability_changed.connect(self._speech_availability_changed)

    def start(self) -> None:
        self.window.restore_geometry_state(
            self.user.load_setting("window_geometry")
        )
        self._configure_settings()
        self._refresh_stats()
        self._refresh_favorites()
        self.window.show_home()

    def _configure_settings(self) -> None:
        names = tuple(self.speech.voice_names())
        saved_voice = self.user.load_setting("voice_name")
        selected = saved_voice if saved_voice in names else (names[0] if names else None)
        using_default_voice = bool(
            getattr(self.speech, "using_default_voice", False)
        )
        self.window.settings_dialog.set_voice_names(
            names,
            selected,
            using_default_voice=using_default_voice,
        )
        if selected:
            self.speech.select_voice(selected)
        self.window.study_page.set_speech_available(bool(self.speech.available))

        raw_rate = self.user.load_setting("speech_rate")
        try:
            rate = float(raw_rate) if raw_rate is not None else 0.0
        except ValueError:
            rate = 0.0
        rate = max(-1.0, min(1.0, rate))
        self.speech.set_rate(rate)
        self.window.settings_dialog.set_rate(rate)

        raw_mode = self.user.load_setting("study_mode")
        try:
            mode = StudyMode(raw_mode) if raw_mode else StudyMode.READING
        except ValueError:
            mode = StudyMode.READING
        self.window.settings_dialog.set_default_mode(mode)

        take_notice = getattr(self.speech, "take_availability_notice", None)
        if callable(take_notice):
            notice = take_notice()
            if notice:
                self._show_status(notice)

    def _refresh_stats(self) -> None:
        self.window.home_page.set_stats(
            total=self.content.count(),
            seen=self.user.seen_word_count(),
            favorites=len(self.user.favorite_ids()),
        )

    def _favorite_words(self) -> list[WordEntry]:
        ids = tuple(self.user.favorite_ids())
        return self.content.list_by_ids(ids) if ids else []

    def _refresh_favorites(self, query: str = "") -> None:
        words = self._favorite_words()
        value = query.strip().casefold()
        if value:
            words = [
                word
                for word in words
                if value in word.headword.casefold()
                or value in word.definition_en.casefold()
                or value in word.definition_zh.casefold()
            ]
        self.window.favorites_page.set_words(words)

    def _show_home(self) -> None:
        self._detail_snapshot = None
        self._refresh_stats()
        self.window.show_home()

    def _find_home(self) -> None:
        self._show_home()
        self.window.home_page.focus_search()

    def _search_home(self, query: str) -> None:
        self.window.home_page.set_results(self.search.search(query))

    def _continue_study(self) -> None:
        value = self.user.load_setting("browse_order")
        try:
            order = BrowseOrder(value) if value else BrowseOrder.SOURCE
        except ValueError:
            order = BrowseOrder.SOURCE
        self._open_study(order)

    def _open_study(self, order: BrowseOrder) -> None:
        try:
            snapshot = self.study.start(order)
        except (KeyError, ValueError, RuntimeError) as error:
            LOGGER.exception("Unable to start study session")
            self._show_status(f"无法开始学习：{error}")
            return
        self._detail_snapshot = None
        self.window.study_page.render(snapshot)
        self.window.show_study()
        self._refresh_stats()
        self._report_persistence_issue()

    def _open_detail(self, word: WordEntry, origin: str) -> None:
        raw_mode = self.user.load_setting("study_mode")
        try:
            mode = StudyMode(raw_mode) if raw_mode else StudyMode.READING
        except ValueError:
            mode = StudyMode.READING
        self._detail_origin = origin
        self._detail_snapshot = SessionSnapshot(
            word=word,
            index=0,
            total=1,
            mode=mode,
            order=BrowseOrder.SOURCE,
            answer_visible=False,
            favorite=self.user.is_favorite(word.id),
            at_start=True,
            at_end=True,
        )
        self.window.study_page.render(self._detail_snapshot)
        self.window.show_study()

    def _back_from_study(self) -> None:
        if self._detail_snapshot is not None and self._detail_origin == "favorites":
            self._detail_snapshot = None
            self._refresh_favorites(self.window.favorites_page.search_edit.text())
            self.window.show_favorites()
        else:
            self._show_home()

    def _previous(self) -> None:
        if self._detail_snapshot is not None:
            self._show_status("当前是单词详情，已经是第一条。")
            return
        before = self.study.current()
        snapshot = self.study.previous()
        self.window.study_page.render(snapshot)
        if before.at_start:
            self._show_status("已经是第一个词。")
        self._refresh_stats()
        self._report_persistence_issue()

    def _next(self) -> None:
        if self._detail_snapshot is not None:
            self._show_status("当前是单词详情，已经是最后一条。")
            return
        before = self.study.current()
        snapshot = self.study.next()
        self.window.study_page.render(snapshot)
        if before.at_end:
            self._show_status("已经到最后一个词。")
        self._refresh_stats()
        self._report_persistence_issue()

    def _set_mode(self, mode: StudyMode) -> None:
        if self._detail_snapshot is not None:
            self.user.save_setting("study_mode", mode.value)
            self._detail_snapshot = replace(self._detail_snapshot, mode=mode)
            self.window.study_page.render(self._detail_snapshot)
        else:
            self.window.study_page.render(self.study.set_mode(mode))
        self.window.settings_dialog.set_default_mode(mode)
        self._report_persistence_issue()

    def _toggle_answer(self) -> None:
        if self._detail_snapshot is not None:
            if self._detail_snapshot.mode is StudyMode.RECALL:
                self._detail_snapshot = replace(
                    self._detail_snapshot,
                    answer_visible=not self._detail_snapshot.answer_visible,
                )
                self.window.study_page.render(self._detail_snapshot)
        else:
            self.window.study_page.render(self.study.toggle_answer())

    def _set_favorite(self, favorite: bool) -> None:
        if self._detail_snapshot is not None:
            self.user.set_favorite(self._detail_snapshot.word.id, favorite)
            self._detail_snapshot = replace(
                self._detail_snapshot, favorite=favorite
            )
            self.window.study_page.render(self._detail_snapshot)
        else:
            self.window.study_page.render(self.study.set_favorite(favorite))
        self._refresh_stats()
        self._refresh_favorites(self.window.favorites_page.search_edit.text())
        self._report_persistence_issue()

    def _remove_favorite(self, word_id: int) -> None:
        self.user.set_favorite(word_id, False)
        self._refresh_stats()
        self._refresh_favorites(self.window.favorites_page.search_edit.text())
        self._report_persistence_issue()

    def _speak(self, headword: str) -> None:
        if not self.speech.speak(headword):
            self.window.study_page.set_speech_available(
                bool(self.speech.available)
            )
            self._show_status("当前没有可用的语音，朗读功能已禁用。")

    def _reshuffle(self) -> None:
        if self._detail_snapshot is not None:
            return
        self.window.study_page.render(self.study.reshuffle())
        self._refresh_stats()
        self._show_status("随机顺序已重新洗牌。")
        self._report_persistence_issue()

    def _open_favorites(self) -> None:
        self._detail_snapshot = None
        self._refresh_favorites(self.window.favorites_page.search_edit.text())
        self.window.show_favorites()

    def _filter_favorites(self, query: str) -> None:
        self._refresh_favorites(query)

    def _select_voice(self, name: str) -> None:
        if self.speech.select_voice(name):
            self.user.save_setting("voice_name", name)
            self._report_persistence_issue()
        else:
            self._show_status("无法使用所选英文语音。")

    def _set_rate(self, rate: float) -> None:
        self.speech.set_rate(rate)
        self.user.save_setting("speech_rate", f"{rate:.1f}")
        self._report_persistence_issue()

    def _set_default_mode(self, mode: StudyMode) -> None:
        self.user.save_setting("study_mode", StudyMode(mode).value)
        self._report_persistence_issue()

    def _reset_positions(self) -> None:
        self._show_status("学习位置已重置。")
        self.user.reset_position(BrowseOrder.SOURCE.value)
        self.user.reset_position(BrowseOrder.RANDOM.value)
        if (
            self._detail_snapshot is None
            and self.window.stack.currentWidget() is self.window.study_page
        ):
            self._open_study(self.study.current().order)
        self._report_persistence_issue()

    def _clear_all(self) -> None:
        self._show_status("本地收藏、进度、队列和设置已清空。")
        self.user.clear_all()
        self._detail_snapshot = None
        self._configure_settings()
        self._refresh_stats()
        self._refresh_favorites()
        self.window.show_home()
        self._report_persistence_issue()

    def _handle_close(self, event: Any) -> None:
        event.ignore()
        if bool(getattr(self.user, "is_closed", False)):
            LOGGER.info("Window closed after user repository shutdown")
            event.accept()
            return
        self.user.save_setting(
            "window_geometry", self.window.geometry_state()
        )
        flush_pending = getattr(self.user, "flush_pending", None)
        if callable(flush_pending):
            flushed = bool(flush_pending())
        else:
            flushed = not bool(getattr(self.user, "has_pending_writes", False))
        if flushed and not bool(getattr(self.user, "has_pending_writes", False)):
            event.accept()
            return

        self._report_persistence_issue()
        while bool(getattr(self.user, "has_pending_writes", False)):
            choice = self.window.confirm_pending_writes()
            if choice == QMessageBox.Retry:
                if bool(flush_pending()) and not self.user.has_pending_writes:
                    event.accept()
                    return
                self._report_persistence_issue()
                continue
            if choice == QMessageBox.Discard:
                discard = getattr(self.user, "discard_pending_writes", None)
                if not callable(discard):
                    LOGGER.error("User repository cannot explicitly discard pending writes")
                    return
                discard()
                LOGGER.warning("User explicitly discarded pending local writes on close")
                event.accept()
            return

    def shutdown(self) -> None:
        for name, resource in (("user", self.user), ("content", self.content)):
            try:
                closed = resource.close()
                if closed is False:
                    LOGGER.error(
                        "%s repository refused shutdown because writes remain pending",
                        name,
                    )
            except Exception:
                LOGGER.exception("Unable to close %s repository during shutdown", name)

    def _report_persistence_issue(self) -> None:
        take_issue = getattr(self.user, "take_persistence_issue", None)
        if not callable(take_issue):
            return
        issue = take_issue()
        if issue is None:
            return
        LOGGER.error("User persistence failure: %s", issue.technical)
        self._show_status(issue.user_message)

    def _speech_error(self, user_message: str, technical: str) -> None:
        LOGGER.error("Speech error: %s", technical)
        self._show_status(user_message)

    def _speech_availability_changed(self, available: bool) -> None:
        self.window.study_page.set_speech_available(bool(available))
        if not available:
            self._show_status("语音引擎当前不可用，朗读功能已禁用。")

    def _show_status(self, message: str) -> None:
        self.window.statusBar().showMessage(message, 5000)
