from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget


class WordMarks(QWidget):
    adjustmentRequested = Signal(str, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.headword = ""
        self.load_count = lambda _word: "0"
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        self.label = QLabel()
        self.label.setTextFormat(Qt.PlainText)
        self.label.setWordWrap(True)
        self.decrease = QPushButton("−1")
        self.increase = QPushButton("+1")
        for button, delta in ((self.decrease, -1), (self.increase, 1)):
            button.setObjectName("outlineButton")
            button.setMinimumHeight(36)
            button.setAccessibleName("累计标记减一" if delta < 0 else "累计标记加一")
            button.clicked.connect(lambda _checked=False, step=delta: self.adjustmentRequested.emit(self.headword, step))
        row.addWidget(self.label, 1)
        row.addWidget(self.decrease)
        row.addWidget(self.increase)
        self.hide()

    def set_word(self, headword):
        self.headword = headword
        self.refresh()

    def refresh(self):
        count = self.load_count(self.headword) if self.headword else "0"
        self.label.setText(f"累计标记：{count} 次")
        self.decrease.setEnabled(count != "0")
        self.setVisible(bool(self.headword))
