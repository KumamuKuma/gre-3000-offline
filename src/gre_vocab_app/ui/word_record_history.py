from collections.abc import Sequence
from datetime import datetime

from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from gre_vocab_app.db.user import WordRecordVersion


_LABELS = {"note": "备注", "star": "星级", "mark": "累计标记"}


class WordRecordHistoryDialog(QDialog):
    def __init__(
        self,
        entries: Sequence[tuple[str, WordRecordVersion]],
        parent=None,
        *,
        note_for: str | None = None,
    ):
        super().__init__(parent)
        self._entries = entries
        self.setWindowTitle(f"{note_for} · 备注历史" if note_for else "单词记录历史")
        self.resize(680, 500)
        layout = QVBoxLayout(self)

        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索单词")
        self.search.setAccessibleName("搜索历史记录的单词")
        self.kind = QComboBox()
        self.kind.setAccessibleName("记录类型")
        self.kind.addItem("全部类型", "")
        for kind, label in _LABELS.items():
            self.kind.addItem(label, kind)
        filters = QHBoxLayout()
        filters.addWidget(self.search, 1)
        filters.addWidget(self.kind)
        layout.addLayout(filters)
        self.search.setVisible(note_for is None)
        self.kind.setVisible(note_for is None)

        self.table = QTableWidget(len(entries), 3)
        self.table.setAccessibleName("历史版本")
        self.table.setHorizontalHeaderLabels(["单词", "类型", "被替换时间"])
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(
            QAbstractItemView.SingleSelection if note_for else QAbstractItemView.ExtendedSelection
        )
        for row, (word, version) in enumerate(entries):
            when = datetime.fromisoformat(version.archived_at).astimezone()
            for column, text in enumerate((word, _LABELS[version.kind], when.strftime("%Y-%m-%d %H:%M:%S"))):
                self.table.setItem(row, column, QTableWidgetItem(text))
        layout.addWidget(self.table, 2)

        self.preview = QPlainTextEdit()
        self.preview.setAccessibleName("历史版本内容")
        self.preview.setReadOnly(True)
        layout.addWidget(self.preview, 1)
        self.hint = QLabel()
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Cancel).setText("关闭")
        self.restore_button = buttons.addButton(
            "使用此版本" if note_for else "恢复选中版本", QDialogButtonBox.AcceptRole
        )
        self.restore_button.setObjectName("primaryButton")
        self.restore_button.setAutoDefault(False)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.table.itemSelectionChanged.connect(self._update_selection)
        self.search.textChanged.connect(self._filter_rows)
        self.kind.currentIndexChanged.connect(self._filter_rows)
        self._update_selection()

    def selected_versions(self) -> tuple[WordRecordVersion, ...]:
        rows = self.table.selectionModel().selectedRows()
        return tuple(self._entries[index.row()][1] for index in rows)

    def _filter_rows(self):
        word_filter = self.search.text().strip().casefold()
        kind = self.kind.currentData()
        self.table.clearSelection()
        for row, (word, version) in enumerate(self._entries):
            matches = word_filter in word.casefold() and (not kind or version.kind == kind)
            self.table.setRowHidden(row, not matches)

    def _update_selection(self):
        versions = self.selected_versions()
        unique = len({(version.kind, version.word_key) for version in versions}) == len(versions)
        self.restore_button.setEnabled(bool(versions) and unique)
        self.preview.setPlainText(versions[0].value if versions else "")
        if not self._entries:
            hint = "暂无历史版本。修改或清空记录时，旧值会自动保存在本机。"
        elif not unique:
            hint = "同一个单词的同一项记录只能选择一个版本。"
        elif versions:
            hint = f"已选 {len(versions)} 项。"
        else:
            hint = "选择一个版本预览内容。"
        self.hint.setText(hint)
