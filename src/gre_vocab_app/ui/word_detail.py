from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from gre_vocab_app.domain import RelatedWord, RootFamily, StudyMode, WordEntry

from .lookup_label import LookupLabel


class WordDetail(QWidget):
    speechRequested = Signal(str)
    revealRequested = Signal()
    quizChoiceRequested = Signal(int)
    relatedWordRequested = Signal(int)
    lookupRequested = Signal(str)
    selectionTranslationRequested = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._word: WordEntry | None = None
        self._mode = StudyMode.READING
        self._revealed = True
        self._speech_available = True
        self._quiz_choices: tuple[str, ...] = ()
        self._quiz_correct_index: int | None = None
        self._quiz_selected_index: int | None = None
        self._root_families: tuple[RootFamily, ...] = ()
        self._lookalikes: tuple[RelatedWord, ...] = ()
        self._equivalents: tuple[RelatedWord, ...] = ()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content = QWidget()
        content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        root = QVBoxLayout(content)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(15)
        root.setSizeConstraint(QLayout.SetMinAndMaxSize)

        word_card = QWidget(objectName="wordCard")
        word_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        word_layout = QVBoxLayout(word_card)
        word_layout.setContentsMargins(26, 21, 26, 21)
        word_layout.setSpacing(8)
        title_row = QHBoxLayout()
        self.headword_label = self._lookup_label(object_name="headword")
        self.headword_label.setAccessibleName("单词")
        title_row.addWidget(self.headword_label, 1)
        self.machine7_badge = QLabel("机经 7.0 重点词")
        self.machine7_badge.setObjectName("sourceBadge")
        self.machine7_badge.setAccessibleName("本词收录于 GRE 镇考机经词 7.0")
        self.machine7_badge.setToolTip("此词同时收录于《GRE 镇考机经词 7.0》")
        self.machine7_badge.hide()
        title_row.addWidget(self.machine7_badge)
        self.speech_button = QPushButton("朗读")
        self.speech_button.setObjectName("outlineButton")
        self.speech_button.setMinimumHeight(40)
        self.speech_button.setAccessibleName("朗读当前单词")
        self.speech_button.setEnabled(False)
        self.speech_button.clicked.connect(self._request_speech)
        title_row.addWidget(self.speech_button)
        word_layout.addLayout(title_row)
        self.phonetic_label = self._label(object_name="phonetic")
        word_layout.addWidget(self.phonetic_label)
        root.addWidget(word_card)

        self.reveal_button = QPushButton("点击显示简义")
        self.reveal_button.setObjectName("revealButton")
        self.reveal_button.setMinimumHeight(48)
        self.reveal_button.setAccessibleName("显示或隐藏简义")
        self.reveal_button.setFocusPolicy(Qt.StrongFocus)
        self.reveal_button.clicked.connect(self.revealRequested.emit)
        self.reveal_button.hide()
        root.addWidget(self.reveal_button)

        self.quiz_panel = QWidget(objectName="meaningPanel")
        self.quiz_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        quiz_layout = QVBoxLayout(self.quiz_panel)
        quiz_layout.setContentsMargins(24, 20, 24, 22)
        quiz_layout.setSpacing(9)
        self.quiz_title = self._section_title("请选择正确词义")
        quiz_layout.addWidget(self.quiz_title)
        self.quiz_buttons: list[QPushButton] = []
        for index in range(4):
            button = QPushButton()
            button.setFocusPolicy(Qt.StrongFocus)
            button.setAccessibleName(f"词义选项 {index + 1}")
            button.clicked.connect(
                lambda _checked=False, choice=index: self._request_quiz_choice(choice)
            )
            self.quiz_buttons.append(button)
            quiz_layout.addWidget(button)
        self.quiz_feedback_label = self._label(object_name="sectionTitle")
        self.quiz_feedback_label.setAccessibleName("答题结果")
        quiz_layout.addWidget(self.quiz_feedback_label)
        self.quiz_panel.hide()
        root.addWidget(self.quiz_panel)

        self.meaning_panel = QWidget(objectName="meaningPanel")
        self.meaning_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        meaning_layout = QVBoxLayout(self.meaning_panel)
        meaning_layout.setContentsMargins(26, 21, 26, 23)
        meaning_layout.setSpacing(9)

        self.definition_label = self._lookup_label(object_name="definition")
        self.definition_zh_label = self._label()
        meaning_layout.addWidget(self.definition_label)
        meaning_layout.addWidget(self.definition_zh_label)

        self.synonyms_title = self._section_title("近义词")
        self.synonyms_label = self._lookup_label()
        meaning_layout.addSpacing(5)
        meaning_layout.addWidget(self.synonyms_title)
        meaning_layout.addWidget(self.synonyms_label)

        self.example_title = self._section_title("例句")
        self.example_en_label = self._lookup_label()
        self.example_zh_label = self._label(object_name="muted")
        meaning_layout.addSpacing(5)
        meaning_layout.addWidget(self.example_title)
        meaning_layout.addWidget(self.example_en_label)
        meaning_layout.addWidget(self.example_zh_label)
        root.addWidget(self.meaning_panel)

        self.equivalent_panel, self.equivalent_relations_layout = (
            self._relation_panel("真经 GRE 等价词（双向）")
        )
        root.addWidget(self.equivalent_panel)
        self.root_panel, self.root_relations_layout = self._relation_panel(
            "同词根 / 同族词（词库内）"
        )
        root.addWidget(self.root_panel)
        self.lookalike_panel, self.lookalike_relations_layout = self._relation_panel(
            "易混淆近形词（拼写相近、词义不同）"
        )
        root.addWidget(self.lookalike_panel)
        root.addStretch(1)
        self.scroll_area.setWidget(content)
        outer.addWidget(self.scroll_area)

    @staticmethod
    def _label(*, object_name: str = "") -> QLabel:
        label = QLabel()
        if object_name:
            label.setObjectName(object_name)
        label.setWordWrap(True)
        label.setTextInteractionFlags(
            Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard
        )
        return label

    @classmethod
    def _section_title(cls, text: str) -> QLabel:
        label = cls._label(object_name="sectionTitle")
        label.setText(text)
        return label

    def _lookup_label(self, *, object_name: str = "") -> LookupLabel:
        label = LookupLabel()
        if object_name:
            label.setObjectName(object_name)
        label.lookupRequested.connect(self.lookupRequested.emit)
        label.selectionTranslationRequested.connect(
            self.selectionTranslationRequested.emit
        )
        return label

    @classmethod
    def _relation_panel(cls, title: str) -> tuple[QWidget, QVBoxLayout]:
        panel = QWidget(objectName="meaningPanel")
        panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 18, 24, 20)
        layout.setSpacing(7)
        layout.addWidget(cls._section_title(title))
        relations = QVBoxLayout()
        relations.setSpacing(6)
        layout.addLayout(relations)
        panel.hide()
        return panel, relations

    def set_word(
        self,
        word: WordEntry,
        *,
        mode: StudyMode = StudyMode.READING,
        answer_visible: bool = False,
        quiz_choices: tuple[str, ...] = (),
        quiz_correct_index: int | None = None,
        quiz_selected_index: int | None = None,
        root_families: tuple[RootFamily, ...] = (),
        lookalikes: tuple[RelatedWord, ...] = (),
        equivalents: tuple[RelatedWord, ...] = (),
        in_machine7: bool = False,
    ) -> None:
        self._word = word
        self._mode = StudyMode(mode)
        self._root_families = tuple(root_families)
        self._lookalikes = tuple(lookalikes)
        self._equivalents = tuple(equivalents)
        for label in (
            self.headword_label,
            self.phonetic_label,
            self.definition_label,
            self.definition_zh_label,
            self.synonyms_label,
            self.example_en_label,
            self.example_zh_label,
        ):
            label.clear()

        self.headword_label.set_lookup_text(word.headword)
        self.machine7_badge.setVisible(bool(in_machine7))
        self.phonetic_label.setText(word.phonetic)
        self.definition_label.set_lookup_text(word.definition_en)
        self.definition_zh_label.setText(word.definition_zh)
        self.synonyms_label.set_lookup_text(word.synonyms)
        self.example_en_label.set_lookup_text(word.example_en)
        self.example_zh_label.setText(word.example_zh)

        self.phonetic_label.setVisible(bool(word.phonetic))
        self.definition_label.setVisible(bool(word.definition_en))
        self.definition_zh_label.setVisible(bool(word.definition_zh))
        has_synonyms = bool(word.synonyms)
        self.synonyms_title.setVisible(has_synonyms)
        self.synonyms_label.setVisible(has_synonyms)
        has_example = bool(word.example_en or word.example_zh)
        self.example_title.setVisible(has_example)
        self.example_en_label.setVisible(bool(word.example_en))
        self.example_zh_label.setVisible(bool(word.example_zh))
        self.speech_button.setEnabled(
            self._speech_available and bool(word.headword)
        )
        self._populate_root_relations()
        self._populate_related_words(
            self.equivalent_relations_layout, self._equivalents
        )
        self._populate_related_words(
            self.lookalike_relations_layout, self._lookalikes
        )
        self._render_mode(
            answer_visible=answer_visible,
            quiz_choices=quiz_choices,
            quiz_correct_index=quiz_correct_index,
            quiz_selected_index=quiz_selected_index,
        )

    def _render_mode(
        self,
        *,
        answer_visible: bool,
        quiz_choices: tuple[str, ...],
        quiz_correct_index: int | None,
        quiz_selected_index: int | None,
    ) -> None:
        brief = self._mode in (StudyMode.BRIEF, StudyMode.RECALL)
        self.synonyms_title.setVisible(not brief and bool(self.synonyms_label.text()))
        self.synonyms_label.setVisible(not brief and bool(self.synonyms_label.text()))
        has_example = bool(self.example_en_label.text() or self.example_zh_label.text())
        self.example_title.setVisible(not brief and has_example)
        self.example_en_label.setVisible(not brief and bool(self.example_en_label.text()))
        self.example_zh_label.setVisible(not brief and bool(self.example_zh_label.text()))

        recall = self._mode is StudyMode.RECALL
        quiz = self._mode is StudyMode.QUIZ
        self.reveal_button.setVisible(recall)
        self.quiz_panel.setVisible(quiz)
        if quiz:
            self.set_revealed(False)
            self._render_quiz(
                quiz_choices,
                correct_index=quiz_correct_index,
                selected_index=quiz_selected_index,
            )
        else:
            self._clear_quiz()
            self.set_revealed(answer_visible if recall else True)

    def _clear_quiz(self) -> None:
        self._quiz_choices = ()
        self._quiz_correct_index = None
        self._quiz_selected_index = None
        self.quiz_feedback_label.clear()
        self.quiz_feedback_label.hide()
        for button in self.quiz_buttons:
            button.setText("")
            button.hide()
            button.setEnabled(False)
            self._set_button_style(button, "")
        self._update_relation_visibility()

    def _render_quiz(
        self,
        choices: tuple[str, ...],
        *,
        correct_index: int | None,
        selected_index: int | None,
    ) -> None:
        self._quiz_choices = tuple(choices[:4])
        self._quiz_correct_index = correct_index
        answered = selected_index is not None
        self._quiz_selected_index = selected_index if answered else None
        valid_correct = (
            correct_index
            if answered
            and correct_index is not None
            and 0 <= correct_index < len(self._quiz_choices)
            else None
        )
        valid_selected = (
            selected_index
            if answered
            and selected_index is not None
            and 0 <= selected_index < len(self._quiz_choices)
            else None
        )

        for index, button in enumerate(self.quiz_buttons):
            if index >= len(self._quiz_choices):
                button.setText("")
                button.hide()
                button.setEnabled(False)
                self._set_button_style(button, "")
                continue
            choice = self._quiz_choices[index]
            text = choice
            style_name = ""
            if answered and index == valid_correct:
                text = (
                    f"✓ 回答正确：{choice}"
                    if valid_selected == valid_correct
                    else f"✓ 正确答案：{choice}"
                )
                style_name = "primaryButton"
            elif answered and index == valid_selected:
                text = f"✗ 你的选择：{choice}"
                style_name = "dangerButton"
            button.setText(text)
            button.setAccessibleName(f"词义选项 {index + 1}：{text}")
            button.setEnabled(not answered)
            button.show()
            self._set_button_style(button, style_name)

        if answered and valid_selected is not None and valid_correct is not None:
            correct = valid_selected == valid_correct
            self.quiz_feedback_label.setText(
                "回答正确"
                if correct
                else "回答错误，正确答案已标出"
            )
            self.quiz_feedback_label.show()
        else:
            self.quiz_feedback_label.clear()
            self.quiz_feedback_label.hide()
        self._update_relation_visibility()

    @staticmethod
    def _set_button_style(button: QPushButton, object_name: str) -> None:
        if button.objectName() == object_name:
            return
        button.setObjectName(object_name)
        style = button.style()
        style.unpolish(button)
        style.polish(button)

    def _request_quiz_choice(self, index: int) -> None:
        if (
            self._mode is StudyMode.QUIZ
            and self._quiz_selected_index is None
            and 0 <= index < len(self._quiz_choices)
        ):
            self._render_quiz(
                self._quiz_choices,
                correct_index=self._quiz_correct_index,
                selected_index=index,
            )
            self.quizChoiceRequested.emit(index)

    def set_revealed(self, revealed: bool) -> None:
        self._revealed = bool(revealed)
        self.meaning_panel.setVisible(self._revealed)
        self.reveal_button.setText(
            "隐藏简义" if self._revealed else "点击显示简义"
        )
        self._update_relation_visibility()

    def is_revealed(self) -> bool:
        return self._revealed

    def set_speech_available(self, available: bool) -> None:
        self._speech_available = bool(available)
        self.speech_button.setEnabled(
            self._speech_available
            and self._word is not None
            and bool(self._word.headword)
        )

    def _request_speech(self) -> None:
        if (
            self._speech_available
            and self._word is not None
            and self._word.headword
        ):
            self.speechRequested.emit(self._word.headword)

    @staticmethod
    def _clear_relation_layout(layout: QVBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _relation_button(self, related: RelatedWord) -> QPushButton:
        text = related.headword
        if related.definition:
            text += f"    {related.definition}"
        button = QPushButton(text)
        button.setObjectName("relationButton")
        button.setAccessibleName(f"打开相关词 {related.headword}")
        button.setToolTip(related.definition)
        button.setCursor(Qt.PointingHandCursor)
        button.clicked.connect(
            lambda _checked=False, word_id=related.word_id: (
                self.relatedWordRequested.emit(word_id)
            )
        )
        return button

    def _populate_related_words(
        self,
        layout: QVBoxLayout,
        words: tuple[RelatedWord, ...],
    ) -> None:
        self._clear_relation_layout(layout)
        for related in words:
            layout.addWidget(self._relation_button(related))

    def _populate_root_relations(self) -> None:
        self._clear_relation_layout(self.root_relations_layout)
        for family in self._root_families:
            root_label = self._section_title(f"词根：{family.root}")
            self.root_relations_layout.addWidget(root_label)
            for related in family.words:
                self.root_relations_layout.addWidget(
                    self._relation_button(related)
                )

    def _update_relation_visibility(self) -> None:
        if self._mode is StudyMode.RECALL:
            allowed = self._revealed
        elif self._mode is StudyMode.QUIZ:
            allowed = self._quiz_selected_index is not None
        else:
            allowed = True
        self.root_panel.setVisible(allowed and bool(self._root_families))
        self.lookalike_panel.setVisible(allowed and bool(self._lookalikes))
        self.equivalent_panel.setVisible(allowed and bool(self._equivalents))
