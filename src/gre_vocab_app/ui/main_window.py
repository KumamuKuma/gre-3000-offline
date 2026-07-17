from __future__ import annotations

import json

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QAction, QCloseEvent, QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import QMainWindow, QStackedWidget, QToolBar

from .favorites_page import FavoritesPage
from .home_page import HomePage
from .settings_dialog import SettingsDialog
from .study_page import StudyPage


class MainWindow(QMainWindow):
    homeRequested = Signal()
    findRequested = Signal()
    closing = Signal()

    def __init__(self):
        super().__init__()
        self._closing_emitted = False
        self.setWindowTitle("GRE 3000 词离线版")
        self.setMinimumSize(820, 620)
        self.resize(980, 760)

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
            rectangle = QRect(*coordinates)
            if rectangle.width() <= 0 or rectangle.height() <= 0:
                raise ValueError("geometry size must be positive")
            if not any(
                rectangle.intersects(screen.availableGeometry())
                for screen in QGuiApplication.screens()
            ):
                raise ValueError("geometry is outside every available screen")
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            self._use_safe_default_geometry()
            return False
        self.setGeometry(rectangle)
        return True

    def _use_safe_default_geometry(self) -> None:
        self.resize(980, 760)
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            self.move(
                available.center().x() - self.width() // 2,
                available.center().y() - self.height() // 2,
            )

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._closing_emitted:
            self._closing_emitted = True
            self.closing.emit()
        super().closeEvent(event)
