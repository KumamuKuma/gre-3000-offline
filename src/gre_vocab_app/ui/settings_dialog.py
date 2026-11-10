from __future__ import annotations

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSlider,
    QScrollArea,
    QStackedWidget,
    QFrame,
    QVBoxLayout,
    QWidget,
)

from .controls import RoundedComboBox, SegmentedControl, ToggleSwitch

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
    cloudAccountRequested = Signal(str, str, bool)
    cloudAccountLogoutRequested = Signal()
    resetPositionRequested = Signal()
    clearAllRequested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setObjectName("settingsDialog")
        self.setMinimumSize(500, 440)
        self.resize(560, 640)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 18, 24, 16)
        root.setSpacing(14)
        header = QHBoxLayout()
        title = QLabel("设置")
        title.setObjectName("settingsTitle")
        header.addWidget(title)
        header.addStretch(1)
        self.close_button = QPushButton("×")
        self.close_button.setObjectName("settingsClose")
        self.close_button.setFixedSize(32, 32)
        self.close_button.setAccessibleName("关闭设置")
        self.close_button.clicked.connect(self.close)
        header.addWidget(self.close_button)
        root.addLayout(header)

        self.navigation = SegmentedControl((("学习与朗读", 0), ("本地数据", 1), ("云端同步", 2)), navigation=True)
        root.addWidget(self.navigation)
        self.pages = QStackedWidget()
        self.navigation.currentIndexChanged.connect(self.pages.setCurrentIndex)
        root.addWidget(self.pages, 1)

        study_panel = QWidget()
        study_panel.setObjectName("settingsPage")
        study = QVBoxLayout(study_panel)
        study.setContentsMargins(2, 0, 8, 0)
        study.setSpacing(8)
        self._section(study, "学习方式")
        self.mode_control = SegmentedControl((("阅读", StudyMode.READING), ("简义", StudyMode.BRIEF),
            ("回忆", StudyMode.RECALL), ("四选一", StudyMode.QUIZ)))
        self.mode_control.setAccessibleName("默认学习模式")
        mode_label = QLabel("默认模式")
        mode_label.setObjectName("settingsLabel")
        study.addWidget(mode_label)
        study.addWidget(self.mode_control)

        self._section(study, "朗读")
        self.voice_combo = RoundedComboBox()
        self.voice_combo.setAccessibleName("主音源")
        self.secondary_voice_combo = RoundedComboBox()
        self.secondary_voice_combo.setAccessibleName("备用音源")
        self._control_row(study, "主音源", self.voice_combo)
        self._control_row(study, "备用音源", self.secondary_voice_combo)
        rate_widget = QWidget()
        rate_row = QHBoxLayout(rate_widget)
        rate_row.setContentsMargins(0, 0, 0, 0)
        rate_row.setSpacing(14)
        self.rate_slider = QSlider(Qt.Horizontal)
        self.rate_slider.setAccessibleName("朗读速度")
        self.rate_slider.setRange(-10, 10)
        self.rate_slider.setSingleStep(1)
        self.rate_slider.setValue(0)
        self.rate_value = QLabel("正常")
        self.rate_value.setObjectName("settingsHint")
        self.rate_value.setFixedWidth(40)
        self.rate_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        rate_row.addWidget(self.rate_slider, 1)
        rate_row.addWidget(self.rate_value)
        self._control_row(study, "朗读速度", rate_widget)
        self.auto_speak_checkbox = ToggleSwitch("")
        self.auto_speak_checkbox.setAccessibleName("切换到下一词时自动朗读一次")
        self.auto_speak_checkbox.setFixedWidth(48)
        self._control_row(study, "自动朗读", self.auto_speak_checkbox, "切换单词时朗读一次", stretch=False)

        self._section(study, "四选一调星")
        self.quiz_wrong_star_up_checkbox = ToggleSwitch("")
        self.quiz_wrong_star_up_checkbox.setAccessibleName("四选一答错时自动加 1 星")
        self.quiz_wrong_star_up_checkbox.setFixedWidth(48)
        self.quiz_correct_star_down_checkbox = ToggleSwitch("")
        self.quiz_correct_star_down_checkbox.setAccessibleName("四选一答对时自动减 1 星")
        self.quiz_correct_star_down_checkbox.setFixedWidth(48)
        self._control_row(study, "答错时加 1 星", self.quiz_wrong_star_up_checkbox, stretch=False)
        self._control_row(study, "答对时减 1 星", self.quiz_correct_star_down_checkbox, stretch=False)
        study.addStretch(1)
        self._add_page(study_panel)

        data_panel = QWidget()
        data_panel.setObjectName("settingsPage")
        data_layout = QVBoxLayout(data_panel)
        data_layout.setContentsMargins(2, 0, 8, 0)
        data_layout.setSpacing(16)
        self._section(data_layout, "进度备份")
        data_note = QLabel("导出学习位置、List 完成次数、星级、备注、累计标记和设置，可在网页版或另一台电脑导入。")
        data_note.setObjectName("settingsHint")
        data_note.setWordWrap(True)
        data_layout.addWidget(data_note)
        self.export_button = QPushButton("导出进度")
        self.import_button = QPushButton("导入进度")
        transfer_row = QHBoxLayout()
        transfer_row.addWidget(self.export_button)
        transfer_row.addWidget(self.import_button)
        data_layout.addLayout(transfer_row)
        self._section(data_layout, "学习位置")
        self.reset_button = QPushButton("重置")
        self.reset_button.setAccessibleName("重置学习位置")
        self._control_row(data_layout, "重置学习位置", self.reset_button, "保留星级、备注和累计标记", stretch=False)
        self._section(data_layout, "本地数据")
        self.clear_button = QPushButton("清空数据")
        self.clear_button.setAccessibleName("清空全部本地数据")
        self.clear_button.setObjectName("dangerButton")
        self._control_row(data_layout, "清空全部本地数据", self.clear_button, "删除本机进度和设置", stretch=False)
        data_layout.addStretch(1)
        self._add_page(data_panel)

        cloud_panel = QWidget()
        cloud_panel.setObjectName("settingsPage")
        cloud_layout = QVBoxLayout(cloud_panel)
        cloud_layout.setContentsMargins(2, 0, 8, 0)
        cloud_layout.setSpacing(16)
        self._section(cloud_layout, "账号同步")
        self.cloud_account_status = QLabel("用网页端的用户名和密码登录即可自动同步。")
        self.cloud_account_status.setWordWrap(True)
        cloud_layout.addWidget(self.cloud_account_status)
        self.cloud_account_form = QWidget()
        account_form = QVBoxLayout(self.cloud_account_form)
        account_form.setContentsMargins(0, 0, 0, 0)
        self.cloud_username = QLineEdit()
        self.cloud_username.setPlaceholderText("用户名")
        self.cloud_username.setAccessibleName("同步账号用户名")
        self.cloud_password = QLineEdit()
        self.cloud_password.setEchoMode(QLineEdit.Password)
        self.cloud_password.setPlaceholderText("密码")
        self.cloud_password.setAccessibleName("同步账号密码")
        account_form.addWidget(self.cloud_username)
        account_form.addWidget(self.cloud_password)
        account_buttons = QHBoxLayout()
        self.cloud_login_button = QPushButton("登录并同步")
        self.cloud_register_button = QPushButton("注册并同步")
        account_buttons.addWidget(self.cloud_login_button)
        account_buttons.addWidget(self.cloud_register_button)
        account_form.addLayout(account_buttons)
        cloud_layout.addWidget(self.cloud_account_form)
        self.cloud_logout_button = QPushButton("退出账号")
        cloud_layout.addWidget(self.cloud_logout_button)
        self.cloud_logout_button.hide()
        self.cloud_legacy_toggle = QPushButton("使用同步码")
        self.cloud_legacy_toggle.setCheckable(True)
        cloud_layout.addWidget(self.cloud_legacy_toggle)
        self.cloud_legacy = QWidget()
        legacy_layout = QVBoxLayout(self.cloud_legacy)
        legacy_layout.setContentsMargins(0, 0, 0, 0)
        self.cloud_token_input = QLineEdit()
        self.cloud_token_input.setAccessibleName("云端同步码")
        self.cloud_token_input.setPlaceholderText("GRE1- 开头的同步码")
        self.cloud_token_input.setEchoMode(QLineEdit.Password)
        legacy_layout.addWidget(self.cloud_token_input)
        self.cloud_create_button = QPushButton("生成新同步码")
        self.cloud_copy_button = QPushButton("复制同步码")
        self.cloud_copy_button.setAccessibleName("复制同步码")
        cloud_code_buttons = QHBoxLayout()
        cloud_code_buttons.addWidget(self.cloud_create_button)
        cloud_code_buttons.addWidget(self.cloud_copy_button)
        legacy_layout.addLayout(cloud_code_buttons)
        cloud_layout.addWidget(self.cloud_legacy)
        self.cloud_legacy.hide()
        self.cloud_backup_button = QPushButton("复制备用同步码")
        cloud_layout.addWidget(self.cloud_backup_button)
        self.cloud_backup_button.hide()
        self._section(cloud_layout, "进度同步")
        self.cloud_upload_button = QPushButton("上传本机进度")
        self.cloud_upload_button.setObjectName("primaryButton")
        self.cloud_download_button = QPushButton("从云端恢复")
        self._control_row(cloud_layout, "保存到云端", self.cloud_upload_button, "上传本机当前进度", stretch=False)
        self._control_row(cloud_layout, "恢复到本机", self.cloud_download_button, "下载云端保存的进度", stretch=False)
        cloud_layout.addStretch(1)
        self._add_page(cloud_panel)

        saved_hint = QLabel("更改自动保存")
        saved_hint.setObjectName("settingsHint")
        saved_hint.setAlignment(Qt.AlignCenter)
        root.addWidget(saved_hint)

        self.voice_combo.currentTextChanged.connect(self._voice_changed)
        self.secondary_voice_combo.currentTextChanged.connect(
            self._secondary_voice_changed
        )
        self.rate_slider.valueChanged.connect(self._rate_changed)
        self.mode_control.currentIndexChanged.connect(self._mode_changed)
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
        self.cloud_legacy_toggle.toggled.connect(self.cloud_legacy.setVisible)
        self.cloud_login_button.clicked.connect(lambda: self._submit_cloud_account(False))
        self.cloud_register_button.clicked.connect(lambda: self._submit_cloud_account(True))
        self.cloud_password.returnPressed.connect(lambda: self._submit_cloud_account(False))
        self.cloud_logout_button.clicked.connect(self.cloudAccountLogoutRequested.emit)
        self.cloud_backup_button.clicked.connect(self._copy_cloud_code)
        self.reset_button.clicked.connect(self.resetPositionRequested.emit)
        self.clear_button.clicked.connect(self._confirm_clear)

    @staticmethod
    def _section(layout, title):
        section = QWidget()
        group = QVBoxLayout(section)
        group.setContentsMargins(0, 4, 0, 0)
        group.setSpacing(8)
        rule = QFrame()
        rule.setObjectName("settingsDivider")
        rule.setFixedHeight(1)
        label = QLabel(title)
        label.setObjectName("settingsSection")
        group.addWidget(rule)
        group.addWidget(label)
        layout.addWidget(section)

    @staticmethod
    def _control_row(layout, title, control, hint=None, *, stretch=True):
        widget = QWidget()
        row = QHBoxLayout(widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(18)
        copy = QVBoxLayout()
        copy.setSpacing(2)
        label = QLabel(title)
        label.setObjectName("settingsLabel")
        copy.addWidget(label)
        if hint:
            subtitle = QLabel(hint)
            subtitle.setObjectName("settingsHint")
            subtitle.setWordWrap(True)
            copy.addWidget(subtitle)
        row.addLayout(copy, 0 if stretch else 1)
        if stretch:
            label.setMinimumWidth(78)
        row.addWidget(control, 1 if stretch else 0)
        layout.addWidget(widget)

    def _add_page(self, panel):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(panel)
        self.pages.addWidget(scroll)

    def set_voice_names(
        self,
        names: tuple[str, ...],
        selected: str | None = None,
        secondary_selected: str | None = None,
        *,
        using_default_voice: bool = False,
        secondary_names: tuple[str, ...] | None = None,
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
                alternatives = (
                    secondary_names
                    if secondary_names is not None
                    else tuple(name for name in names if name != selected)
                )
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
                alternatives = secondary_names or ()
                if alternatives:
                    self.secondary_voice_combo.addItems(alternatives)
                    self.secondary_voice_combo.setEnabled(True)
                    if secondary_selected in alternatives:
                        self.secondary_voice_combo.setCurrentText(
                            secondary_selected
                        )
                else:
                    self.secondary_voice_combo.addItem("备用音源不可用")
                    self.secondary_voice_combo.setEnabled(False)

    def set_rate(self, rate: float) -> None:
        value = max(-10, min(10, round(float(rate) * 10)))
        with QSignalBlocker(self.rate_slider):
            self.rate_slider.setValue(value)
        self.rate_value.setText("正常" if value == 0 else f"{value / 10:+.1f}")

    def set_default_mode(self, mode: StudyMode) -> None:
        index = self.mode_control.findData(StudyMode(mode))
        if index >= 0:
            with QSignalBlocker(self.mode_control):
                self.mode_control.setCurrentIndex(index)

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
            self.cloud_token_input.setEchoMode(QLineEdit.Password)
            self.cloud_token_input.setText(token or "")

    def set_cloud_account(self, username: str) -> None:
        self.cloud_account_form.setVisible(not username)
        self.cloud_logout_button.setVisible(bool(username))
        self.cloud_backup_button.setVisible(bool(username))
        self.cloud_legacy_toggle.setVisible(not username)
        self.cloud_legacy_toggle.setChecked(False)
        self.cloud_account_status.setText(f"已登录 {username}" if username else "用网页端的用户名和密码登录即可自动同步。注册时会绑定当前同步码。")

    def set_cloud_account_busy(self, busy: bool) -> None:
        self.cloud_account_form.setEnabled(not busy)

    def _submit_cloud_account(self, register: bool) -> None:
        password = self.cloud_password.text()
        if not password:
            self.cloud_account_status.setText("请输入密码。")
            return
        if register:
            repeated, accepted = QInputDialog.getText(self, "确认密码", "请再输入一次密码", QLineEdit.Password)
            if not accepted:
                return
            if repeated != password:
                self.cloud_account_status.setText("两次输入的密码不一致。")
                return
        self.cloud_password.clear()
        self.cloudAccountRequested.emit(self.cloud_username.text(), password, register)

    def reveal_cloud_token(self) -> None:
        self.cloud_token_input.setEchoMode(QLineEdit.Normal)
        self.cloud_token_input.selectAll()
        self.cloud_token_input.setFocus()

    def _copy_cloud_code(self) -> None:
        code = self.cloud_token_input.text().strip()
        if not code:
            return
        QApplication.clipboard().setText(code)
        self.cloud_copy_button.setText("已复制")
        self.cloud_backup_button.setText("已复制备用同步码")

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
        self.rate_value.setText("正常" if value == 0 else f"{rate:+.1f}")
        self.rateChanged.emit(rate)

    def _mode_changed(self, index: int) -> None:
        mode = self.mode_control.itemData(index)
        if mode is not None:
            self.defaultModeChanged.emit(StudyMode(mode))

    def _confirm_clear(self) -> None:
        message = (
            "这会清空本机保存的星级评分、备注、累计标记、List 完成次数、学习位置和应用设置。"
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
