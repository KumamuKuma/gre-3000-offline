from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


TEXT_COLOR = "#34443c"
MUTED_COLOR = "#5e6b63"
ACCENT_COLOR = "#527665"
WARNING_COLOR = "#81613c"

APP_STYLESHEET = """
QWidget {
    font-family: "Segoe UI Variable Text", "Segoe UI", "Microsoft YaHei";
    font-size: 14px;
}
QWidget#appSurface, QMainWindow, QDialog { background: #efeee8; }

QToolBar#mainToolbar {
    min-height: 40px;
    background: #f5f4ee;
    border: 0;
    border-bottom: 1px solid #dbddd2;
    padding: 9px 30px;
    spacing: 6px;
}
QToolBar#mainToolbar QToolButton {
    color: #56665d;
    background: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 8px 14px;
    font-weight: 600;
}
QToolBar#mainToolbar QToolButton:hover,
QToolBar#mainToolbar QToolButton:focus {
    color: #34443c;
    background: #ebece3;
    border-color: #d7dbce;
}
QToolBar#mainToolbar QToolButton:checked {
    color: #3c6957;
    background: #e1eadf;
    border-color: #cad8ca;
}
QLabel#brandGlyph {
    color: #3d6254;
    background: #e0e9dd;
    border: 1px solid #cedacd;
    border-radius: 8px;
    font-family: "Cambria", "Georgia", serif;
    font-size: 21px;
    font-weight: 700;
}
QLabel#brandMark { color: #34443c; font-size: 16px; font-weight: 650; }

QLabel#eyebrow, QLabel#heroEyebrow {
    color: #527665;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 2px;
}
QLabel#pageTitle {
    color: #2d4237;
    font-family: "Segoe UI Variable Display", "Segoe UI", "Microsoft YaHei";
    font-size: 30px;
    font-weight: 650;
}
QLabel#headword, QLabel#lookupHeadword, QLabel#noteTitle, QLabel#heroTitle {
    color: #2d4237;
    font-family: "Cambria", "Georgia", "Microsoft YaHei";
    font-weight: 400;
}
QLabel#lookupHeadword, QLabel#noteTitle { font-size: 34px; }
QLabel#sectionTitle { color: #384a40; font-size: 17px; font-weight: 650; }
QLabel#sectionHint, QLabel#muted { color: #5e6b63; }
QLabel#fieldLabel { color: #56665d; font-size: 13px; font-weight: 600; }

QFrame#heroCard {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 1,
        stop: 0 #f8f4e9, stop: 0.52 #eff0e6, stop: 1 #dce8de
    );
    border: 1px solid #d2d8cb;
    border-radius: 20px;
}
QLabel#heroTitle { font-size: 46px; }
QLabel#heroSubtitle { color: #55675d; font-size: 15px; }
QFrame#heroMetric {
    background: #f2f3e9;
    border: 1px solid #d0dbcd;
    border-radius: 12px;
}
QLabel#heroMetricLabel { color: #55675d; font-size: 12px; }
QLabel#heroMetricValue {
    color: #3b594b;
    font-family: "Cambria", "Georgia", serif;
    font-size: 31px;
    font-weight: 400;
}

QFrame#card, QFrame#searchCard, QFrame#studyCard, QFrame#studyHeader,
QFrame#navigationBar, QFrame#longSentenceCard, QWidget#wordCard,
QWidget#meaningPanel {
    background: #f8f7f1;
    border: 1px solid #dadcd2;
    border-radius: 14px;
}
QWidget#wordCard, QFrame#longSentenceCard {
    background: #f6f6ee;
    border-color: #d3d9cb;
    border-radius: 17px;
}
QFrame#studyHeader, QFrame#navigationBar { border-radius: 11px; }
QFrame#quizAutomationBar {
    background: #edf1e8;
    border: 1px solid #d1dacf;
    border-radius: 10px;
}
QLabel#longSentenceText {
    color: #34443c;
    font-family: "Cambria", "Georgia", "Microsoft YaHei";
    font-size: 26px;
    font-weight: 400;
}
QLabel#longSentenceNotesHeading {
    color: #56665d;
    border-top: 1px solid #d7dbce;
    padding-top: 18px;
    font-size: 15px;
    font-weight: 650;
}
QFrame#longSentenceNoteCard {
    background: #f1f2ea;
    border: 1px solid #d9ded1;
    border-radius: 12px;
}
QLabel#longSentenceNoteLabel, QLabel#countBadge {
    color: #3c6957;
    background: #e1eadf;
    border: 1px solid #cddacc;
    border-radius: 7px;
    padding: 4px 9px;
    font-weight: 650;
}
QLabel#longSentenceNoteText { font-size: 15px; }

QLabel#headword { font-size: 46px; }
QLabel#phonetic { color: #65766c; font-size: 16px; }
QLabel#definition { color: #34443c; font-size: 17px; font-weight: 600; }
QLabel#exampleText {
    font-family: "Cambria", "Georgia", "Microsoft YaHei";
    font-size: 17px;
}
QLabel#lookupTranslation, QLabel#lookupOnline, QLabel#notePreview {
    background: #eef1e9;
    border: 1px solid #d7e0d4;
    border-radius: 11px;
    padding: 14px;
    font-size: 15px;
}
QLabel#lookupOnline { background: #e9f0e7; border-color: #cfdccf; }
QLabel#sourceBadge {
    color: #81613c;
    background: #f3ecdc;
    border: 1px solid #ded0b7;
    border-radius: 7px;
    padding: 5px 9px;
    font-weight: 650;
}
QLabel#positionPill, QLabel#shortcutBadge {
    color: #506458;
    background: #f4f4ec;
    border: 1px solid #d9ddd0;
    border-radius: 7px;
    padding: 5px 9px;
    font-family: "Segoe UI Variable Text", "Segoe UI", "Microsoft YaHei";
    font-size: 12px;
    font-weight: 600;
}
QLabel#emptyState {
    color: #56665d;
    background: #f8f7f1;
    border: 1px dashed #bbc7b9;
    border-radius: 12px;
    padding: 20px;
}

QLineEdit, QComboBox, QPlainTextEdit {
    color: #34443c;
    background: #fbf9f3;
    border: 1px solid #ccd2c6;
    border-radius: 9px;
    padding: 8px 11px;
    selection-color: #2e4c3d;
    selection-background-color: #d6e5d8;
}
QLineEdit, QComboBox { min-height: 21px; }
QLineEdit:hover, QComboBox:hover, QPlainTextEdit:hover { border-color: #a1b3a5; }
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus { border-color: #527665; }
QLineEdit:disabled, QComboBox:disabled { color: #78827a; border-color: #dadcd2; }
QLineEdit#largeSearch { min-height: 24px; font-size: 15px; padding: 8px 13px; }
QPlainTextEdit#noteEditor { padding: 13px; font-size: 16px; }
QComboBox QAbstractItemView {
    background: #f6f6ee;
    border: 1px solid #ccd2c6;
    selection-color: #34443c;
    selection-background-color: #e0eade;
}
QCheckBox { spacing: 8px; }
QCheckBox:hover { color: #365f4d; }
QCheckBox:disabled { color: #78827a; }
QCheckBox::indicator:unchecked, QListWidget::indicator:unchecked {
    width: 12px;
    height: 12px;
    background: #f5f4ee;
    border: 1px solid #899b8d;
    border-radius: 3px;
}
QCheckBox::indicator:unchecked:hover, QListWidget::indicator:unchecked:hover {
    border-color: #527665;
}

QPushButton {
    color: #43554b;
    background: #f4f4ec;
    border: 1px solid #d5dbcf;
    border-radius: 8px;
    padding: 8px 13px;
    font-weight: 600;
}
QPushButton:hover {
    color: #304b3c;
    background: #e8eee4;
    border-color: #a2b6a7;
}
QPushButton:pressed { background: #dce7da; }
QPushButton:focus { border-color: #527665; }
QPushButton:disabled {
    color: #78827a;
    background: #eeeee7;
    border-color: #dadcd2;
}
QPushButton#primaryButton:enabled, QDialogButtonBox QPushButton:default:enabled {
    color: #fbfaf3;
    background: #527665;
    border-color: #527665;
    font-weight: 750;
}
QPushButton#primaryButton:hover, QDialogButtonBox QPushButton:default:hover {
    background: #3c6957;
    border-color: #3c6957;
}
QPushButton#primaryButton:pressed, QDialogButtonBox QPushButton:default:pressed {
    background: #345846;
    border-color: #345846;
}
QPushButton#primaryButton:focus, QDialogButtonBox QPushButton:default:focus {
    border-color: #8ba895;
}
QPushButton#heroActionButton, QPushButton#outlineButton:enabled,
QPushButton#revealButton {
    color: #3c6957;
    background: #f3f5ed;
    border-color: #cedacd;
}
QPushButton#heroActionButton:hover, QPushButton#outlineButton:hover,
QPushButton#outlineButton:checked, QPushButton#revealButton:hover {
    color: #345f4d;
    background: #e3ede2;
    border-color: #86a792;
}
QPushButton#heroActionButton:focus, QPushButton#outlineButton:focus,
QPushButton#revealButton:focus { border-color: #527665; }
QPushButton#compactButton { min-width: 18px; padding: 5px 9px; }
QPushButton#backButton:enabled { color: #4e6257; background: #f3f3ea; }
QPushButton#modeButton {
    color: #56665d;
    background: transparent;
    border-color: transparent;
    padding: 7px 12px;
}
QPushButton#modeButton:hover { color: #34443c; background: #edf0e8; }
QPushButton#modeButton:checked {
    color: #3c6957;
    background: #deeadd;
    border-color: #c4d5c7;
}
QPushButton#modeButton:focus { border-color: #527665; }
QPushButton#starButton {
    color: #81613c;
    background: #f3ecdc;
    border-color: #ded0b7;
    font-size: 16px;
}
QPushButton#starButton:hover, QPushButton#starButton[rated="true"] {
    background: #eee3cf;
    border-color: #d6c29e;
}
QPushButton#starButton:focus { border-color: #81613c; }
QPushButton#starButton:disabled { color: #78827a; border-color: #dadcd2; }
QPushButton#dangerButton, QPushButton[quizAnswer="true"]#dangerButton:disabled {
    color: #934f43;
    background: #f4e6df;
    border-color: #d9b8ad;
}
QPushButton#dangerButton:hover { background: #f0dbd2; }
QPushButton#dangerButton:focus { border-color: #934f43; }
QPushButton[quizAnswer="true"] { text-align: left; padding-left: 14px; }
QPushButton[quizAnswer="true"]#primaryButton:disabled {
    color: #3c6957;
    background: #e1ede3;
    border-color: #a6c0ad;
}
QPushButton#relationButton {
    text-align: left;
    background: #f3f3ea;
    border-color: #d9dfd2;
    font-weight: 500;
}
QPushButton#relationButton:hover { background: #e7eee4; border-color: #9db5a3; }
QPushButton#relationButton:focus { border-color: #527665; }

QListWidget, QTableWidget {
    color: #34443c;
    background: #f8f7f1;
    alternate-background-color: #f1f1e9;
    border: 1px solid #d8dbcf;
    border-radius: 10px;
    padding: 4px;
    outline: none;
}
QListWidget:focus, QTableWidget:focus { border-color: #86a792; }
QListWidget::item { border-radius: 6px; padding: 8px 10px; margin: 2px; }
QListWidget::item:hover, QTableWidget::item:hover { background: #e9eee4; }
QListWidget::item:selected, QTableWidget::item:selected {
    color: #304c3c;
    background: #dce8dc;
}
QTableWidget::item { padding: 6px 10px; }
QHeaderView { background: #ebeee4; }
QHeaderView::section {
    color: #53665b;
    background: #ebeee4;
    border: 0;
    border-bottom: 1px solid #d5dbcf;
    padding: 9px;
    font-size: 13px;
    font-weight: 650;
}
QMenu {
    background: #f3f3ea;
    border: 1px solid #d5dbcf;
    padding: 4px;
}
QMenu::item { padding: 6px 18px; }
QMenu::item:selected { color: #304c3c; background: #dce8dc; }
QMenu::item:disabled { color: #78827a; }
QMenu::separator { height: 1px; background: #d5dbcf; margin: 4px; }
QTabWidget::pane {
    background: #f8f7f1;
    border: 1px solid #dadcd2;
    border-radius: 10px;
    top: -1px;
}
QTabBar::tab {
    color: #56665d;
    background: #efeee8;
    border: 1px solid transparent;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    padding: 9px 16px;
    margin-right: 3px;
    font-weight: 600;
}
QTabBar::tab:hover { color: #34443c; background: #f4f4ec; }
QTabBar::tab:selected {
    color: #3c6957;
    background: #e7eee4;
    border-color: #cedacd;
}
QTabBar::tab:focus { border-color: #527665; }
QScrollArea { background: transparent; border: 0; }
QScrollBar:vertical { background: transparent; width: 9px; margin: 2px; }
QScrollBar:horizontal { background: transparent; height: 9px; margin: 2px; }
QScrollBar::handle { background: #a7b4a8; border-radius: 3px; min-height: 28px; min-width: 28px; }
QScrollBar::handle:hover { background: #899c8d; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
QStatusBar {
    color: #5e6b63;
    background: #f5f4ee;
    border-top: 1px solid #dbddd2;
    font-size: 12px;
}
QStatusBar::item { border: 0; }
QToolTip {
    color: #34443c;
    background: #f4f2e8;
    border: 1px solid #a7b4a8;
    padding: 6px;
}
"""


def apply_theme(application: QApplication) -> None:
    application.setStyle("Fusion")
    application.styleHints().setColorScheme(Qt.ColorScheme.Light)
    palette = QPalette()
    colors = {
        QPalette.Window: "#efeee8",
        QPalette.WindowText: TEXT_COLOR,
        QPalette.Base: "#f8f7f1",
        QPalette.AlternateBase: "#f1f1e9",
        QPalette.Text: TEXT_COLOR,
        QPalette.Button: "#f4f4ec",
        QPalette.ButtonText: TEXT_COLOR,
        QPalette.Light: "#faf8f1",
        QPalette.Midlight: "#e2e7dc",
        QPalette.Mid: "#c3cdc0",
        QPalette.Dark: "#a6b3a5",
        QPalette.Shadow: "#879889",
        QPalette.BrightText: "#934f43",
        QPalette.PlaceholderText: MUTED_COLOR,
        QPalette.Highlight: "#d6e5d8",
        QPalette.HighlightedText: "#2e4c3d",
        QPalette.Link: ACCENT_COLOR,
        QPalette.ToolTipBase: "#f4f2e8",
        QPalette.ToolTipText: TEXT_COLOR,
    }
    for role, color in colors.items():
        palette.setColor(role, QColor(color))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        palette.setColor(QPalette.Disabled, role, QColor("#78827a"))
    application.setPalette(palette)
    application.setStyleSheet(APP_STYLESHEET)
