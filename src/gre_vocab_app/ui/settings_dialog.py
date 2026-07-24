from __future__ import annotations

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from gre_vocab_app.domain import StudyMode


class SettingsDialog(QDialog):
    voiceSelected = Signal(str)
    secondaryVoiceSelected = Signal(str)
    rateChanged = Signal(float)
    defaultModeChanged = Signal(object)
    autoSpeakChanged = Signal(bool)
    quizWrongStarUpChanged = Signal(bool)
    quizCorrectStarDownChanged = Signal(bool)
    exportProgressRequested = Signal()
    importProgressRequested = Signal()
    cloudTokenChanged = Signal(str)
    cloudCreateCodeRequested = Signal()
    cloudUploadRequested = Signal()
    cloudDownloadRequested = Signal()
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
        self.secondary_voice_combo = QComboBox()
        self.rate_slider = QSlider(Qt.Horizontal)
        self.rate_slider.setRange(-10, 10)
        self.rate_slider.setSingleStep(1)
        self.rate_slider.setValue(0)
        self.rate_value = QLabel("0.0")
        rate_row = QHBoxLayout()
        rate_row.addWidget(self.rate_slider, 1)
        rate_row.addWidget(self.rate_value)
        self.auto_speak_checkbox = QCheckBox("切换到下一词时自动朗读一次")
        self.quiz_wrong_star_up_checkbox = QCheckBox(
            "四选一答错时自动加 1 星"
        )
        self.quiz_correct_star_down_checkbox = QCheckBox(
            "四选一答对时自动减 1 星"
        )
        form.addRow("默认模式", self.mode_combo)
        form.addRow("主音源", self.voice_combo)
        form.addRow("备用音源", self.secondary_voice_combo)
        form.addRow("朗读速度", rate_row)
        form.addRow("自动朗读", self.auto_speak_checkbox)
        form.addRow("自动调星", self.quiz_wrong_star_up_checkbox)
        form.addRow("", self.quiz_correct_star_down_checkbox)
        root.addWidget(study_group)

        data_group = QGroupBox("本地数据")
        data_layout = QVBoxLayout(data_group)
        data_note = QLabel(
            "可导出学习位置、List 完成次数、星级和设置，并在网页版或另一台电脑导入。"
        )
        data_note.setObjectName("muted")
        data_note.setWordWrap(True)
        self.reset_button = QPushButton("重置学习位置")
        transfer_row = QHBoxLayout()
        self.export_button = QPushButton("导出进度")
        self.import_button = QPushButton("导入进度")
        transfer_row.addWidget(self.export_button)
        transfer_row.addWidget(self.import_button)
        self.clear_button = QPushButton("清空全部本地数据")
        self.clear_button.setObjectName("dangerButton")
        data_layout.addWidget(data_note)
        data_layout.addLayout(transfer_row)
        data_layout.addWidget(self.reset_button)
        data_layout.addWidget(self.clear_button)
        root.addWidget(data_group)

        cloud_group = QGroupBox("免账号同步码")
        cloud_layout = QVBoxLayout(cloud_group)
        cloud_note = QLabel(
            "无需登录。创建一组同步码，在 Windows 和 iPhone 网页版粘贴同一组码即可同步。"
            "进度会先在设备端加密；请妥善保存同步码，遗失后无法恢复。"
        )
        cloud_note.setObjectName("muted")
        cloud_note.setWordWrap(True)
        self.cloud_token_input = QLineEdit()
        self.cloud_token_input.setPlaceholderText("GRE1- 开头的同步码")
        self.cloud_token_input.setEchoMode(QLineEdit.Password)
        self.cloud_create_button = QPushButton("生成新同步码")
        self.cloud_copy_button = QPushButton("显示并复制同步码")
        cloud_code_buttons = QHBoxLayout()
        cloud_code_buttons.addWidget(self.cloud_create_button)
        cloud_code_buttons.addWidget(self.cloud_copy_button)
        cloud_buttons = QHBoxLayout()
        self.cloud_upload_button = QPushButton("上传本机进度")
        self.cloud_download_button = QPushButton("从云端恢复")
        cloud_buttons.addWidget(self.cloud_upload_button)
        cloud_buttons.addWidget(self.cloud_download_button)
        cloud_layout.addWidget(cloud_note)
        cloud_layout.addWidget(self.cloud_token_input)
        cloud_layout.addLayout(cloud_code_buttons)
        cloud_layout.addLayout(cloud_buttons)
        root.addWidget(cloud_group)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.close)
        root.addWidget(buttons)

        self.voice_combo.currentTextChanged.connect(self._voice_changed)
        self.secondary_voice_combo.currentTextChanged.connect(
            self._secondary_voice_changed
        )
        self.rate_slider.valueChanged.connect(self._rate_changed)
        self.mode_combo.currentIndexChanged.connect(self._mode_changed)
        self.auto_speak_checkbox.toggled.connect(self.autoSpeakChanged.emit)
        self.quiz_wrong_star_up_checkbox.toggled.connect(
            self.quizWrongStarUpChanged.emit
        )
        self.quiz_correct_star_down_checkbox.toggled.connect(
            self.quizCorrectStarDownChanged.emit
        )
        self.export_button.clicked.connect(self.exportProgressRequested.emit)
        self.import_button.clicked.connect(self.importProgressRequested.emit)
        self.cloud_token_input.editingFinished.connect(
            lambda: self.cloudTokenChanged.emit(self.cloud_token_input.text().strip())
        )
        self.cloud_create_button.clicked.connect(self._confirm_create_sync_code)
        self.cloud_copy_button.clicked.connect(self._copy_cloud_code)
        self.cloud_upload_button.clicked.connect(self.cloudUploadRequested.emit)
        self.cloud_download_button.clicked.connect(self.cloudDownloadRequested.emit)
        self.reset_button.clicked.connect(self.resetPositionRequested.emit)
        self.clear_button.clicked.connect(self._confirm_clear)

    def set_voice_names(
        self,
        names: tuple[str, ...],
        selected: str | None = None,
        secondary_selected: str | None = None,
        *,
        using_default_voice: bool = False,
    ) -> None:
        with (
            QSignalBlocker(self.voice_combo),
            QSignalBlocker(self.secondary_voice_combo),
        ):
            self.voice_combo.clear()
            self.secondary_voice_combo.clear()
            if names:
                self.voice_combo.addItems(names)
                self.voice_combo.setEnabled(True)
                if selected in names:
                    self.voice_combo.setCurrentText(selected)
                alternatives = tuple(name for name in names if name != selected)
                if alternatives:
                    self.secondary_voice_combo.addItems(alternatives)
                    self.secondary_voice_combo.setEnabled(True)
                    if secondary_selected in alternatives:
                        self.secondary_voice_combo.setCurrentText(
                            secondary_selected
                        )
                else:
                    self.secondary_voice_combo.addItem("未检测到第二个英文语音")
                    self.secondary_voice_combo.setEnabled(False)
            else:
                self.voice_combo.addItem(
                    "使用系统默认语音（建议安装英文语音包）"
                    if using_default_voice
                    else "朗读不可用"
                )
                self.voice_combo.setEnabled(False)
                self.secondary_voice_combo.addItem("备用音源不可用")
                self.secondary_voice_combo.setEnabled(False)

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

    def set_quiz_star_adjustments(
        self,
        *,
        add_on_wrong: bool,
        remove_on_correct: bool,
    ) -> None:
        with (
            QSignalBlocker(self.quiz_wrong_star_up_checkbox),
            QSignalBlocker(self.quiz_correct_star_down_checkbox),
        ):
            self.quiz_wrong_star_up_checkbox.setChecked(bool(add_on_wrong))
            self.quiz_correct_star_down_checkbox.setChecked(
                bool(remove_on_correct)
            )

    def set_cloud_token(self, token: str | None) -> None:
        with QSignalBlocker(self.cloud_token_input):
            self.cloud_token_input.setText(token or "")

    def reveal_cloud_token(self) -> None:
        self.cloud_token_input.setEchoMode(QLineEdit.Normal)
        self.cloud_token_input.selectAll()
        self.cloud_token_input.setFocus()

    def _copy_cloud_code(self) -> None:
        code = self.cloud_token_input.text().strip()
        if not code:
            return
        QApplication.clipboard().setText(code)
        self.reveal_cloud_token()
        self.cloud_copy_button.setText("已复制")

    def _confirm_create_sync_code(self) -> None:
        if self.cloud_token_input.text().strip():
            answer = QMessageBox.question(
                self,
                "更换同步码",
                "生成新同步码会断开当前云端进度。请确认旧同步码已经备份，是否继续？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return
        self.cloudCreateCodeRequested.emit()

    def _voice_changed(self, name: str) -> None:
        if self.voice_combo.isEnabled() and name:
            self.voiceSelected.emit(name)

    def _secondary_voice_changed(self, name: str) -> None:
        if self.secondary_voice_combo.isEnabled() and name:
            self.secondaryVoiceSelected.emit(name)

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
