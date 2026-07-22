from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gre_vocab_app.domain import WordEntry


@dataclass(frozen=True, slots=True)
class WordListRow:
    """One complete-word-list row plus its star rating."""

    word: WordEntry
    rating: int
    in_machine7: bool = False

    def __post_init__(self) -> None:
        if type(self.rating) is not int or not 0 <= self.rating <= 3:
            raise ValueError("rating must be an integer from 0 through 3")


class WordListPage(QWidget):
    wordSelected = Signal(object)
    starRatingRequested = Signal(int, int)
    searchRequested = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("appSurface")
        self._rows: list[WordListRow] = []
        self._selected_word_id: int | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(36, 27, 36, 28)
        root.setSpacing(15)

        header_row = QHBoxLayout()
        header_copy = QVBoxLayout()
        header_copy.setSpacing(4)
        eyebrow = QLabel("VOCABULARY LIBRARY")
        eyebrow.setObjectName("eyebrow")
        title = QLabel("完整词表")
        title.setObjectName("pageTitle")
        subtitle = QLabel("按原书顺序浏览；单词只保留 0–3 星标注。")
        subtitle.setObjectName("muted")
        header_copy.addWidget(eyebrow)
        header_copy.addWidget(title)
        header_copy.addWidget(subtitle)
        header_row.addLayout(header_copy)
        header_row.addStretch(1)
        self.count_label = QLabel("0 词")
        self.count_label.setObjectName("countBadge")
        header_row.addWidget(self.count_label, 0, Qt.AlignBottom)
        root.addLayout(header_row)

        self.search_edit = QLineEdit()
        self.search_edit.setObjectName("largeSearch")
        self.search_edit.setPlaceholderText("筛选单词、释义、List 或机经 7.0 重点词")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._on_search_changed)
        root.addWidget(self.search_edit)

        self.empty_state = QLabel("词表为空。")
        self.empty_state.setObjectName("emptyState")
        self.empty_state.setAlignment(Qt.AlignCenter)
        self.empty_state.hide()
        root.addWidget(self.empty_state)

        self.words_table = QTableWidget(0, 6)
        self.words_table.setHorizontalHeaderLabels(
            ("序号", "List", "单词", "机经 7.0", "简义", "星级")
        )
        self.words_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.words_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.words_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.words_table.setAlternatingRowColors(True)
        self.words_table.setSortingEnabled(False)
        self.words_table.setShowGrid(False)
        self.words_table.verticalHeader().hide()
        self.words_table.verticalHeader().setDefaultSectionSize(42)
        header = self.words_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.words_table.itemActivated.connect(self._emit_selected_item)
        self.words_table.currentCellChanged.connect(self._on_current_changed)
        root.addWidget(self.words_table, 1)

        actions_bar = QFrame(objectName="navigationBar")
        actions = QHBoxLayout(actions_bar)
        actions.setContentsMargins(12, 9, 12, 9)
        actions.addStretch(1)
        self.open_button = QPushButton("打开词条")
        self.open_button.setObjectName("primaryButton")
        self.star_button = QPushButton("星级 +1")
        self.star_button.setObjectName("outlineButton")
        self.open_button.setMinimumHeight(40)
        self.star_button.setMinimumHeight(40)
        self.open_button.clicked.connect(self._open_current)
        self.star_button.clicked.connect(self._advance_star)
        actions.addWidget(self.open_button)
        actions.addWidget(self.star_button)
        root.addWidget(actions_bar)
        self._update_actions()

    def set_words(self, rows: Sequence[WordListRow]) -> None:
        """Replace rows, sorted by source order, while preserving filter/selection."""

        current = self._current_row_data()
        if current is not None:
            self._selected_word_id = current.word.id
        self._rows = sorted(rows, key=lambda row: row.word.source_order)

        # Rebuilding a populated, visible QTableWidget can repeatedly trigger
        # ResizeToContents layout work. Keep it hidden until the new model and
        # row visibility are complete; routine annotation edits use the
        # incremental path below and do not rebuild at all.
        was_explicitly_hidden = self.words_table.isHidden()
        had_focus = (
            self.words_table.hasFocus()
            or self.words_table.viewport().hasFocus()
        )
        self.words_table.hide()
        self.words_table.setUpdatesEnabled(False)
        self.words_table.blockSignals(True)
        try:
            self.words_table.clearContents()
            self.words_table.setRowCount(len(self._rows))
            for row_index, row in enumerate(self._rows):
                summary = self._summary(row.word)
                values = (
                    str(row.word.source_order),
                    self._section_label(row.word.source_section),
                    row.word.headword,
                    "重点" if row.in_machine7 else "",
                    summary,
                    f"{row.rating} 星",
                )
                for column, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    if column == 0:
                        item.setData(Qt.UserRole, row)
                    if column in (0, 1, 3, 5):
                        item.setTextAlignment(Qt.AlignCenter)
                    if column in (2, 4):
                        item.setToolTip(summary)
                    if column == 3 and row.in_machine7:
                        font = item.font()
                        font.setBold(True)
                        item.setFont(font)
                        item.setForeground(QColor("#c2410c"))
                        item.setToolTip("同时收录于《GRE 镇考机经词 7.0》")
                    self.words_table.setItem(row_index, column, item)
        finally:
            self.words_table.blockSignals(False)
            self.words_table.setUpdatesEnabled(True)
        self._apply_filter()
        if not was_explicitly_hidden:
            self.words_table.show()
        if had_focus:
            self.words_table.setFocus(Qt.OtherFocusReason)

    def update_rating(self, word_id: int, rating: int) -> bool:
        """Update one word's rating without rebuilding 3,292 rows."""

        if type(word_id) is not int:
            raise ValueError("word_id must be an integer")
        for row_index, current in enumerate(self._rows):
            if current.word.id != word_id:
                continue
            updated = replace(current, rating=rating)
            row_item = self.words_table.item(row_index, 0)
            rating_item = self.words_table.item(row_index, 5)
            if row_item is None or rating_item is None:
                return False
            with QSignalBlocker(self.words_table):
                row_item.setData(Qt.UserRole, updated)
                rating_item.setText(f"{updated.rating} 星")
            self._rows[row_index] = updated
            if self.words_table.currentRow() == row_index:
                self._selected_word_id = word_id
                self._update_actions()
            return True
        return False

    @staticmethod
    def _summary(word: WordEntry) -> str:
        value = word.definition_zh or word.definition_en
        return " ".join(value.split())

    @staticmethod
    def _section_label(key: str) -> str:
        if key.startswith("list") and key[4:].isdigit():
            return f"List {int(key[4:])}"
        if key.startswith("supplement-") and key[11:].isdigit():
            return f"补充 {int(key[11:])}"
        return key

    def _row_data(self, row_index: int) -> WordListRow | None:
        if not 0 <= row_index < self.words_table.rowCount():
            return None
        item = self.words_table.item(row_index, 0)
        if item is None:
            return None
        value = item.data(Qt.UserRole)
        return value if isinstance(value, WordListRow) else None

    def _current_row_data(self) -> WordListRow | None:
        row_index = self.words_table.currentRow()
        if row_index < 0 or self.words_table.isRowHidden(row_index):
            return None
        return self._row_data(row_index)

    def _on_search_changed(self, text: str) -> None:
        query = text.strip()
        self.searchRequested.emit(query)
        self._apply_filter()

    def _apply_filter(self) -> None:
        query = self.search_edit.text().strip().casefold()
        preferred_row = -1
        visible_count = 0
        for row_index, row in enumerate(self._rows):
            word = row.word
            haystack = "\n".join(
                (
                    word.headword,
                    word.definition_en,
                    word.definition_zh,
                    word.source_section,
                    str(word.source_order),
                    "机经7.0" if row.in_machine7 else "",
                )
            ).casefold()
            visible = not query or query in haystack
            self.words_table.setRowHidden(row_index, not visible)
            if visible:
                visible_count += 1
                if word.id == self._selected_word_id:
                    preferred_row = row_index

        if preferred_row >= 0:
            self.words_table.setCurrentCell(preferred_row, 0)
        elif self._current_row_data() is None:
            self.words_table.clearSelection()
            self.words_table.setCurrentCell(-1, -1)

        self.empty_state.setText(
            "没有找到匹配的单词。" if query else "词表为空。"
        )
        self.empty_state.setVisible(visible_count == 0)
        self.count_label.setText(
            f"{visible_count:,} / {len(self._rows):,} 词"
            if query
            else f"{len(self._rows):,} 词"
        )
        self._update_actions()

    def _on_current_changed(self, *_args: object) -> None:
        current = self._current_row_data()
        if current is not None:
            self._selected_word_id = current.word.id
        self._update_actions()

    def _update_actions(self) -> None:
        current = self._current_row_data()
        enabled = current is not None
        self.open_button.setEnabled(enabled)
        self.star_button.setEnabled(enabled)

    def _emit_selected_item(self, item: QTableWidgetItem) -> None:
        row = self._row_data(item.row())
        if row is not None:
            self.wordSelected.emit(row.word)

    def _open_current(self) -> None:
        row = self._current_row_data()
        if row is not None:
            self.wordSelected.emit(row.word)

    def _advance_star(self) -> None:
        row = self._current_row_data()
        if row is not None:
            self.starRatingRequested.emit(row.word.id, (row.rating + 1) % 4)
