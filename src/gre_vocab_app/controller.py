from __future__ import annotations

import logging
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from PySide6.QtWidgets import QFileDialog, QMessageBox

from gre_vocab_app.domain import BrowseOrder, SessionSnapshot, StudyMode, WordEntry
from gre_vocab_app.progress_transfer import (
    ProgressFormatError,
    export_progress,
    import_progress,
)
from gre_vocab_app.services.cloud_sync import (
    DEFAULT_CLOUD_ENDPOINT,
    CloudSyncError,
    create_sync_code,
    download_progress,
    upload_progress,
)
from gre_vocab_app.ui.main_window import MainWindow
from gre_vocab_app.ui.word_list_page import WordListRow


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
        self._all_words: list[WordEntry] = []
        self._source_lists = ()
        self._auto_speak_enabled = False
        self._connect()

    def _connect(self) -> None:
        home = self.window.home_page
        study_page = self.window.study_page
        settings = self.window.settings_dialog

        home.searchRequested.connect(self._search_home)
        home.listStudyRequested.connect(self._open_list_study)
        home.listSelectionChanged.connect(self._select_list)
        home.listCompletionAdjustmentRequested.connect(
            self._adjust_list_completion
        )
        home.wordSelected.connect(lambda word: self._open_detail(word, "home"))

        study_page.backRequested.connect(self._back_from_study)
        study_page.previousRequested.connect(self._previous)
        study_page.nextRequested.connect(self._next)
        study_page.firstRequested.connect(self._first)
        study_page.lastRequested.connect(self._last)
        study_page.finishRequested.connect(self._finish_round)
        study_page.modeRequested.connect(self._set_mode)
        study_page.answerToggleRequested.connect(self._toggle_answer)
        study_page.speechRequested.connect(self._speak)
        study_page.starRatingRequested.connect(self._set_star_rating)
        study_page.quizChoiceRequested.connect(self._answer_quiz)
        study_page.relatedWordRequested.connect(self._open_related_word)

        word_list = self.window.word_list_page
        word_list.wordSelected.connect(
            lambda word: self._open_detail(word, "word_list")
        )
        word_list.starRatingRequested.connect(self._set_word_list_star)

        self.window.homeRequested.connect(self._show_home)
        self.window.wordListRequested.connect(self._open_word_list)
        self.window.findRequested.connect(self._find_home)
        self.window.closing.connect(self._handle_close)
        self.window.enable_close_guard()
        settings.voiceSelected.connect(self._select_voice)
        settings.rateChanged.connect(self._set_rate)
        settings.defaultModeChanged.connect(self._set_default_mode)
        settings.autoSpeakChanged.connect(self._set_auto_speak)
        settings.exportProgressRequested.connect(self._export_progress)
        settings.importProgressRequested.connect(self._import_progress)
        settings.cloudTokenChanged.connect(self._set_cloud_token)
        settings.cloudCreateCodeRequested.connect(self._create_cloud_code)
        settings.cloudUploadRequested.connect(self._upload_cloud_progress)
        settings.cloudDownloadRequested.connect(self._download_cloud_progress)
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
        self._all_words = self.content.list_by_ids(
            tuple(self.content.ids_in_source_order())
        )
        self._source_lists = tuple(self.content.source_lists())
        self._configure_settings()
        self.window.home_page.set_source_lists(
            self._source_lists,
            self.user.list_completion_counts(),
            selected_key=self.user.load_setting("study_list"),
        )
        saved_filter = self.user.load_setting("study_filter") or "all"
        if saved_filter.startswith("star:"):
            try:
                rating = int(saved_filter.removeprefix("star:"))
            except ValueError:
                rating = -1
            if 0 <= rating <= 3:
                self.window.home_page.set_selected_star_filter(rating)
        self._refresh_stats()
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

        self._auto_speak_enabled = (
            self.user.load_setting("auto_speak") == "1"
        )
        self.window.settings_dialog.set_auto_speak(
            self._auto_speak_enabled
        )
        self.window.settings_dialog.set_cloud_token(
            self.user.load_setting("cloud_token")
        )

        take_notice = getattr(self.speech, "take_availability_notice", None)
        if callable(take_notice):
            notice = take_notice()
            if notice:
                self._show_status(notice)

    def _refresh_stats(self) -> None:
        completion_counts = self.user.list_completion_counts()
        self.window.home_page.set_stats(
            total=self.content.count(),
            completed_rounds=sum(completion_counts.values()),
        )
        self.window.home_page.set_list_completion_counts(completion_counts)
        self._refresh_selected_list_counts()

    def _refresh_selected_list_counts(self, key: str | None = None) -> None:
        selected = key or self.window.home_page.selected_list_key()
        if selected is None:
            self.window.home_page.set_star_counts({})
            return
        try:
            word_ids = tuple(self.content.ids_for_section(selected))
        except KeyError:
            self.window.home_page.set_star_counts({})
            return
        self.window.home_page.set_star_counts(self.user.star_counts(word_ids))

    def _select_list(self, key: str) -> None:
        self.user.save_setting("study_list", str(key))
        self._refresh_selected_list_counts(str(key))
        self._report_persistence_issue()

    def _adjust_list_completion(self, key: str, delta: int) -> None:
        try:
            completed = self.user.adjust_list_completion(str(key), int(delta))
            source_list = self.content.source_list(str(key))
        except (KeyError, TypeError, ValueError) as error:
            LOGGER.exception("Unable to adjust List completion count")
            self._show_status(f"无法修改已背次数：{error}")
            return
        self._refresh_stats()
        self._show_status(f"{source_list.label} 已背次数：{completed}。")
        self._report_persistence_issue()

    def _word_list_rows(self) -> list[WordListRow]:
        machine7_lookup = getattr(self.content, "in_machine7", None)
        return [
            WordListRow(
                word=word,
                rating=self.user.star_rating(word.id),
                in_machine7=(
                    bool(machine7_lookup(word.id))
                    if callable(machine7_lookup)
                    else False
                ),
            )
            for word in self._all_words
        ]

    def _refresh_word_list(self) -> None:
        self.window.word_list_page.set_words(self._word_list_rows())

    def _show_home(self) -> None:
        self._detail_snapshot = None
        self._refresh_stats()
        self.window.show_home()

    def _open_word_list(self) -> None:
        self._detail_snapshot = None
        self._refresh_word_list()
        self.window.show_word_list()

    def _find_home(self) -> None:
        self._show_home()
        self.window.home_page.focus_search()

    def _search_home(self, query: str) -> None:
        self.window.home_page.set_results(self.search.search(query))

    def _open_list_study(
        self, source_section: str, star_rating: object
    ) -> None:
        rating = None if star_rating is None else int(star_rating)
        self._open_study(str(source_section), rating)

    def _open_study(
        self, source_section: str, star_rating: int | None = None
    ) -> None:
        try:
            snapshot = self.study.start(
                BrowseOrder.SOURCE,
                source_section=source_section,
                star_rating=star_rating,
            )
        except (KeyError, ValueError, RuntimeError) as error:
            LOGGER.exception("Unable to start study session")
            if star_rating is not None and "no words match" in str(error):
                self._show_status(
                    f"所选 List 中没有 {star_rating} 星单词。"
                )
            else:
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
        try:
            self._detail_snapshot = self.study.detail_snapshot(word, mode)
        except (KeyError, ValueError, RuntimeError) as error:
            LOGGER.exception("Unable to open vocabulary detail")
            self._show_status(f"无法打开单词详情：{error}")
            return
        self.window.study_page.render(self._detail_snapshot)
        self.window.show_study()

    def _open_related_word(self, word_id: int) -> None:
        origin = self._detail_origin if self._detail_snapshot is not None else "study"
        try:
            word = self.content.get(int(word_id))
        except (KeyError, TypeError, ValueError) as error:
            LOGGER.exception("Unable to open related vocabulary entry")
            self._show_status(f"无法打开相关词：{error}")
            return
        self._open_detail(word, origin)

    def _back_from_study(self) -> None:
        if (
            self._detail_snapshot is not None
            and self._detail_origin == "word_list"
        ):
            self._detail_snapshot = None
            self._refresh_word_list()
            self.window.show_word_list()
        elif (
            self._detail_snapshot is not None
            and self._detail_origin == "study"
        ):
            self._detail_snapshot = None
            self.window.study_page.render(self.study.current())
            self.window.show_study()
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
        elif self._auto_speak_enabled and snapshot.word.id != before.word.id:
            self._speak(snapshot.word.headword)
        self._refresh_stats()
        self._report_persistence_issue()

    def _first(self) -> None:
        if self._detail_snapshot is not None:
            return
        before = self.study.current()
        snapshot = self.study.first()
        self.window.study_page.render(snapshot)
        if snapshot.word.id != before.word.id and self._auto_speak_enabled:
            self._speak(snapshot.word.headword)
        self._refresh_stats()
        self._report_persistence_issue()

    def _last(self) -> None:
        if self._detail_snapshot is not None:
            return
        before = self.study.current()
        snapshot = self.study.last()
        self.window.study_page.render(snapshot)
        if snapshot.word.id != before.word.id and self._auto_speak_enabled:
            self._speak(snapshot.word.headword)
        self._refresh_stats()
        self._report_persistence_issue()

    def _finish_round(self) -> None:
        try:
            snapshot = self.study.current()
            completed = self.study.complete_round()
        except (KeyError, ValueError, RuntimeError) as error:
            LOGGER.exception("Unable to finish List round")
            self._show_status(f"无法完成本轮：{error}")
            return
        label = snapshot.list_label or snapshot.list_key or "所选 List"
        self._show_home()
        self._show_status(f"{label} 已完整学习 {completed} 次。")
        self._report_persistence_issue()

    def _set_mode(self, mode: StudyMode) -> None:
        if self._detail_snapshot is not None:
            if self._detail_snapshot.mode is mode:
                return
            try:
                self._detail_snapshot = self.study.detail_snapshot(
                    self._detail_snapshot.word,
                    mode,
                )
            except (KeyError, ValueError, RuntimeError) as error:
                LOGGER.exception("Unable to switch vocabulary detail mode")
                self._show_status(f"无法切换学习模式：{error}")
                return
            self.user.save_setting("study_mode", mode.value)
            self.window.study_page.render(self._detail_snapshot)
        else:
            try:
                self.window.study_page.render(self.study.set_mode(mode))
            except (KeyError, ValueError, RuntimeError) as error:
                LOGGER.exception("Unable to switch study mode")
                self._show_status(f"无法切换学习模式：{error}")
                return
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

    def _set_star_rating(self, star_rating: int) -> None:
        if self._detail_snapshot is not None:
            self.user.set_star_rating(
                self._detail_snapshot.word.id,
                int(star_rating),
            )
            self._detail_snapshot = replace(
                self._detail_snapshot,
                star_rating=int(star_rating),
            )
            self.window.study_page.render(self._detail_snapshot)
        else:
            self.window.study_page.render(
                self.study.set_star_rating(int(star_rating))
            )
        self._refresh_stats()
        if self.window.stack.currentWidget() is self.window.word_list_page:
            self._refresh_word_list()
        self._report_persistence_issue()

    def _answer_quiz(self, choice_index: int) -> None:
        try:
            if self._detail_snapshot is not None:
                self._detail_snapshot = self.study.answer_detail_quiz(
                    self._detail_snapshot,
                    int(choice_index),
                )
                snapshot = self._detail_snapshot
            else:
                snapshot = self.study.answer_quiz(int(choice_index))
        except (TypeError, ValueError, RuntimeError) as error:
            LOGGER.exception("Unable to record quiz answer")
            self._show_status(f"无法记录答案：{error}")
            return
        self.window.study_page.render(snapshot)

    def _set_word_list_star(self, word_id: int, star_rating: int) -> None:
        word_id = int(word_id)
        star_rating = int(star_rating)
        self.user.set_star_rating(word_id, star_rating)
        if not self.window.word_list_page.update_rating(word_id, star_rating):
            self._refresh_word_list()
        self._refresh_stats()
        self._report_persistence_issue()

    def _speak(self, headword: str) -> None:
        if not self.speech.speak(headword):
            self.window.study_page.set_speech_available(
                bool(self.speech.available)
            )
            self._show_status("当前没有可用的语音，朗读功能已禁用。")

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

    def _set_auto_speak(self, enabled: bool) -> None:
        self._auto_speak_enabled = bool(enabled)
        self.user.save_setting(
            "auto_speak", "1" if self._auto_speak_enabled else "0"
        )
        if self._auto_speak_enabled and not bool(self.speech.available):
            self._show_status("自动朗读已开启，但当前没有可用的语音引擎。")
        self._report_persistence_issue()

    def _reset_positions(self) -> None:
        active = None
        if (
            self._detail_snapshot is None
            and self.window.stack.currentWidget() is self.window.study_page
        ):
            active = self.study.current()
        self.user.reset_all_positions()
        self._show_status("学习位置已重置。")
        if active is not None and active.list_key is not None:
            self._open_study(active.list_key, active.star_filter)
        self._report_persistence_issue()

    def _export_progress(self) -> None:
        path, _selected_filter = QFileDialog.getSaveFileName(
            self.window.settings_dialog,
            "导出学习进度",
            "GRE-3000-学习进度.json",
            "JSON 文件 (*.json)",
        )
        if not path:
            return
        try:
            payload = export_progress(self.user, self.content)
            Path(path).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except (OSError, TypeError, ValueError) as error:
            LOGGER.exception("Unable to export progress")
            QMessageBox.warning(
                self.window.settings_dialog,
                "导出失败",
                f"无法导出学习进度：{error}",
            )
            return
        self._show_status("学习进度已导出，可在 iPhone 网页版中导入。")

    def _import_progress(self) -> None:
        path, _selected_filter = QFileDialog.getOpenFileName(
            self.window.settings_dialog,
            "导入学习进度",
            "",
            "JSON 文件 (*.json)",
        )
        if not path:
            return
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
            summary = import_progress(self.user, self.content, payload)
        except (OSError, json.JSONDecodeError, ProgressFormatError) as error:
            LOGGER.exception("Unable to import progress")
            QMessageBox.warning(
                self.window.settings_dialog,
                "导入失败",
                f"无法导入学习进度：{error}",
            )
            return
        self._detail_snapshot = None
        self._configure_settings()
        self.window.home_page.set_source_lists(
            self._source_lists,
            self.user.list_completion_counts(),
            selected_key=self.user.load_setting("study_list"),
        )
        self._refresh_stats()
        self._refresh_word_list()
        self.window.show_home()
        self._show_status(
            f"已导入 {summary.star_count} 个星级和 "
            f"{summary.list_count} 个 List 的进度。"
        )
        self._report_persistence_issue()

    def _set_cloud_token(self, token: str) -> None:
        self.user.save_setting("cloud_token", token.strip())
        self._report_persistence_issue()

    def _cloud_token(self) -> str:
        return (self.user.load_setting("cloud_token") or "").strip()

    def _create_cloud_code(self) -> None:
        code = create_sync_code()
        self.user.save_setting("cloud_token", code)
        self.window.settings_dialog.set_cloud_token(code)
        self.window.settings_dialog.reveal_cloud_token()
        self._show_status("新同步码已生成并选中，请复制保存，再上传本机进度。")
        self._report_persistence_issue()

    def _upload_cloud_progress(self) -> None:
        try:
            payload = export_progress(self.user, self.content)
            upload_progress(DEFAULT_CLOUD_ENDPOINT, self._cloud_token(), payload)
        except (CloudSyncError, TypeError, ValueError) as error:
            self._show_status(f"云同步上传失败：{error}")
            return
        self._show_status("本机学习进度已上传到云端。")

    def _download_cloud_progress(self) -> None:
        try:
            payload = download_progress(
                DEFAULT_CLOUD_ENDPOINT,
                self._cloud_token(),
            )
            if payload is None:
                self._show_status("云端还没有学习进度，请先上传一次。")
                return
            summary = import_progress(self.user, self.content, payload)
        except (CloudSyncError, ProgressFormatError, TypeError, ValueError) as error:
            self._show_status(f"云同步恢复失败：{error}")
            return
        self._detail_snapshot = None
        self._configure_settings()
        self.window.home_page.set_source_lists(
            self._source_lists,
            self.user.list_completion_counts(),
            selected_key=self.user.load_setting("study_list"),
        )
        self._refresh_stats()
        self._refresh_word_list()
        self.window.show_home()
        self._show_status(
            f"已从云端恢复 {summary.star_count} 个星级和 "
            f"{summary.list_count} 个 List 的进度。"
        )

    def _clear_all(self) -> None:
        self._show_status("本地星级、List 完成次数、进度和设置已清空。")
        self.user.clear_all()
        self._detail_snapshot = None
        self._configure_settings()
        self.window.home_page.set_source_lists(
            self._source_lists,
            self.user.list_completion_counts(),
        )
        self._refresh_stats()
        self._refresh_word_list()
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
