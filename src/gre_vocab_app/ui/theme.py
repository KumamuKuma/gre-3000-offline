from PySide6.QtWidgets import QApplication


APP_STYLESHEET = """
QWidget {
    color: #172033;
    font-family: "Segoe UI", "Microsoft YaHei UI";
    font-size: 14px;
}
QWidget#appSurface { background: #f5f7fb; }
QLabel#eyebrow { color: #64748b; font-size: 12px; font-weight: 600; }
QLabel#pageTitle { color: #111827; font-size: 28px; font-weight: 700; }
QLabel#sectionTitle { color: #26334d; font-size: 16px; font-weight: 650; }
QLabel#muted { color: #64748b; }
QFrame#card, QWidget#wordCard, QWidget#meaningPanel {
    background: #ffffff;
    border: 1px solid #dfe5ee;
    border-radius: 14px;
}
QLabel#statValue { color: #18233b; font-size: 24px; font-weight: 700; }
QLabel#headword { color: #15213a; font-size: 34px; font-weight: 750; }
QLabel#phonetic { color: #64748b; font-size: 16px; }
QLabel#definition { color: #18233b; font-size: 17px; font-weight: 600; }
QLineEdit {
    background: #ffffff;
    border: 1px solid #ced7e4;
    border-radius: 11px;
    padding: 10px 13px;
    selection-background-color: #7c5cff;
}
QLineEdit:focus { border: 2px solid #7257e8; padding: 9px 12px; }
QPushButton {
    background: #ffffff;
    border: 1px solid #cfd8e6;
    border-radius: 10px;
    padding: 9px 15px;
    font-weight: 600;
}
QPushButton:hover { background: #f2efff; border-color: #8b74ee; }
QPushButton:pressed { background: #e7e0ff; }
QPushButton:disabled { color: #9aa5b5; background: #f3f5f8; }
QPushButton#primaryButton {
    color: white;
    background: #6f52df;
    border-color: #6f52df;
}
QPushButton#primaryButton:hover { background: #5e43c7; }
QPushButton#dangerButton { color: #b42318; border-color: #efc7c3; }
QListWidget {
    background: #ffffff;
    border: 1px solid #dfe5ee;
    border-radius: 12px;
    padding: 5px;
    outline: none;
}
QListWidget::item { border-radius: 8px; padding: 11px 10px; margin: 2px; }
QListWidget::item:hover { background: #f3f0ff; }
QListWidget::item:selected { color: #24145f; background: #e8e2ff; }
"""


def apply_theme(application: QApplication) -> None:
    application.setStyle("Fusion")
    application.setStyleSheet(APP_STYLESHEET)
