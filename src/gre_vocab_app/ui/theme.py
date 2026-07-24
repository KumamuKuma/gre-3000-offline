from PySide6.QtWidgets import QApplication


APP_STYLESHEET = """
QWidget {
    color: #172033;
    font-family: "Segoe UI", "Microsoft YaHei UI";
    font-size: 14px;
}
QWidget#appSurface { background: #f3f6fa; }

QToolBar#mainToolbar {
    min-height: 52px;
    background: #0b1220;
    border: 0;
    border-bottom: 1px solid #1e293b;
    padding: 6px 18px;
    spacing: 4px;
}
QToolBar#mainToolbar QToolButton {
    color: #cbd5e1;
    background: transparent;
    border: 0;
    border-radius: 9px;
    padding: 9px 16px;
    font-weight: 650;
}
QToolBar#mainToolbar QToolButton:hover {
    color: #ffffff;
    background: #182235;
}
QToolBar#mainToolbar QToolButton:checked {
    color: #ffffff;
    background: #26334d;
}
QToolBar#mainToolbar::separator {
    width: 1px;
    margin: 8px 10px;
    background: #334155;
}
QLabel#brandMark {
    color: #ffffff;
    font-size: 16px;
    font-weight: 800;
    letter-spacing: 1px;
}
QLabel#brandTag {
    color: #a5b4fc;
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 4px 8px;
    font-size: 11px;
    font-weight: 700;
}

QLabel#eyebrow {
    color: #6366f1;
    font-size: 12px;
    font-weight: 750;
    letter-spacing: 1px;
}
QLabel#pageTitle {
    color: #0f172a;
    font-size: 29px;
    font-weight: 780;
}
QLabel#sectionTitle {
    color: #1e293b;
    font-size: 16px;
    font-weight: 700;
}
QLabel#sectionHint, QLabel#muted { color: #64748b; }
QLabel#fieldLabel {
    color: #475569;
    font-size: 12px;
    font-weight: 700;
}

QFrame#heroCard {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 1,
        stop: 0 #0b1220, stop: 0.55 #111c31, stop: 1 #202c4a
    );
    border: 1px solid #263652;
    border-radius: 22px;
}
QLabel#heroEyebrow {
    color: #a5b4fc;
    font-size: 12px;
    font-weight: 750;
    letter-spacing: 1px;
}
QLabel#heroTitle {
    color: #ffffff;
    font-size: 31px;
    font-weight: 800;
}
QLabel#heroSubtitle {
    color: #cbd5e1;
    font-size: 14px;
}
QFrame#heroMetric {
    background: rgba(255, 255, 255, 20);
    border: 1px solid rgba(255, 255, 255, 42);
    border-radius: 15px;
}
QLabel#heroMetricLabel {
    color: #aebbd0;
    font-size: 11px;
    font-weight: 700;
}
QLabel#heroMetricValue {
    color: #ffffff;
    font-size: 25px;
    font-weight: 800;
}

QFrame#card, QFrame#searchCard, QFrame#studyCard,
QFrame#studyHeader, QFrame#navigationBar,
QWidget#wordCard, QWidget#meaningPanel {
    background: #ffffff;
    border: 1px solid #e1e7ef;
    border-radius: 17px;
}
QFrame#studyCard {
    border: 1px solid #dce3ee;
    border-top: 3px solid #6366f1;
}
QFrame#studyHeader, QFrame#navigationBar {
    background: #ffffff;
    border-color: #e2e8f0;
    border-radius: 14px;
}
QFrame#quizAutomationBar {
    background: #fff7ed;
    border: 1px solid #fed7aa;
    border-radius: 12px;
}
QWidget#wordCard {
    border-radius: 19px;
    border-top: 3px solid #6366f1;
}
QWidget#meaningPanel { border-radius: 17px; }

QLabel#statValue { color: #172033; font-size: 24px; font-weight: 780; }
QLabel#headword { color: #101828; font-size: 36px; font-weight: 800; }
QLabel#phonetic { color: #64748b; font-size: 16px; }
QLabel#definition { color: #172033; font-size: 17px; font-weight: 650; }
QLabel#lookupHeadword { color: #101828; font-size: 30px; font-weight: 800; }
QLabel#lookupTranslation {
    color: #172033;
    background: #eef2ff;
    border: 1px solid #c7d2fe;
    border-radius: 12px;
    padding: 14px;
    font-size: 16px;
    font-weight: 650;
}
QLabel#lookupOnline {
    color: #172033;
    background: #f0fdf4;
    border: 1px solid #bbf7d0;
    border-radius: 12px;
    padding: 14px;
    font-size: 16px;
}
QLabel#sourceBadge {
    color: #9a3412;
    background: #fff7ed;
    border: 1px solid #fed7aa;
    border-radius: 9px;
    padding: 6px 10px;
    font-weight: 750;
}
QLabel#positionPill, QLabel#countBadge, QLabel#shortcutBadge {
    color: #475569;
    background: #f1f5f9;
    border: 1px solid #e2e8f0;
    border-radius: 9px;
    padding: 6px 10px;
    font-weight: 700;
}
QLabel#countBadge {
    color: #4338ca;
    background: #eef2ff;
    border-color: #c7d2fe;
}
QLabel#emptyState {
    color: #64748b;
    background: #ffffff;
    border: 1px dashed #cbd5e1;
    border-radius: 14px;
    padding: 22px;
}

QLineEdit, QComboBox {
    min-height: 22px;
    color: #172033;
    background: #ffffff;
    border: 1px solid #cfd8e6;
    border-radius: 11px;
    padding: 10px 13px;
    selection-color: #ffffff;
    selection-background-color: #6366f1;
}
QLineEdit:hover, QComboBox:hover { border-color: #aab7ca; }
QLineEdit:focus, QComboBox:focus {
    border: 2px solid #6366f1;
    padding: 9px 12px;
}
QLineEdit#largeSearch {
    min-height: 27px;
    font-size: 15px;
    padding: 11px 14px;
}
QLineEdit#largeSearch:focus { padding: 10px 13px; }
QComboBox::drop-down { border: 0; width: 32px; }
QComboBox QAbstractItemView {
    background: #ffffff;
    border: 1px solid #d8e0ec;
    selection-color: #312e81;
    selection-background-color: #eef2ff;
    outline: none;
}

QPushButton {
    color: #334155;
    background: #ffffff;
    border: 1px solid #cfd8e6;
    border-radius: 10px;
    padding: 9px 15px;
    font-weight: 650;
}
QPushButton:hover {
    color: #312e81;
    background: #f7f7ff;
    border-color: #a5b4fc;
}
QPushButton:pressed { background: #eef2ff; }
QPushButton:focus { border-color: #818cf8; }
QPushButton:disabled {
    color: #a0aabb;
    background: #f4f6f9;
    border-color: #e2e8f0;
}
QPushButton#primaryButton {
    color: #ffffff;
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 0,
        stop: 0 #5b5bd6, stop: 1 #7164e8
    );
    border-color: #5b5bd6;
    font-weight: 750;
}
QPushButton#primaryButton:hover {
    color: #ffffff;
    background: #5048c8;
    border-color: #5048c8;
}
QPushButton#outlineButton { color: #4338ca; border-color: #c7d2fe; }
QPushButton#outlineButton:hover { background: #eef2ff; }
QPushButton#compactButton {
    min-width: 18px;
    padding: 6px 9px;
    border-radius: 9px;
}
QPushButton#backButton { color: #475569; background: #f8fafc; }
QPushButton#modeButton {
    color: #64748b;
    background: transparent;
    border-color: transparent;
    padding: 9px 13px;
}
QPushButton#modeButton:hover { color: #312e81; background: #f1f3ff; }
QPushButton#modeButton:checked {
    color: #ffffff;
    background: #1e293b;
    border-color: #1e293b;
}
QPushButton#starButton {
    color: #a16207;
    background: #fffbeb;
    border-color: #fde68a;
    font-size: 16px;
    letter-spacing: 1px;
}
QPushButton#starButton[rated="true"] {
    color: #92400e;
    background: #fef3c7;
    border-color: #fbbf24;
}
QPushButton#revealButton {
    color: #ffffff;
    background: #1e293b;
    border-color: #1e293b;
    padding: 12px;
}
QPushButton#dangerButton {
    color: #b42318;
    background: #fff7f6;
    border-color: #f2c9c5;
}
QPushButton#relationButton {
    text-align: left;
    color: #334155;
    background: #f8fafc;
    border-color: #e2e8f0;
    font-weight: 550;
}
QPushButton#relationButton:hover {
    color: #3730a3;
    background: #eef2ff;
    border-color: #c7d2fe;
}

QListWidget, QTableWidget {
    color: #1e293b;
    background: #ffffff;
    alternate-background-color: #f8fafc;
    border: 1px solid #dfe5ee;
    border-radius: 14px;
    padding: 5px;
    outline: none;
    gridline-color: #edf1f6;
}
QListWidget::item {
    border-radius: 9px;
    padding: 12px 11px;
    margin: 2px;
}
QListWidget::item:hover, QTableWidget::item:hover { background: #f4f3ff; }
QListWidget::item:selected, QTableWidget::item:selected {
    color: #312e81;
    background: #e8e7ff;
}
QTableWidget::item { padding: 8px 8px; }
QHeaderView::section {
    color: #475569;
    background: #f1f5f9;
    border: 0;
    border-bottom: 1px solid #d8e0ea;
    padding: 10px 8px;
    font-size: 12px;
    font-weight: 750;
}

QScrollArea { background: transparent; border: 0; }
QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: #cbd5e1;
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover { background: #94a3b8; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

QStatusBar {
    color: #64748b;
    background: #f8fafc;
    border-top: 1px solid #e2e8f0;
    font-size: 12px;
}
QToolTip {
    color: #f8fafc;
    background: #172033;
    border: 1px solid #334155;
    padding: 6px;
}
"""


def apply_theme(application: QApplication) -> None:
    application.setStyle("Fusion")
    application.setStyleSheet(APP_STYLESHEET)
