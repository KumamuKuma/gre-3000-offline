from __future__ import annotations

import html
import re
import urllib.parse

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QLabel


TOKEN = re.compile(r"[A-Za-z]+(?:['’-][A-Za-z]+)*")


def lookup_html(text: str) -> str:
    pieces: list[str] = []
    cursor = 0
    for match in TOKEN.finditer(text):
        pieces.append(html.escape(text[cursor : match.start()]))
        token = match.group(0)
        href = urllib.parse.quote(token, safe="")
        pieces.append(
            f'<a href="lookup:{href}" style="color:#4338ca;'
            f'text-decoration:none;">{html.escape(token)}</a>'
        )
        cursor = match.end()
    pieces.append(html.escape(text[cursor:]))
    return "".join(pieces).replace("\n", "<br>")


class LookupLabel(QLabel):
    lookupRequested = Signal(str)
    selectionTranslationRequested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._plain_text = ""
        self.setWordWrap(True)
        self.setTextFormat(Qt.RichText)
        self.setTextInteractionFlags(
            Qt.TextBrowserInteraction | Qt.TextSelectableByKeyboard
        )
        self.setOpenExternalLinks(False)
        self.linkActivated.connect(self._activate_link)
        self._selection_on_press = ""

    def set_lookup_text(self, text: str) -> None:
        self._plain_text = text
        super().setText(lookup_html(text))

    def setText(self, text: str) -> None:
        self._plain_text = text
        super().setText(text)

    def text(self) -> str:
        return self._plain_text

    def clear(self) -> None:
        self._plain_text = ""
        super().clear()

    def _activate_link(self, href: str) -> None:
        if href.startswith("lookup:"):
            self.lookupRequested.emit(
                urllib.parse.unquote(href.removeprefix("lookup:"))
            )

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._selection_on_press = self.selectedText()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        super().mouseReleaseEvent(event)
        selected = (
            self.selectedText()
            .replace("\u2029", "\n")
            .replace("\u2028", "\n")
            .strip()
        )
        if selected and selected != self._selection_on_press:
            self.selectionTranslationRequested.emit(selected)
