from __future__ import annotations

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtGui import QKeyEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QButtonGroup,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from gre_vocab_app.domain import SessionSnapshot, StudyMode

from .word_detail import WordDetail


class StudyPage(QWidget):
    backRequested = Signal()
    findRequested = Signal()
    previousRequested = Signal()
    nextRequested = Signal()
    finishRequested = Signal()
    modeRequested = Signal(object)
    answerToggleRequested = Signal()
    speechRequested = Signal(str)
    starRatingRequested = Signal(int)
    quizChoiceRequested = Signal(int)
    relatedWordRequested = Signal(int)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("appSurface")
        self.snapshot: SessionSnapshot | None = None
        self._speech_available = True
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 20, 28, 22)
        root.setSpacing(14)

        study_header = QFrame(objectName="studyHeader")
        top = QHBoxLayout(study_header)
        top.setContentsMargins(12, 10, 12, 10)
        top.setSpacing(7)
        self.back_button = QPushButton("返回")
        self.back_button.setObjectName("backButton")
        self.back_button.setMinimumHeight(40)
        self.position_label = QLabel("0 / 0")
        self.position_label.setObjectName("positionPill")
        top.addWidget(self.back_button)
        top.addWidget(self.position_label)
        top.addStretch(1)

        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        self.reading_button = QPushButton("阅读模式")
        self.brief_button = QPushButton("简义模式")
        self.recall_button = QPushButton("回忆模式")
        self.quiz_button = QPushButton("四选一")
        for button in (
            self.reading_button,
            self.brief_button,
            self.recall_button,
            self.quiz_button,
        ):
            button.setCheckable(True)
            button.setObjectName("modeButton")
            button.setMinimumHeight(40)
            self.mode_group.addButton(button)
            top.addWidget(button)
        self.reading_button.setChecked(True)
        self.star_button = QPushButton("☆☆☆")
        self.star_button.setObjectName("starButton")
        self.star_button.setMinimumHeight(40)
        self.star_button.setAccessibleName("星级评分，当前 0 星，点击设为 1 星")
        self.star_button.setToolTip("点击循环标注星级：0 → 1 → 2 → 3 → 0")
        top.addWidget(self.star_button)
        root.addWidget(study_header)

        self.word_detail = WordDetail()
        root.addWidget(self.word_detail, 1)

        navigation_bar = QFrame(objectName="navigationBar")
        navigation = QHBoxLayout(navigation_bar)
        navigation.setContentsMargins(12, 10, 12, 10)
        self.previous_button = QPushButton("上一词")
        self.next_button = QPushButton("下一词")
        self.next_button.setObjectName("primaryButton")
        self.previous_button.setMinimumSize(112, 42)
        self.next_button.setMinimumSize(112, 42)
        shortcut_hint = QLabel("← / → 切换 · P 朗读 · Space 揭示")
        shortcut_hint.setObjectName("sectionHint")
        navigation.addWidget(self.previous_button)
        navigation.addStretch(1)
        navigation.addWidget(shortcut_hint)
        navigation.addStretch(1)
        navigation.addWidget(self.next_button)
        root.addWidget(navigation_bar)

        self.back_button.clicked.connect(self.backRequested.emit)
        self.previous_button.clicked.connect(self.previousRequested.emit)
        self.next_button.clicked.connect(self._next)
        self.reading_button.clicked.connect(
            lambda checked: self._request_mode(StudyMode.READING, checked)
        )
        self.brief_button.clicked.connect(
            lambda checked: self._request_mode(StudyMode.BRIEF, checked)
        )
        self.recall_button.clicked.connect(
            lambda checked: self._request_mode(StudyMode.RECALL, checked)
        )
        self.quiz_button.clicked.connect(
            lambda checked: self._request_mode(StudyMode.QUIZ, checked)
        )
        self.star_button.clicked.connect(self._request_next_star_rating)
        self.word_detail.speechRequested.connect(self.speechRequested.emit)
        self.word_detail.revealRequested.connect(self.answerToggleRequested.emit)
        self.word_detail.quizChoiceRequested.connect(
            self.quizChoiceRequested.emit
        )
        self.word_detail.relatedWordRequested.connect(
            self.relatedWordRequested.emit
        )

        self.previous_shortcut = self._shortcut(Qt.Key_Left, self._previous)
        self.next_shortcut = self._shortcut(Qt.Key_Right, self._next)
        self.speech_shortcut = self._shortcut(Qt.Key_P, self._speak)
        self.answer_shortcut = self._shortcut(Qt.Key_Space, self._toggle_answer)
        application = QApplication.instance()
        if application is not None:
            application.focusChanged.connect(self._sync_shortcut_state)
        self._sync_shortcut_state()

    def _shortcut(self, key: Qt.Key, callback) -> QShortcut:
        shortcut = QShortcut(QKeySequence(key), self)
        shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        shortcut.activated.connect(callback)
        return shortcut

    def render(self, snapshot: SessionSnapshot) -> None:
        self.snapshot = snapshot
        prefix = f"{snapshot.list_label} · " if snapshot.list_label else ""
        self.position_label.setText(
            f"{prefix}{snapshot.index + 1:,} / {snapshot.total:,}"
        )
        self.previous_button.setEnabled(not snapshot.at_start)
        if snapshot.can_complete_round:
            self.next_button.setText("完成本轮")
            self.next_button.setAccessibleName("完成本轮 List 学习")
            self.next_button.setEnabled(True)
        else:
            self.next_button.setText("下一词")
            self.next_button.setAccessibleName("下一词")
            self.next_button.setEnabled(not snapshot.at_end)
        with (
            QSignalBlocker(self.reading_button),
            QSignalBlocker(self.brief_button),
            QSignalBlocker(self.recall_button),
            QSignalBlocker(self.quiz_button),
        ):
            self.reading_button.setChecked(snapshot.mode is StudyMode.READING)
            self.brief_button.setChecked(snapshot.mode is StudyMode.BRIEF)
            self.recall_button.setChecked(snapshot.mode is StudyMode.RECALL)
            self.quiz_button.setChecked(snapshot.mode is StudyMode.QUIZ)
        self._render_star_rating(snapshot.star_rating)
        self.word_detail.set_word(
            snapshot.word,
            mode=snapshot.mode,
            answer_visible=snapshot.answer_visible,
            quiz_choices=snapshot.quiz_choices,
            quiz_correct_index=snapshot.quiz_correct_index,
            quiz_selected_index=snapshot.quiz_selected_index,
            root_families=snapshot.root_families,
            lookalikes=snapshot.lookalikes,
            equivalents=snapshot.equivalents,
            in_machine7=snapshot.in_machine7,
        )
        self._sync_shortcut_state()

    @staticmethod
    def _star_text(rating: int) -> str:
        value = max(0, min(3, int(rating)))
        return "★" * value + "☆" * (3 - value)

    def _render_star_rating(self, rating: int) -> None:
        value = max(0, min(3, int(rating)))
        next_value = (value + 1) % 4
        self.star_button.setText(self._star_text(value))
        self.star_button.setProperty("rated", value > 0)
        style = self.star_button.style()
        style.unpolish(self.star_button)
        style.polish(self.star_button)
        self.star_button.setAccessibleName(
            f"星级评分，当前 {value} 星，点击设为 {next_value} 星"
        )
        self.star_button.setToolTip(
            f"当前 {value} 星；点击改为 {next_value} 星（3 星后回到 0 星）"
        )

    def _request_next_star_rating(self) -> None:
        if self.snapshot is not None:
            current = max(0, min(3, int(self.snapshot.star_rating)))
            self.starRatingRequested.emit((current + 1) % 4)

    def _request_mode(self, mode: StudyMode, checked: bool) -> None:
        if (
            checked
            and (self.snapshot is None or self.snapshot.mode is not mode)
        ):
            self.modeRequested.emit(mode)

    def _focus_uses_native_keys(self) -> bool:
        focus = QApplication.focusWidget()
        if focus is None or not self.isAncestorOf(focus):
            return False
        if isinstance(
            focus, (QLineEdit, QTextEdit, QPlainTextEdit, QAbstractSpinBox, QComboBox)
        ):
            return True
        text_interaction_flags = getattr(focus, "textInteractionFlags", None)
        return callable(text_interaction_flags) and bool(
            text_interaction_flags() & Qt.TextSelectableByKeyboard
        )

    def _sync_shortcut_state(self, *_focus_widgets: QWidget | None) -> None:
        active = self.snapshot is not None and not self._focus_uses_native_keys()
        self.previous_shortcut.setEnabled(active)
        self.next_shortcut.setEnabled(active)
        self.speech_shortcut.setEnabled(active and self._speech_available)
        recall = self.snapshot is not None and self.snapshot.mode is StudyMode.RECALL
        self.answer_shortcut.setEnabled(active and recall)

    def _previous(self) -> None:
        if self.snapshot is not None and not self._focus_uses_native_keys():
            self.previousRequested.emit()

    def _next(self) -> None:
        if self.snapshot is not None and not self._focus_uses_native_keys():
            if self.snapshot.can_complete_round:
                self.finishRequested.emit()
            elif not self.snapshot.at_end:
                self.nextRequested.emit()

    def _toggle_answer(self) -> None:
        if (
            self.snapshot is not None
            and self.snapshot.mode is StudyMode.RECALL
            and not self._focus_uses_native_keys()
        ):
            self.answerToggleRequested.emit()

    def _speak(self) -> None:
        if (
            self._speech_available
            and self.snapshot is not None
            and not self._focus_uses_native_keys()
        ):
            self.speechRequested.emit(self.snapshot.word.headword)

    def set_speech_available(self, available: bool) -> None:
        self._speech_available = bool(available)
        self._sync_shortcut_state()
        self.word_detail.set_speech_available(self._speech_available)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if (
            event.key() == Qt.Key_F
            and event.modifiers() == Qt.ControlModifier
        ):
            self.findRequested.emit()
            event.accept()
            return
        if self._focus_uses_native_keys():
            super().keyPressEvent(event)
            return
        handlers = {
            Qt.Key_Left: self._previous,
            Qt.Key_Right: self._next,
        }
        if self._speech_available:
            handlers[Qt.Key_P] = self._speak
        if self.snapshot is not None and self.snapshot.mode is StudyMode.RECALL:
            handlers[Qt.Key_Space] = self._toggle_answer
        handler = handlers.get(event.key())
        if handler is not None and event.modifiers() == Qt.NoModifier:
            handler()
            event.accept()
            return
        super().keyPressEvent(event)
