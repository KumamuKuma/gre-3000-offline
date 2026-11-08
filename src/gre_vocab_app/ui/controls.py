"""Quiet, keyboard-accessible controls shared by the desktop pages."""

from PySide6.QtCore import QEasingCurve, Property, QPropertyAnimation, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QButtonGroup, QCheckBox, QComboBox, QFrame, QHBoxLayout, QPushButton, QSizePolicy


class ToggleSwitch(QCheckBox):
    """A checkbox's semantics with a full-row hit area and an animated switch."""

    def __init__(self, text="", parent=None, *, pill=False):
        super().__init__(text, parent)
        self._pill = pill
        self._position = 0.0
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self._animation = QPropertyAnimation(self, b"thumbPosition", self)
        self._animation.setDuration(140)
        self._animation.setEasingCurve(QEasingCurve.InOutCubic)
        self.toggled.connect(self._animate)

    def _get_position(self):
        return self._position

    def _set_position(self, value):
        self._position = value
        self.update()

    thumbPosition = Property(float, _get_position, _set_position)

    def _animate(self, checked):
        self._animation.stop()
        self._animation.setStartValue(self._position)
        self._animation.setEndValue(1.0 if checked else 0.0)
        self._animation.start()

    def showEvent(self, event):
        # State restoration may block signals; always render the real state.
        self._animation.stop()
        self._set_position(1.0 if self.isChecked() else 0.0)
        super().showEvent(event)

    def checkStateSet(self):
        super().checkStateSet()
        self._animate(self.isChecked())

    def sizeHint(self):
        return QSize(self.fontMetrics().horizontalAdvance(self.text()) + 80, 40 if self._pill else 34)

    def minimumSizeHint(self):
        return self.sizeHint()

    def hitButton(self, position):
        return self.rect().contains(position)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        enabled = self.isEnabled()
        ink = QColor("#252724" if enabled else "#989791")
        edge = QColor("#c8c5bd" if self.hasFocus() or self.underMouse() else "#dedbd4")
        if self._pill:
            painter.setPen(QPen(edge, 1))
            painter.setBrush(QColor("#f2f0eb" if self.isChecked() else "#faf9f6"))
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 20, 20)
        elif self.hasFocus():
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor("#77766e"), 1, Qt.DashLine))
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 8, 8)

        padding = 14 if self._pill else 4
        track = QRectF(self.width() - padding - 40, (self.height() - 22) / 2, 40, 22)
        # Mirror geometry for right-to-left layouts as well as text alignment.
        rtl = self.layoutDirection() == Qt.RightToLeft
        if rtl:
            track.moveLeft(padding)
        if not self._animation.state() == QPropertyAnimation.Running:
            self._position = 1.0 if self.isChecked() else 0.0
        position = 1.0 - self._position if rtl else self._position
        painter.setPen(Qt.NoPen)
        off = QColor("#d6d4ce" if enabled else "#e5e3de")
        on = QColor("#292b28" if enabled else "#a7a69f")
        mix = self._position
        painter.setBrush(QColor.fromRgbF(
            off.redF() * (1 - mix) + on.redF() * mix,
            off.greenF() * (1 - mix) + on.greenF() * mix,
            off.blueF() * (1 - mix) + on.blueF() * mix,
        ))
        painter.drawRoundedRect(track, 11, 11)
        painter.setBrush(QColor("#ffffff"))
        painter.drawEllipse(QRectF(track.left() + 3 + position * 18, track.top() + 3, 16, 16))
        text_rect = QRectF(padding, 0, self.width() - 2 * padding - 52, self.height())
        if rtl:
            text_rect.moveLeft(padding + 52)
        painter.setPen(ink)
        painter.setFont(self.font())
        painter.drawText(text_rect, Qt.AlignVCenter | (Qt.AlignRight if rtl else Qt.AlignLeft), self.text())


class SelectionChip(QPushButton):
    """A full-surface multi-select button; selection never relies on a tick."""

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setObjectName("selectionChip")
        self.setCheckable(True)
        self.setMinimumHeight(40)
        self.setCursor(Qt.PointingHandCursor)


class SegmentedControl(QFrame):
    """An exclusive, accessible row of choices with typed item data."""

    currentIndexChanged = Signal(int)

    def __init__(self, items, parent=None, *, navigation=False):
        super().__init__(parent)
        self.setObjectName("settingsNavigation" if navigation else "segmentedControl")
        self._items = tuple(items)
        self._index = -1
        self.buttons = []
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        row = QHBoxLayout(self)
        row.setContentsMargins(4, 4, 4, 4)
        row.setSpacing(2)
        for index, (text, _data) in enumerate(self._items):
            button = QPushButton(text)
            button.setObjectName("segmentButton")
            button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor)
            button.setMinimumHeight(32)
            button.setAutoDefault(False)
            self.group.addButton(button, index)
            row.addWidget(button, 1)
            self.buttons.append(button)
        self.group.idClicked.connect(self.setCurrentIndex)
        if self._items:
            self.setCurrentIndex(0)

    def itemData(self, index):
        return self._items[index][1]

    def currentData(self):
        return self.itemData(self._index) if self._index >= 0 else None

    def currentIndex(self):
        return self._index

    def findData(self, value):
        return next((index for index, (_text, data) in enumerate(self._items) if data == value), -1)

    def setCurrentIndex(self, index):
        if not 0 <= index < len(self._items) or self._index == index:
            return
        self._index = index
        self.buttons[index].setChecked(True)
        self.currentIndexChanged.emit(index)


class RoundedComboBox(QComboBox):
    """Keep Qt's popup and keyboard behavior, replace its native arrow box."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("settingsChoice")
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.currentTextChanged.connect(self.setToolTip)

    def sizeHint(self):
        return QSize(250, 40)

    def minimumSizeHint(self):
        return QSize(140, 40)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor("#ece9e2" if self.underMouse() else "#f1efe9"))
        painter.setPen(QPen(QColor("#aaa69b"), 1) if self.hasFocus() else Qt.NoPen)
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 18, 18)
        painter.setPen(QColor("#252724" if self.isEnabled() else "#989791"))
        painter.setFont(self.font())
        text = self.fontMetrics().elidedText(self.currentText(), Qt.ElideRight, max(0, self.width() - 52))
        painter.drawText(QRectF(16, 0, self.width() - 52, self.height()), Qt.AlignVCenter | Qt.AlignLeft, text)
        x, y = self.width() - 22, self.height() / 2
        chevron = QPainterPath()
        chevron.moveTo(x - 4, y - 2)
        chevron.lineTo(x, y + 2)
        chevron.lineTo(x + 4, y - 2)
        painter.setPen(QPen(QColor("#62625b" if self.isEnabled() else "#b3afa5"), 1.3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawPath(chevron)
