from __future__ import annotations

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtGui import QKeyEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QButtonGroup,
    QComboBox,
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
    previousRequested = Signal()
    nextRequested = Signal()
    modeRequested = Signal(object)
    answerToggleRequested = Signal()
    speechRequested = Signal(str)
    favoriteRequested = Signal(bool)
    reshuffleRequested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("appSurface")
        self.snapshot: SessionSnapshot | None = None
        self._speech_available = True
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 22, 28, 24)
        root.setSpacing(13)

        top = QHBoxLayout()
        self.back_button = QPushButton("返回")
        self.position_label = QLabel("0 / 0")
        self.position_label.setObjectName("sectionTitle")
        top.addWidget(self.back_button)
        top.addWidget(self.position_label)
        top.addStretch(1)

        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        self.reading_button = QPushButton("阅读模式")
        self.recall_button = QPushButton("回忆模式")
        for button in (self.reading_button, self.recall_button):
            button.setCheckable(True)
            self.mode_group.addButton(button)
            top.addWidget(button)
        self.reading_button.setChecked(True)
        self.favorite_button = QPushButton("收藏")
        self.favorite_button.setCheckable(True)
        top.addWidget(self.favorite_button)
        root.addLayout(top)

        self.word_detail = WordDetail()
        root.addWidget(self.word_detail, 1)

        navigation = QHBoxLayout()
        self.previous_button = QPushButton("上一词")
        self.reshuffle_button = QPushButton("重新洗牌")
        self.next_button = QPushButton("下一词")
        self.next_button.setObjectName("primaryButton")
        navigation.addWidget(self.previous_button)
        navigation.addStretch(1)
        navigation.addWidget(self.reshuffle_button)
        navigation.addWidget(self.next_button)
        root.addLayout(navigation)

        self.back_button.clicked.connect(self.backRequested.emit)
        self.previous_button.clicked.connect(self.previousRequested.emit)
        self.next_button.clicked.connect(self.nextRequested.emit)
        self.reshuffle_button.clicked.connect(self.reshuffleRequested.emit)
        self.reading_button.clicked.connect(
            lambda checked: checked and self.modeRequested.emit(StudyMode.READING)
        )
        self.recall_button.clicked.connect(
            lambda checked: checked and self.modeRequested.emit(StudyMode.RECALL)
        )
        self.favorite_button.clicked.connect(
            lambda checked: self.favoriteRequested.emit(bool(checked))
        )
        self.word_detail.speechRequested.connect(self.speechRequested.emit)
        self.word_detail.revealRequested.connect(self.answerToggleRequested.emit)

        self.previous_shortcut = self._shortcut(Qt.Key_Left, self._previous)
        self.next_shortcut = self._shortcut(Qt.Key_Right, self._next)
        self.speech_shortcut = self._shortcut(Qt.Key_P, self._speak)
        self.favorite_shortcut = self._shortcut(Qt.Key_S, self._toggle_favorite)
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
        self.position_label.setText(f"{snapshot.index + 1:,} / {snapshot.total:,}")
        self.previous_button.setEnabled(not snapshot.at_start)
        self.next_button.setEnabled(not snapshot.at_end)
        self.reshuffle_button.setVisible(snapshot.order.value == "random")
        with QSignalBlocker(self.reading_button), QSignalBlocker(self.recall_button):
            self.reading_button.setChecked(snapshot.mode is StudyMode.READING)
            self.recall_button.setChecked(snapshot.mode is StudyMode.RECALL)
        with QSignalBlocker(self.favorite_button):
            self.favorite_button.setChecked(snapshot.favorite)
        self.favorite_button.setText("已收藏" if snapshot.favorite else "收藏")
        reveal = snapshot.mode is StudyMode.READING or snapshot.answer_visible
        self.word_detail.set_word(
            snapshot.word,
            reveal=reveal,
            recall=snapshot.mode is StudyMode.RECALL,
        )
        self._sync_shortcut_state()

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
        self.favorite_shortcut.setEnabled(active)
        self.speech_shortcut.setEnabled(active and self._speech_available)
        recall = self.snapshot is not None and self.snapshot.mode is StudyMode.RECALL
        self.answer_shortcut.setEnabled(active and recall)

    def _previous(self) -> None:
        if self.snapshot is not None and not self._focus_uses_native_keys():
            self.previousRequested.emit()

    def _next(self) -> None:
        if self.snapshot is not None and not self._focus_uses_native_keys():
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

    def _toggle_favorite(self) -> None:
        if self.snapshot is not None and not self._focus_uses_native_keys():
            self.favoriteRequested.emit(not self.snapshot.favorite)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self._focus_uses_native_keys():
            super().keyPressEvent(event)
            return
        handlers = {
            Qt.Key_Left: self._previous,
            Qt.Key_Right: self._next,
            Qt.Key_S: self._toggle_favorite,
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
