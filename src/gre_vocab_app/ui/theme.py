from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


TEXT_COLOR = "#e8eff8"
MUTED_COLOR = "#9caec3"
ACCENT_COLOR = "#81ead7"
WARNING_COLOR = "#f1be7c"

APP_STYLESHEET = """
QWidget {
    font-family: "Segoe UI", "Microsoft YaHei UI";
    font-size: 14px;
}
QWidget#appSurface, QMainWindow, QDialog { background: #0c121c; }

QToolBar#mainToolbar {
    min-height: 40px;
    background: #101824;
    border: 0;
    border-bottom: 1px solid #222f40;
    padding: 9px 30px;
    spacing: 6px;
}
QToolBar#mainToolbar QToolButton {
    color: #aab9cb;
    background: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 8px 14px;
    font-weight: 600;
}
QToolBar#mainToolbar QToolButton:hover,
QToolBar#mainToolbar QToolButton:focus {
    color: #e8eff8;
    background: #1a2736;
    border-color: #324258;
}
QToolBar#mainToolbar QToolButton:checked {
    color: #a5f4e6;
    background: #183037;
    border-color: #275050;
}
QLabel#brandGlyph {
    color: #0c2227;
    background: #81ead7;
    border-radius: 8px;
    font-size: 17px;
    font-weight: 800;
}
QLabel#brandMark { color: #e8eff8; font-size: 16px; font-weight: 750; }

QLabel#eyebrow, QLabel#heroEyebrow {
    color: #81ead7;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 2px;
}
QLabel#pageTitle, QLabel#lookupHeadword, QLabel#noteTitle {
    color: #f3f7fc;
    font-size: 29px;
    font-weight: 750;
}
QLabel#sectionTitle { color: #edf3fa; font-size: 17px; font-weight: 650; }
QLabel#sectionHint, QLabel#muted { color: #9caec3; }
QLabel#fieldLabel { color: #aab9cb; font-size: 13px; font-weight: 600; }

QFrame#heroCard {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 1,
        stop: 0 #162338, stop: 0.52 #111f30, stop: 1 #14363b
    );
    border: 1px solid #2a424f;
    border-radius: 20px;
}
QLabel#heroTitle { color: #f3f7fc; font-size: 36px; font-weight: 750; }
QLabel#heroSubtitle { color: #aabdd0; font-size: 14px; }
QFrame#heroMetric {
    background: #12252f;
    border: 1px solid #315257;
    border-radius: 12px;
}
QLabel#heroMetricLabel { color: #aabdd0; font-size: 12px; }
QLabel#heroMetricValue {
    color: #d7fff7;
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 28px;
    font-weight: 650;
}

QFrame#card, QFrame#searchCard, QFrame#studyCard, QFrame#studyHeader,
QFrame#navigationBar, QFrame#longSentenceCard, QWidget#wordCard,
QWidget#meaningPanel {
    background: #121c2a;
    border: 1px solid #26364a;
    border-radius: 14px;
}
QWidget#wordCard, QFrame#longSentenceCard {
    background: #142131;
    border-color: #30465a;
    border-radius: 17px;
}
QFrame#studyHeader, QFrame#navigationBar { border-radius: 11px; }
QFrame#quizAutomationBar {
    background: #17252f;
    border: 1px solid #2b4048;
    border-radius: 10px;
}
QLabel#longSentenceText { color: #e8eff8; font-size: 23px; font-weight: 550; }
QLabel#longSentenceNotesHeading {
    color: #aab9cb;
    border-top: 1px solid #324258;
    padding-top: 18px;
    font-size: 15px;
    font-weight: 650;
}
QFrame#longSentenceNoteCard {
    background: #101a28;
    border: 1px solid #2a3a4f;
    border-radius: 12px;
}
QLabel#longSentenceNoteLabel, QLabel#countBadge {
    color: #a5f4e6;
    background: #183037;
    border: 1px solid #295155;
    border-radius: 7px;
    padding: 4px 9px;
    font-weight: 650;
}
QLabel#longSentenceNoteText { font-size: 15px; }

QLabel#headword { color: #e8eff8; font-size: 42px; font-weight: 750; }
QLabel#phonetic { color: #a8bed5; font-size: 16px; }
QLabel#definition { color: #e8eff8; font-size: 17px; font-weight: 650; }
QLabel#lookupTranslation, QLabel#lookupOnline, QLabel#notePreview {
    background: #162836;
    border: 1px solid #2d4958;
    border-radius: 11px;
    padding: 14px;
    font-size: 15px;
}
QLabel#lookupOnline { background: #152b2d; border-color: #2d4e4b; }
QLabel#sourceBadge {
    color: #f1be7c;
    background: #2a241e;
    border: 1px solid #524131;
    border-radius: 7px;
    padding: 5px 9px;
    font-weight: 650;
}
QLabel#positionPill, QLabel#shortcutBadge {
    color: #b3c4d9;
    background: #1a2839;
    border: 1px solid #304158;
    border-radius: 7px;
    padding: 5px 9px;
    font-family: "Cascadia Mono", "Consolas", "Microsoft YaHei UI";
    font-size: 12px;
    font-weight: 600;
}
QLabel#emptyState {
    color: #aab9cb;
    background: #121c2a;
    border: 1px dashed #3a5068;
    border-radius: 12px;
    padding: 20px;
}

QLineEdit, QComboBox, QPlainTextEdit {
    color: #e8eff8;
    background: #0d1623;
    border: 1px solid #34455c;
    border-radius: 9px;
    padding: 8px 11px;
    selection-color: #effffb;
    selection-background-color: #285653;
}
QLineEdit, QComboBox { min-height: 21px; }
QLineEdit:hover, QComboBox:hover, QPlainTextEdit:hover { border-color: #4b627a; }
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus { border-color: #81ead7; }
QLineEdit:disabled, QComboBox:disabled { color: #8495a9; border-color: #26364a; }
QLineEdit#largeSearch { min-height: 24px; font-size: 15px; padding: 8px 13px; }
QPlainTextEdit#noteEditor { padding: 13px; font-size: 16px; }
QComboBox QAbstractItemView {
    background: #142131;
    border: 1px solid #34455c;
    selection-color: #e8eff8;
    selection-background-color: #23454d;
}
QCheckBox { spacing: 8px; }
QCheckBox:hover { color: #b7fff1; }
QCheckBox:disabled { color: #8495a9; }
QCheckBox::indicator:unchecked, QListWidget::indicator:unchecked {
    width: 12px;
    height: 12px;
    background: #101824;
    border: 1px solid #62778e;
    border-radius: 3px;
}
QCheckBox::indicator:unchecked:hover, QListWidget::indicator:unchecked:hover {
    border-color: #81ead7;
}

QPushButton {
    color: #dbe6f3;
    background: #1a2839;
    border: 1px solid #32445b;
    border-radius: 8px;
    padding: 8px 13px;
    font-weight: 600;
}
QPushButton:hover {
    color: #f2f7ff;
    background: #23364b;
    border-color: #506780;
}
QPushButton:pressed { background: #2c4158; }
QPushButton:focus { border-color: #81ead7; }
QPushButton:disabled {
    color: #8495a9;
    background: #141e2c;
    border-color: #26364a;
}
QPushButton#primaryButton:enabled, QDialogButtonBox QPushButton:default:enabled {
    color: #092324;
    background: #81ead7;
    border-color: #81ead7;
    font-weight: 750;
}
QPushButton#primaryButton:hover, QDialogButtonBox QPushButton:default:hover {
    background: #a5f4e6;
    border-color: #a5f4e6;
}
QPushButton#primaryButton:pressed, QDialogButtonBox QPushButton:default:pressed {
    background: #66cdbb;
    border-color: #66cdbb;
}
QPushButton#primaryButton:focus, QDialogButtonBox QPushButton:default:focus {
    border-color: #edfffb;
}
QPushButton#heroActionButton, QPushButton#outlineButton:enabled,
QPushButton#revealButton {
    color: #a5f4e6;
    background: #162b34;
    border-color: #34565c;
}
QPushButton#heroActionButton:hover, QPushButton#outlineButton:hover,
QPushButton#outlineButton:checked, QPushButton#revealButton:hover {
    color: #d9fff7;
    background: #24474c;
    border-color: #5a9c98;
}
QPushButton#heroActionButton:focus, QPushButton#outlineButton:focus,
QPushButton#revealButton:focus { border-color: #81ead7; }
QPushButton#compactButton { min-width: 18px; padding: 5px 9px; }
QPushButton#backButton:enabled { color: #afc0d4; background: #152232; }
QPushButton#modeButton {
    color: #aab9cb;
    background: transparent;
    border-color: transparent;
    padding: 7px 12px;
}
QPushButton#modeButton:hover { color: #e8eff8; background: #1c3042; }
QPushButton#modeButton:checked {
    color: #a5f4e6;
    background: #1d3b41;
    border-color: #345e63;
}
QPushButton#modeButton:focus { border-color: #81ead7; }
QPushButton#starButton {
    color: #f1be7c;
    background: #2a241e;
    border-color: #524131;
    font-size: 16px;
}
QPushButton#starButton:hover, QPushButton#starButton[rated="true"] {
    background: #392d20;
    border-color: #795d3d;
}
QPushButton#starButton:focus { border-color: #f1be7c; }
QPushButton#starButton:disabled { color: #8495a9; border-color: #26364a; }
QPushButton#dangerButton, QPushButton[quizAnswer="true"]#dangerButton:disabled {
    color: #ffb9bc;
    background: #37242e;
    border-color: #71434e;
}
QPushButton#dangerButton:hover { background: #4c2c38; }
QPushButton#dangerButton:focus { border-color: #ffb9bc; }
QPushButton[quizAnswer="true"] { text-align: left; padding-left: 14px; }
QPushButton[quizAnswer="true"]#primaryButton:disabled {
    color: #a5f4e6;
    background: #1d3939;
    border-color: #468376;
}
QPushButton#relationButton {
    text-align: left;
    background: #152232;
    border-color: #2d3d53;
    font-weight: 500;
}
QPushButton#relationButton:hover { background: #1c3341; border-color: #476674; }
QPushButton#relationButton:focus { border-color: #81ead7; }

QListWidget, QTableWidget {
    color: #e8eff8;
    background: #111b29;
    alternate-background-color: #152132;
    border: 1px solid #293a4f;
    border-radius: 10px;
    padding: 4px;
    outline: none;
}
QListWidget:focus, QTableWidget:focus { border-color: #5a9c98; }
QListWidget::item { border-radius: 6px; padding: 8px 10px; margin: 2px; }
QListWidget::item:hover, QTableWidget::item:hover { background: #1b3042; }
QListWidget::item:selected, QTableWidget::item:selected {
    color: #e7fff9;
    background: #22454d;
}
QTableWidget::item { padding: 6px 10px; }
QHeaderView { background: #1a293b; }
QHeaderView::section {
    color: #b2c4d8;
    background: #1a293b;
    border: 0;
    border-bottom: 1px solid #34465e;
    padding: 9px;
    font-size: 13px;
    font-weight: 650;
}
QMenu {
    background: #152232;
    border: 1px solid #34465e;
    padding: 4px;
}
QMenu::item { padding: 6px 18px; }
QMenu::item:selected { color: #e7fff9; background: #22454d; }
QMenu::item:disabled { color: #8495a9; }
QMenu::separator { height: 1px; background: #34465e; margin: 4px; }
QTabWidget::pane {
    background: #121c2a;
    border: 1px solid #26364a;
    border-radius: 10px;
    top: -1px;
}
QTabBar::tab {
    color: #aab9cb;
    background: #0c121c;
    border: 1px solid transparent;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    padding: 9px 16px;
    margin-right: 3px;
    font-weight: 600;
}
QTabBar::tab:hover { color: #e8eff8; background: #1a2839; }
QTabBar::tab:selected {
    color: #a5f4e6;
    background: #162932;
    border-color: #34565c;
}
QTabBar::tab:focus { border-color: #81ead7; }
QScrollArea { background: transparent; border: 0; }
QScrollBar:vertical { background: transparent; width: 9px; margin: 2px; }
QScrollBar:horizontal { background: transparent; height: 9px; margin: 2px; }
QScrollBar::handle { background: #3b516b; border-radius: 3px; min-height: 28px; min-width: 28px; }
QScrollBar::handle:hover { background: #5a748c; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
QStatusBar {
    color: #9caec3;
    background: #101824;
    border-top: 1px solid #222f40;
    font-size: 12px;
}
QStatusBar::item { border: 0; }
QToolTip {
    color: #e8eff8;
    background: #192838;
    border: 1px solid #3b516b;
    padding: 6px;
}
"""


def apply_theme(application: QApplication) -> None:
    application.setStyle("Fusion")
    application.styleHints().setColorScheme(Qt.ColorScheme.Dark)
    palette = QPalette()
    colors = {
        QPalette.Window: "#0c121c",
        QPalette.WindowText: TEXT_COLOR,
        QPalette.Base: "#111b29",
        QPalette.AlternateBase: "#152132",
        QPalette.Text: TEXT_COLOR,
        QPalette.Button: "#1a2839",
        QPalette.ButtonText: TEXT_COLOR,
        QPalette.BrightText: "#ffb9bc",
        QPalette.PlaceholderText: MUTED_COLOR,
        QPalette.Highlight: "#285653",
        QPalette.HighlightedText: "#effffb",
        QPalette.Link: ACCENT_COLOR,
        QPalette.ToolTipBase: "#192838",
        QPalette.ToolTipText: TEXT_COLOR,
    }
    for role, color in colors.items():
        palette.setColor(role, QColor(color))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        palette.setColor(QPalette.Disabled, role, QColor("#8495a9"))
    application.setPalette(palette)
    application.setStyleSheet(APP_STYLESHEET)
