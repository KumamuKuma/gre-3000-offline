import json

from PySide6.QtGui import QGuiApplication
from PySide6.QtTest import QSignalSpy

from gre_vocab_app.ui.main_window import MainWindow


def test_main_window_restores_intersecting_geometry_and_rejects_offscreen(qtbot):
    assert hasattr(MainWindow, "restore_geometry_state")
    window = MainWindow()
    qtbot.addWidget(window)
    available = QGuiApplication.primaryScreen().availableGeometry()
    valid = json.dumps(
        {
            "x": available.x() + 10,
            "y": available.y() + 10,
            "width": 900,
            "height": 700,
        }
    )

    assert window.restore_geometry_state(valid) is True
    assert window.width() == 900
    assert window.height() == 700
    assert json.loads(window.geometry_state())["width"] == 900

    offscreen = json.dumps(
        {"x": 100000, "y": 100000, "width": 500, "height": 400}
    )
    assert window.restore_geometry_state(offscreen) is False
    assert (window.width(), window.height()) == (980, 760)


def test_main_window_emits_closing_before_accepting_close(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    closing = QSignalSpy(window.closing)

    window.close()

    assert closing.count() == 1
