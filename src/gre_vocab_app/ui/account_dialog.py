from PySide6.QtCore import QDateTime, QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class AccountDialog(QDialog):
    cloudTokenChanged = Signal(str)
    cloudCreateCodeRequested = Signal()
    cloudUploadRequested = Signal()
    cloudDownloadRequested = Signal()
    cloudAccountRequested = Signal(str, str, bool)
    cloudAccountLogoutRequested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("账号")
        self.setObjectName("settingsDialog")
        self.setMinimumSize(400, 350)
        self.resize(490, 520)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 18, 24, 20)
        root.setSpacing(14)
        header = QHBoxLayout()
        title = QLabel("账号与同步")
        title.setObjectName("settingsTitle")
        header.addWidget(title)
        header.addStretch(1)
        close_button = QPushButton("×")
        close_button.setObjectName("settingsClose")
        close_button.setAccessibleName("关闭账号窗口")
        close_button.clicked.connect(self.close)
        header.addWidget(close_button)
        root.addLayout(header)

        cloud_panel = QWidget()
        cloud_panel.setObjectName("settingsPage")
        cloud_layout = QVBoxLayout(cloud_panel)
        cloud_layout.setContentsMargins(0, 0, 8, 0)
        cloud_layout.setSpacing(16)
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
        sync_title = QLabel("进度同步")
        sync_title.setObjectName("settingsSection")
        cloud_layout.addWidget(sync_title)
        self.cloud_updated_at = QLabel()
        self.cloud_updated_at.setWordWrap(True)
        self.cloud_updated_at.hide()
        cloud_layout.addWidget(self.cloud_updated_at)
        self.cloud_upload_button = QPushButton("上传本机进度")
        self.cloud_upload_button.setObjectName("primaryButton")
        self.cloud_download_button = QPushButton("从云端恢复")
        sync_buttons = QHBoxLayout()
        sync_buttons.addWidget(self.cloud_upload_button)
        sync_buttons.addWidget(self.cloud_download_button)
        cloud_layout.addLayout(sync_buttons)
        cloud_layout.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(cloud_panel)
        root.addWidget(scroll, 1)

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

    def set_cloud_updated_at(self, updated_at: str | None, *, empty: bool = False) -> None:
        when = QDateTime.fromString(updated_at or "", Qt.ISODateWithMs)
        text = ""
        if when.isValid():
            text = f"云端更新于 {when.toLocalTime().toString('yyyy/M/d HH:mm:ss')}"
        elif empty:
            text = "云端暂无学习进度"
        self.cloud_updated_at.setText(text)
        self.cloud_updated_at.setVisible(bool(text))

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
