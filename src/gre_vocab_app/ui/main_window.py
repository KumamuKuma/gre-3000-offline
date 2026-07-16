from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMainWindow, QStackedWidget, QToolBar

from .favorites_page import FavoritesPage
from .home_page import HomePage
from .settings_dialog import SettingsDialog
from .study_page import StudyPage


class MainWindow(QMainWindow):
    homeRequested = Signal()

    def __init__(self):
        super().__init__()
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
