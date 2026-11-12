from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


TEXT_COLOR = "#252724"
MUTED_COLOR = "#77766f"
ACCENT_COLOR = "#292b28"
WARNING_COLOR = "#81613c"

APP_STYLESHEET = """
QWidget {
    font-family: "Segoe UI Variable Text", "Segoe UI", "Microsoft YaHei";
    font-size: 14px;
}
QWidget#appSurface, QMainWindow, QDialog { background: #faf9f6; }

QToolBar#mainToolbar {
    min-height: 40px;
    background: #faf9f6;
    border: 0;
    border-bottom: 1px solid #dbd9d4;
    padding: 9px 30px;
    spacing: 6px;
}
QToolBar#mainToolbar QToolButton {
    color: #62625b;
    background: transparent;
    border: 1px solid transparent;
    border-radius: 14px;
    padding: 8px 14px;
    font-weight: 600;
}
QToolBar#mainToolbar QToolButton:hover,
QToolBar#mainToolbar QToolButton:focus {
    color: #252724;
    background: #eae9e5;
    border-color: #d9d6d0;
}
QToolBar#mainToolbar QToolButton:checked {
    color: #41433d;
    background: #eeece6;
    border-color: #d6d3cc;
}
QLabel#eyebrow, QLabel#heroEyebrow {
    color: #292b28;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 2px;
}
QLabel#pageTitle {
    color: #252724;
    font-family: "Segoe UI Variable Display", "Segoe UI", "Microsoft YaHei";
    font-size: 30px;
    font-weight: 650;
}
QLabel#headword, QLabel#lookupHeadword, QLabel#heroTitle {
    color: #252724;
    font-family: "Cambria", "Georgia", "Microsoft YaHei";
    font-weight: 400;
}
QLabel#lookupHeadword { font-size: 34px; }
QLabel#sectionTitle { color: #343630; font-size: 17px; font-weight: 650; }
QLabel#sectionHint, QLabel#muted { color: #77766f; }
QLabel#fieldLabel { color: #62625b; font-size: 13px; font-weight: 600; }

QFrame#heroCard { background: transparent; border: 0; }
QLabel#heroTitle { font-size: 46px; }
QLabel#heroSubtitle { color: #77766f; font-size: 15px; }
QFrame#heroMetric { background: transparent; border: 0; }
QLabel#heroMetricLabel { color: #77766f; font-size: 12px; }
QLabel#heroMetricValue {
    color: #292b28;
    font-family: "Cambria", "Georgia", serif;
    font-size: 31px;
    font-weight: 400;
}

QFrame#card, QFrame#searchCard, QFrame#studyCard, QFrame#studyHeader,
QFrame#navigationBar, QFrame#longSentenceCard, QWidget#wordCard,
QWidget#meaningPanel {
    background: #fdfcf9;
    border: 1px solid #e4e1da;
    border-radius: 14px;
}
QWidget#wordCard, QFrame#longSentenceCard {
    background: #fdfcf9;
    border-color: #d6d4ce;
    border-radius: 17px;
}
QFrame#studyHeader, QFrame#navigationBar { border-radius: 14px; }
QFrame#quizAutomationBar {
    background: #eeedeb;
    border: 1px solid #d9d6d0;
    border-radius: 14px;
}
QLabel#longSentenceText {
    color: #252724;
    font-family: "Cambria", "Georgia", "Microsoft YaHei";
    font-size: 26px;
    font-weight: 400;
}
QLabel#longSentenceNotesHeading {
    color: #62625b;
    border-top: 1px solid #d9d6d0;
    padding-top: 18px;
    font-size: 15px;
    font-weight: 650;
}
QFrame#longSentenceNoteCard {
    background: #f0efec;
    border: 1px solid #dbd9d4;
    border-radius: 12px;
}
QLabel#longSentenceNoteLabel, QLabel#countBadge {
    color: #41433d;
    background: #eeece6;
    border: 1px solid #d7d5cf;
    border-radius: 14px;
    padding: 4px 9px;
    font-weight: 650;
}
QLabel#longSentenceNoteText { font-size: 15px; }

QLabel#headword { font-size: 46px; }
QLabel#phonetic { color: #767165; font-size: 16px; }
QLabel#definition { color: #252724; font-size: 17px; font-weight: 600; }
QLabel#exampleText {
    font-family: "Cambria", "Georgia", "Microsoft YaHei";
    font-size: 17px;
}
QLabel#lookupTranslation, QLabel#lookupOnline, QLabel#notePreview {
    background: #efeeeb;
    border: 1px solid #dedcd6;
    border-radius: 14px;
    padding: 14px;
    font-size: 15px;
}
QLabel#lookupOnline { background: #edecea; border-color: #dad7d1; }
QLabel#sourceBadge {
    color: #81613c;
    background: #f3ecdc;
    border: 1px solid #ded0b7;
    border-radius: 14px;
    padding: 5px 9px;
    font-weight: 650;
}
QLabel#positionPill, QLabel#shortcutBadge {
    color: #635e51;
    background: #faf9f6;
    border: 1px solid #dbd8d2;
    border-radius: 14px;
    padding: 5px 9px;
    font-family: "Segoe UI Variable Text", "Segoe UI", "Microsoft YaHei";
    font-size: 12px;
    font-weight: 600;
}
QLabel#emptyState {
    color: #62625b;
    background: #fdfcf9;
    border: 1px dashed #c6c3ba;
    border-radius: 12px;
    padding: 20px;
}

QLineEdit, QComboBox, QPlainTextEdit {
    color: #252724;
    background: #fdfcf9;
    border: 1px solid #d8d5cc;
    border-radius: 14px;
    padding: 8px 11px;
    selection-color: #434037;
    selection-background-color: #e8e5dd;
}
QLineEdit, QComboBox { min-height: 21px; }
QLineEdit:hover, QComboBox:hover, QPlainTextEdit:hover { border-color: #b2aea2; }
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus { border-color: #292b28; }
QLineEdit:disabled, QComboBox:disabled { color: #989791; border-color: #e4e1da; }
QLineEdit#largeSearch { min-height: 24px; font-size: 15px; padding: 8px 13px; }
QPlainTextEdit#noteEditor { padding: 13px; font-size: 16px; }
QComboBox QAbstractItemView {
    background: #fdfcf9;
    border: 1px solid #d8d5cc;
    selection-color: #252724;
    selection-background-color: #e7e5e1;
}
QPushButton {
    color: #544f44;
    background: #faf9f6;
    border: 1px solid #d8d5cc;
    border-radius: 14px;
    padding: 8px 13px;
    font-weight: 600;
}
QPushButton:hover {
    color: #444037;
    background: #ebeae7;
    border-color: #b4b0a4;
}
QPushButton:pressed { background: #e4e2dd; }
QPushButton:focus { border-color: #292b28; }
QPushButton:disabled {
    color: #989791;
    background: #edebe8;
    border-color: #e4e1da;
}
QPushButton#primaryButton:enabled, QDialogButtonBox QPushButton:default:enabled {
    color: #ffffff;
    background: #292b28;
    border-color: #292b28;
    font-weight: 750;
}
QPushButton#primaryButton:hover, QDialogButtonBox QPushButton:default:hover {
    background: #41433d;
    border-color: #41433d;
}
QPushButton#primaryButton:pressed, QDialogButtonBox QPushButton:default:pressed {
    background: #171916;
    border-color: #171916;
}
QPushButton#primaryButton:focus, QDialogButtonBox QPushButton:default:focus {
    border-color: #a49e8f;
}
QPushButton#heroActionButton, QPushButton#outlineButton:enabled,
QPushButton#revealButton {
    color: #41433d;
    background: #f2f2f0;
    border-color: #d8d5cf;
}
QPushButton#heroActionButton:hover, QPushButton#outlineButton:hover,
QPushButton#outlineButton:checked, QPushButton#revealButton:hover {
    color: #514d42;
    background: #eae9e5;
    border-color: #a19b8c;
}
QPushButton#heroActionButton:focus, QPushButton#outlineButton:focus,
QPushButton#revealButton:focus { border-color: #292b28; }
QPushButton#compactButton { min-width: 18px; padding: 5px 9px; }
QPushButton#backButton:enabled { color: #615c4f; background: #f0efed; }
QPushButton#modeButton {
    color: #62625b;
    background: transparent;
    border-color: transparent;
    padding: 7px 12px;
}
QPushButton#modeButton:hover { color: #252724; background: #eeedea; }
QPushButton#modeButton:checked {
    color: #41433d;
    background: #e6e5e1;
    border-color: #d2cfc7;
}
QPushButton#modeButton:focus { border-color: #292b28; }
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
QPushButton#starButton:disabled { color: #989791; border-color: #e4e1da; }
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
    background: #e9e8e5;
    border-color: #bbb6ab;
}
QPushButton#relationButton {
    text-align: left;
    background: #f0efed;
    border-color: #dcdad5;
    font-weight: 500;
}
QPushButton#relationButton:hover { background: #ebeae7; border-color: #b2ada0; }
QPushButton#relationButton:focus { border-color: #292b28; }

QListWidget, QTableWidget {
    color: #252724;
    background: #fdfcf9;
    alternate-background-color: #f4f2ed;
    border: 1px solid #d9d7d1;
    border-radius: 14px;
    padding: 4px;
    outline: none;
}
QListWidget:focus, QTableWidget:focus { border-color: #a19b8c; }
QListWidget::item { border-radius: 6px; padding: 8px 10px; margin: 2px; }
QListWidget::item:hover, QTableWidget::item:hover { background: #ebeae7; }
QListWidget::item:selected, QTableWidget::item:selected {
    color: #444138;
    background: #e5e3df;
}
QTableWidget::item { padding: 6px 10px; }
QHeaderView { background: #ebeae7; }
QHeaderView::section {
    color: #666153;
    background: #ebeae7;
    border: 0;
    border-bottom: 1px solid #d8d5cc;
    padding: 9px;
    font-size: 13px;
    font-weight: 650;
}
QMenu {
    background: #f0efed;
    border: 1px solid #d8d5cc;
    padding: 4px;
}
QMenu::item { padding: 6px 18px; }
QMenu::item:selected { color: #444138; background: #e5e3df; }
QMenu::item:disabled { color: #989791; }
QMenu::separator { height: 1px; background: #d8d5cc; margin: 4px; }
QTabWidget::pane {
    background: #fdfcf9;
    border: 1px solid #e4e1da;
    border-radius: 14px;
    top: -1px;
}
QTabBar::tab {
    color: #62625b;
    background: #faf9f6;
    border: 1px solid transparent;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    padding: 9px 16px;
    margin-right: 3px;
    font-weight: 600;
}
QTabBar::tab:hover { color: #252724; background: #faf9f6; }
QTabBar::tab:selected {
    color: #41433d;
    background: #ebeae7;
    border-color: #d8d5cf;
}
QTabBar::tab:focus { border-color: #292b28; }
QScrollArea { background: transparent; border: 0; }
QScrollBar:vertical { background: transparent; width: 9px; margin: 2px; }
QScrollBar:horizontal { background: transparent; height: 9px; margin: 2px; }
QScrollBar::handle { background: #b4b0a7; border-radius: 3px; min-height: 28px; min-width: 28px; }
QScrollBar::handle:hover { background: #9c9789; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
QStatusBar {
    color: #77766f;
    background: #faf9f6;
    border-top: 1px solid #dbd9d4;
    font-size: 12px;
}
QStatusBar::item { border: 0; }
QToolTip {
    color: #252724;
    background: #fdfcf9;
    border: 1px solid #b4b0a7;
    padding: 6px;
}

/* Editorial desktop layout: warm paper, quiet type, rounded controls. */
QToolBar#mainToolbar {
    min-height: 46px; padding: 10px 26px; spacing: 10px;
}
QToolBar#mainToolbar QToolButton {
    color: #77766f; background: transparent; border: 0;
    border-bottom: 2px solid transparent; border-radius: 0;
    padding: 10px 15px; font-size: 15px; font-weight: 600;
}
QToolBar#mainToolbar QToolButton:checked {
    color: #252724; background: transparent; border-bottom-color: #292b28;
}
QToolBar#mainToolbar QToolButton:hover { color: #252724; background: #f0eee8; }
QToolBar#mainToolbar QToolButton:focus { background: #eeece6; }
QLabel#heroTitle { font-size: 48px; }
QLabel#heroMetricValue { font-size: 38px; }
QLabel#heroMetricLabel { font-size: 13px; }
QLabel#homeStudyTitle { color: #252724; font-size: 28px; font-weight: 600; }
QFrame#studyCard { background: #f4f2ed; border: 0; border-radius: 24px; }
QPushButton#primaryButton[homeAction="true"] { border-radius: 25px; font-size: 17px; }
QPushButton#heroActionButton { text-align: left; padding-left: 16px; }
QPushButton#textButton { background: transparent; border: 0; padding: 2px 0; color: #62625b; }
QPushButton#textButton:hover { color: #252724; text-decoration: underline; }
QPushButton#textButton:focus { background: #e4e1d9; }
QLineEdit#largeSearch { min-height: 24px; font-size: 14px; padding: 8px 16px; border-radius: 20px; }
QFrame#roundStepper { background: #faf9f6; border: 1px solid #d8d5cc; border-radius: 18px; }
QPushButton#stepperDecrease, QPushButton#stepperIncrease {
    border: 0; background: transparent; padding: 0; font-size: 20px; border-radius: 17px;
}
QPushButton#stepperDecrease:hover, QPushButton#stepperIncrease:hover { background: #eeece6; }
QPushButton#stepperDecrease:focus, QPushButton#stepperIncrease:focus { background: #e4e1d9; }
QLabel#roundStepperValue { border-left: 1px solid #e4e1da; border-right: 1px solid #e4e1da; }
QPushButton#selectionChip { border-radius: 20px; }
QPushButton#selectionChip:checked { color: #ffffff; background: #292b28; border-color: #292b28; }
QPushButton#selectionChip:checked:hover { background: #42443e; border-color: #42443e; }
QPushButton#selectionChip:focus { border: 2px solid #8e8b81; padding: 7px 12px; }
QSlider::groove:horizontal { height: 4px; background: #dfdcd4; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #41433d; border-radius: 2px; }
QSlider::handle:horizontal { width: 16px; margin: -6px 0; background: #faf9f6; border: 1px solid #77766f; border-radius: 8px; }

/* Center the home content as one calm, bounded column. */
QLabel#homeStudyTitle { font-size: 24px; font-weight: 600; }
QLabel#homeInlineValue {
    color: #292b28; font-family: "Cambria", "Georgia", serif;
    font-size: 23px; font-weight: 400;
}
QLabel#heroMetricLabel { font-size: 14px; }
QFrame#studyCard QLabel#fieldLabel, QFrame#studyCard QPushButton#outlineButton { font-weight: 500; }
QPushButton#textButton { font-weight: 500; padding: 6px 4px; }
QPushButton#primaryButton[homeAction="true"] { border-radius: 24px; font-weight: 600; }

/* Settings use the same rounded language without native tab/arrow boxes. */
QWidget#settingsPage { background: #faf9f6; }
QLabel#settingsTitle { color: #252724; font-size: 24px; font-weight: 600; }
QLabel#settingsSection { color: #292b28; font-size: 17px; font-weight: 600; }
QLabel#settingsLabel { color: #343630; font-size: 14px; font-weight: 400; }
QLabel#settingsHint { color: #858178; font-size: 12px; font-weight: 400; }
QFrame#settingsDivider { background: #e4e1d9; border: 0; }
QFrame#settingsNavigation, QFrame#segmentedControl {
    background: #eeece6; border: 0; border-radius: 20px;
}
QFrame#settingsNavigation QPushButton#segmentButton,
QFrame#segmentedControl QPushButton#segmentButton {
    color: #62625b; background: transparent; border: 0;
    border-radius: 16px; padding: 5px 8px; font-weight: 500;
}
QFrame#settingsNavigation QPushButton#segmentButton:hover,
QFrame#segmentedControl QPushButton#segmentButton:hover { background: #e4e1d9; }
QFrame#settingsNavigation QPushButton#segmentButton:checked {
    color: #252724; background: #fdfcf9;
}
QFrame#segmentedControl QPushButton#segmentButton:checked {
    color: #ffffff; background: #292b28;
}
QFrame#settingsNavigation QPushButton#segmentButton:focus,
QFrame#segmentedControl QPushButton#segmentButton:focus { border: 1px solid #8e8b81; padding: 4px 7px; }
QPushButton#settingsClose {
    color: #77766f; background: transparent; border: 0;
    border-radius: 16px; padding: 0; font-size: 23px; font-weight: 400;
}
QPushButton#settingsClose:hover, QPushButton#settingsClose:focus { color: #252724; background: #eeece6; }
QWidget#settingsPage QPushButton { border-radius: 17px; font-weight: 500; padding: 7px 13px; }
QComboBox#settingsChoice { border: 0; padding: 0; font-size: 14px; font-weight: 400; }

"""


def apply_theme(application: QApplication) -> None:
    application.setStyle("Fusion")
    application.styleHints().setColorScheme(Qt.ColorScheme.Light)
    palette = QPalette()
    colors = {
        QPalette.Window: "#faf9f6",
        QPalette.WindowText: TEXT_COLOR,
        QPalette.Base: "#fdfcf9",
        QPalette.AlternateBase: "#f4f2ed",
        QPalette.Text: TEXT_COLOR,
        QPalette.Button: "#faf9f6",
        QPalette.ButtonText: TEXT_COLOR,
        QPalette.Light: "#ffffff",
        QPalette.Midlight: "#e4e3df",
        QPalette.Mid: "#ccc9c1",
        QPalette.Dark: "#b3afa5",
        QPalette.Shadow: "#989387",
        QPalette.BrightText: "#934f43",
        QPalette.PlaceholderText: MUTED_COLOR,
        QPalette.Highlight: "#e8e5dd",
        QPalette.HighlightedText: "#434037",
        QPalette.Link: ACCENT_COLOR,
        QPalette.ToolTipBase: "#fdfcf9",
        QPalette.ToolTipText: TEXT_COLOR,
    }
    for role, color in colors.items():
        palette.setColor(role, QColor(color))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        palette.setColor(QPalette.Disabled, role, QColor("#989791"))
    application.setPalette(palette)
    application.setStyleSheet(APP_STYLESHEET)
