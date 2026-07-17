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
    assert window.width() == min(900, available.width())
    assert window.height() == min(700, available.height())
    assert json.loads(window.geometry_state())["width"] == min(
        900, available.width()
    )
    assert available.contains(window.geometry())

    offscreen = json.dumps(
        {"x": 100000, "y": 100000, "width": 500, "height": 400}
    )
    assert window.restore_geometry_state(offscreen) is False
    assert (window.width(), window.height()) == (
        min(980, available.width()),
        min(760, available.height()),
    )
    assert available.contains(window.geometry())


def test_main_window_emits_closing_before_accepting_close(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    closing = QSignalSpy(window.closing)

    try:
        assert window.close() is True
    finally:
        window.deleteLater()

    assert closing.count() == 1


def test_successful_guarded_close_is_not_requested_twice(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    closing = QSignalSpy(window.closing)
    window.enable_close_guard()
    window.closing.connect(lambda event: event.accept())

    assert window.close() is True
    assert closing.count() == 1
    assert window.close() is True
    assert closing.count() == 1


def test_geometry_rejects_removed_secondary_and_one_pixel_titlebar(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    available = QGuiApplication.primaryScreen().availableGeometry()

    removed_secondary = json.dumps(
        {
            "x": available.right() + 200,
            "y": available.top() + 20,
            "width": 900,
            "height": 700,
        }
    )
    assert window.restore_geometry_state(removed_secondary) is False

    one_pixel_titlebar = json.dumps(
        {
            "x": available.right(),
            "y": available.top() + 20,
            "width": 500,
            "height": 400,
        }
    )
    assert window.restore_geometry_state(one_pixel_titlebar) is False


def test_geometry_clamps_oversized_and_partial_offscreen_to_target_screen(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    available = QGuiApplication.primaryScreen().availableGeometry()

    oversized = json.dumps(
        {
            "x": available.left() + 10,
            "y": available.top() + 10,
            "width": available.width() + 500,
            "height": available.height() + 500,
        }
    )
    assert window.restore_geometry_state(oversized) is True
    assert window.geometry() == available

    partial_width = max(400, available.width() // 2)
    partial_height = max(300, available.height() // 2)
    partially_offscreen = json.dumps(
        {
            "x": available.left() - 100,
            "y": available.top() + 20,
            "width": partial_width,
            "height": partial_height,
        }
    )
    assert window.restore_geometry_state(partially_offscreen) is True
    assert available.contains(window.geometry())
