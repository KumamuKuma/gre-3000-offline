from __future__ import annotations

import json

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QAction, QCloseEvent, QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import QMainWindow, QMessageBox, QStackedWidget, QToolBar

from .favorites_page import FavoritesPage
from .home_page import HomePage
from .settings_dialog import SettingsDialog
from .study_page import StudyPage


_PREFERRED_MINIMUM_WIDTH = 820
_PREFERRED_MINIMUM_HEIGHT = 620
_SAFE_DEFAULT_WIDTH = 980
_SAFE_DEFAULT_HEIGHT = 760
_TITLE_BAR_HEIGHT = 32
_OPERABLE_TITLE_WIDTH = 120
_OPERABLE_TITLE_HEIGHT = 24
_QT_INT_MIN = -(2**31)
_QT_INT_MAX = 2**31 - 1


class MainWindow(QMainWindow):
    homeRequested = Signal()
    findRequested = Signal()
    closing = Signal(object)

    def __init__(self):
        super().__init__()
        self._close_guard_enabled = False
        self._close_guard_installed = False
        self.setWindowTitle("GRE 3000 词离线版")
        self.setMinimumSize(
            _PREFERRED_MINIMUM_WIDTH, _PREFERRED_MINIMUM_HEIGHT
        )
        self.resize(_SAFE_DEFAULT_WIDTH, _SAFE_DEFAULT_HEIGHT)

        self.stack = QStackedWidget()
        self.home_page = HomePage()
        self.study_page = StudyPage()
        self.favorites_page = FavoritesPage()
        self.stack.addWidget(self.home_page)
        self.stack.addWidget(self.study_page)
        self.stack.addWidget(self.favorites_page)
        self.setCentralWidget(self.stack)

        toolbar = QToolBar("主工具栏")
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.addToolBar(toolbar)
        self.home_action = QAction("首页", self)
        self.settings_action = QAction("设置", self)
        toolbar.addAction(self.home_action)
        toolbar.addSeparator()
        toolbar.addAction(self.settings_action)
        self.home_action.triggered.connect(self.homeRequested.emit)

        self.find_shortcut = QShortcut(QKeySequence.StandardKey.Find, self)
        self.find_shortcut.setContext(Qt.ApplicationShortcut)
        self.find_shortcut.activated.connect(self.findRequested.emit)

        self.settings_dialog = SettingsDialog(self)
        self.settings_action.triggered.connect(self.show_settings)
        self.statusBar().showMessage("离线模式")

    def show_home(self) -> None:
        self.stack.setCurrentWidget(self.home_page)

    def show_study(self) -> None:
        self.stack.setCurrentWidget(self.study_page)

    def show_favorites(self) -> None:
        self.stack.setCurrentWidget(self.favorites_page)

    def show_settings(self) -> None:
        self.settings_dialog.show()
        self.settings_dialog.raise_()
        self.settings_dialog.activateWindow()

    def geometry_state(self) -> str:
        geometry = self.geometry()
        return json.dumps(
            {
                "x": geometry.x(),
                "y": geometry.y(),
                "width": geometry.width(),
                "height": geometry.height(),
            },
            separators=(",", ":"),
        )

    def restore_geometry_state(self, value: str | None) -> bool:
        try:
            payload = json.loads(value) if value else None
            if not isinstance(payload, dict):
                raise ValueError("geometry payload must be an object")
            coordinates = tuple(
                payload[key] for key in ("x", "y", "width", "height")
            )
            if any(type(item) is not int for item in coordinates):
                raise ValueError("geometry values must be integers")
            if any(
                item < _QT_INT_MIN or item > _QT_INT_MAX
                for item in coordinates
            ):
                raise ValueError("geometry values exceed Qt integer limits")
            if coordinates[2] <= 0 or coordinates[3] <= 0:
                raise ValueError("geometry size must be positive")
            rectangle = QRect(*coordinates)
            available = self._target_available_geometry(rectangle)
            if available is None:
                raise ValueError("window title bar is not operable on any screen")
        except (
            KeyError,
            TypeError,
            ValueError,
            OverflowError,
            json.JSONDecodeError,
        ):
            self._use_safe_default_geometry()
            return False
        self.setGeometry(self._clamp_geometry(rectangle, available))
        return True

    @staticmethod
    def _target_available_geometry(rectangle: QRect) -> QRect | None:
        title_bar = QRect(
            rectangle.x(),
            rectangle.y(),
            rectangle.width(),
            min(rectangle.height(), _TITLE_BAR_HEIGHT),
        )
        required_width = min(_OPERABLE_TITLE_WIDTH, title_bar.width())
        required_height = min(_OPERABLE_TITLE_HEIGHT, title_bar.height())
        candidates: list[tuple[int, QRect]] = []
        for screen in QGuiApplication.screens():
            available = screen.availableGeometry()
            visible = title_bar.intersected(available)
            if (
                visible.width() >= required_width
                and visible.height() >= required_height
            ):
                candidates.append((visible.width() * visible.height(), available))
        if not candidates:
            return None
        return max(candidates, key=lambda item: item[0])[1]

    def _adapt_minimum_size(self, available: QRect) -> None:
        self.setMinimumSize(
            min(_PREFERRED_MINIMUM_WIDTH, available.width()),
            min(_PREFERRED_MINIMUM_HEIGHT, available.height()),
        )

    def _clamp_geometry(self, rectangle: QRect, available: QRect) -> QRect:
        self._adapt_minimum_size(available)
        width = min(
            max(rectangle.width(), self.minimumWidth()), available.width()
        )
        height = min(
            max(rectangle.height(), self.minimumHeight()), available.height()
        )
        maximum_x = available.right() - width + 1
        maximum_y = available.bottom() - height + 1
        x = min(max(rectangle.x(), available.left()), maximum_x)
        y = min(max(rectangle.y(), available.top()), maximum_y)
        return QRect(x, y, width, height)

    def _use_safe_default_geometry(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            self.setMinimumSize(
                _PREFERRED_MINIMUM_WIDTH, _PREFERRED_MINIMUM_HEIGHT
            )
            self.resize(_SAFE_DEFAULT_WIDTH, _SAFE_DEFAULT_HEIGHT)
            return
        available = screen.availableGeometry()
        self._adapt_minimum_size(available)
        width = min(_SAFE_DEFAULT_WIDTH, available.width())
        height = min(_SAFE_DEFAULT_HEIGHT, available.height())
        x = available.left() + (available.width() - width) // 2
        y = available.top() + (available.height() - height) // 2
        self.setGeometry(x, y, width, height)

    def confirm_pending_writes(self) -> QMessageBox.StandardButton:
        message = QMessageBox(self)
        message.setIcon(QMessageBox.Warning)
        message.setWindowTitle("本地数据尚未保存")
        message.setText("本地数据库暂时不可写，未保存的学习记录仍保留在内存中。")
        message.setInformativeText(
            "请选择“重试保存”；只有选择“放弃未保存内容并退出”才会丢弃这些记录。"
        )
        retry = message.addButton("重试保存", QMessageBox.AcceptRole)
        discard = message.addButton(
            "放弃未保存内容并退出", QMessageBox.DestructiveRole
        )
        cancel = message.addButton("取消", QMessageBox.RejectRole)
        message.setDefaultButton(retry)
        message.setEscapeButton(cancel)
        message.exec()
        clicked = message.clickedButton()
        if clicked is retry:
            return QMessageBox.Retry
        if clicked is discard:
            return QMessageBox.Discard
        return QMessageBox.Cancel

    def enable_close_guard(self) -> None:
        self._close_guard_installed = True
        self._close_guard_enabled = True

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._close_guard_enabled:
            if not self._close_guard_installed:
                self.closing.emit(event)
            if event.isAccepted():
                super().closeEvent(event)
            return
        event.ignore()
        self.closing.emit(event)
        if event.isAccepted():
            self._close_guard_enabled = False
            super().closeEvent(event)
