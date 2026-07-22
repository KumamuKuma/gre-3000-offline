from __future__ import annotations

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from gre_vocab_app.domain import StudyMode


class SettingsDialog(QDialog):
    voiceSelected = Signal(str)
    rateChanged = Signal(float)
    defaultModeChanged = Signal(object)
    autoSpeakChanged = Signal(bool)
    resetPositionRequested = Signal()
    clearAllRequested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setMinimumWidth(460)
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 18)
        root.setSpacing(14)

        study_group = QGroupBox("学习与朗读")
        form = QFormLayout(study_group)
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("阅读模式", StudyMode.READING)
        self.mode_combo.addItem("简义模式", StudyMode.BRIEF)
        self.mode_combo.addItem("回忆模式", StudyMode.RECALL)
        self.mode_combo.addItem("四选一", StudyMode.QUIZ)
        self.voice_combo = QComboBox()
        self.rate_slider = QSlider(Qt.Horizontal)
        self.rate_slider.setRange(-10, 10)
        self.rate_slider.setSingleStep(1)
        self.rate_slider.setValue(0)
        self.rate_value = QLabel("0.0")
        rate_row = QHBoxLayout()
        rate_row.addWidget(self.rate_slider, 1)
        rate_row.addWidget(self.rate_value)
        self.auto_speak_checkbox = QCheckBox("切换到下一词时自动朗读一次")
        form.addRow("默认模式", self.mode_combo)
        form.addRow("英文语音", self.voice_combo)
        form.addRow("朗读速度", rate_row)
        form.addRow("自动朗读", self.auto_speak_checkbox)
        root.addWidget(study_group)

        data_group = QGroupBox("本地数据")
        data_layout = QVBoxLayout(data_group)
        data_note = QLabel(
            "学习位置、List 完成次数、星级评分和设置仅保存在这台电脑。"
        )
        data_note.setObjectName("muted")
        data_note.setWordWrap(True)
        self.reset_button = QPushButton("重置学习位置")
        self.clear_button = QPushButton("清空全部本地数据")
        self.clear_button.setObjectName("dangerButton")
        data_layout.addWidget(data_note)
        data_layout.addWidget(self.reset_button)
        data_layout.addWidget(self.clear_button)
        root.addWidget(data_group)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.close)
        root.addWidget(buttons)

        self.voice_combo.currentTextChanged.connect(self._voice_changed)
        self.rate_slider.valueChanged.connect(self._rate_changed)
        self.mode_combo.currentIndexChanged.connect(self._mode_changed)
        self.auto_speak_checkbox.toggled.connect(self.autoSpeakChanged.emit)
        self.reset_button.clicked.connect(self.resetPositionRequested.emit)
        self.clear_button.clicked.connect(self._confirm_clear)

    def set_voice_names(
        self,
        names: tuple[str, ...],
        selected: str | None = None,
        *,
        using_default_voice: bool = False,
    ) -> None:
        with QSignalBlocker(self.voice_combo):
            self.voice_combo.clear()
            if names:
                self.voice_combo.addItems(names)
                self.voice_combo.setEnabled(True)
                if selected in names:
                    self.voice_combo.setCurrentText(selected)
            else:
                self.voice_combo.addItem(
                    "使用系统默认语音（建议安装英文语音包）"
                    if using_default_voice
                    else "朗读不可用"
                )
                self.voice_combo.setEnabled(False)

    def set_rate(self, rate: float) -> None:
        value = max(-10, min(10, round(float(rate) * 10)))
        with QSignalBlocker(self.rate_slider):
            self.rate_slider.setValue(value)
        self.rate_value.setText(f"{value / 10:.1f}")

    def set_default_mode(self, mode: StudyMode) -> None:
        index = self.mode_combo.findData(StudyMode(mode))
        if index >= 0:
            with QSignalBlocker(self.mode_combo):
                self.mode_combo.setCurrentIndex(index)

    def set_auto_speak(self, enabled: bool) -> None:
        with QSignalBlocker(self.auto_speak_checkbox):
            self.auto_speak_checkbox.setChecked(bool(enabled))

    def _voice_changed(self, name: str) -> None:
        if self.voice_combo.isEnabled() and name:
            self.voiceSelected.emit(name)

    def _rate_changed(self, value: int) -> None:
        rate = value / 10.0
        self.rate_value.setText(f"{rate:.1f}")
        self.rateChanged.emit(rate)

    def _mode_changed(self, index: int) -> None:
        mode = self.mode_combo.itemData(index)
        if mode is not None:
            self.defaultModeChanged.emit(StudyMode(mode))

    def _confirm_clear(self) -> None:
        message = (
            "这会清空本机保存的星级评分、List 完成次数、学习位置和应用设置。"
            "词库文件不会被删除。此操作无法撤销，是否继续？"
        )
        answer = QMessageBox.question(
            self,
            "清空全部本地数据",
            message,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            self.clearAllRequested.emit()
