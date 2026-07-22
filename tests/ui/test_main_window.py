import json

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QRect
from PySide6.QtGui import QGuiApplication
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QMessageBox

from gre_vocab_app.ui.main_window import MainWindow


def test_main_window_exposes_word_list_navigation_and_find_signal(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)

    window.show_word_list()
    assert window.stack.currentWidget() is window.word_list_page
    window.show_home()
    assert window.stack.currentWidget() is window.home_page

    with qtbot.waitSignal(window.wordListRequested):
        window.word_list_action.trigger()
    with qtbot.waitSignal(window.wordListRequested):
        window.home_page.word_list_button.click()
    with qtbot.waitSignal(window.findRequested):
        window.find_shortcut.activated.emit()

    assert window.word_list_action.text() == "词表"


def test_home_search_results_fit_without_overlapping_actions_at_minimum_size(
    qtbot, sample_word
):
    window = MainWindow()
    qtbot.addWidget(window)
    window.resize(820, 620)
    window.show()
    page = window.home_page
    page.search_edit.setText("a")
    page.set_results([sample_word])
    qtbot.waitUntil(page.results.isVisible)

    start_bottom = page.start_button.mapTo(
        page, page.start_button.rect().bottomLeft()
    ).y()
    assert start_bottom < page.results.geometry().top()
    assert page.results.height() >= page.results.minimumSizeHint().height()


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


def test_accepted_guarded_close_also_closes_visible_settings_once(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    window.show_settings()
    qtbot.waitUntil(window.settings_dialog.isVisible)
    closing = QSignalSpy(window.closing)
    window.enable_close_guard()
    window.closing.connect(lambda event: event.accept())

    assert window.close() is True

    assert not window.settings_dialog.isVisible()
    assert closing.count() == 1


def test_accepted_guarded_close_closes_settings_owned_message_boxes(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    window.show_settings()
    message = QMessageBox(window.settings_dialog)
    message.setWindowTitle("确认本地数据操作")
    message.show()
    qtbot.waitUntil(message.isVisible)
    window.enable_close_guard()
    window.closing.connect(lambda event: event.accept())

    assert window.close() is True

    assert not window.settings_dialog.isVisible()
    assert not message.isVisible()


def test_rejected_guarded_close_keeps_visible_settings_open(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    window.show_settings()
    qtbot.waitUntil(window.settings_dialog.isVisible)
    message = QMessageBox(window.settings_dialog)
    message.show()
    qtbot.waitUntil(message.isVisible)
    window.enable_close_guard()
    window.closing.connect(lambda event: event.ignore())

    assert window.close() is False

    assert window.settings_dialog.isVisible()
    assert message.isVisible()

    window.closing.disconnect()
    window.closing.connect(lambda event: event.accept())
    window.close()


def test_geometry_rejects_removed_secondary_and_one_pixel_titlebar(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    available_geometries = [
        screen.availableGeometry() for screen in QGuiApplication.screens()
    ]
    topmost = min(available_geometries, key=lambda geometry: geometry.top())

    removed_secondary = json.dumps(
        {
            "x": max(geometry.right() for geometry in available_geometries) + 200,
            "y": topmost.top() + 20,
            "width": 900,
            "height": 700,
        }
    )
    assert window.restore_geometry_state(removed_secondary) is False

    one_pixel_titlebar = json.dumps(
        {
            "x": topmost.left() + 20,
            "y": topmost.top() - 31,
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


@pytest.mark.parametrize("field", ("x", "y", "width", "height"))
@pytest.mark.parametrize("value", (2**31, -(2**31) - 1))
def test_geometry_rejects_values_outside_qt_signed_int_range(
    qtbot, field, value
):
    window = MainWindow()
    qtbot.addWidget(window)
    available = QGuiApplication.primaryScreen().availableGeometry()
    payload = {"x": 10, "y": 10, "width": 500, "height": 400}
    payload[field] = value

    assert window.restore_geometry_state(json.dumps(payload)) is False
    assert available.contains(window.geometry())


@pytest.mark.parametrize(
    "payload",
    (
        {"x": 2**31 - 1, "y": 0, "width": 2, "height": 400},
        {"x": 0, "y": 2**31 - 1, "width": 500, "height": 2},
    ),
)
def test_geometry_rejects_right_or_bottom_overflow_before_qrect(qtbot, payload):
    window = MainWindow()
    qtbot.addWidget(window)
    available = QGuiApplication.primaryScreen().availableGeometry()

    assert window.restore_geometry_state(json.dumps(payload)) is False
    assert available.contains(window.geometry())


def test_geometry_accepts_negative_coordinates_on_a_secondary_screen(
    qtbot, monkeypatch
):
    window = MainWindow()
    qtbot.addWidget(window)
    secondary = QRect(-1920, -200, 1920, 1080)
    monkeypatch.setattr(
        MainWindow,
        "_target_available_geometry",
        staticmethod(lambda _rectangle: secondary),
    )
    payload = {"x": -1800, "y": -100, "width": 900, "height": 700}

    assert window.restore_geometry_state(json.dumps(payload)) is True
    assert secondary.contains(window.geometry())


def test_pending_write_prompts_are_deleted_after_each_choice(qtbot, monkeypatch):
    window = MainWindow()
    qtbot.addWidget(window)
    monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)
    monkeypatch.setattr(
        QMessageBox,
        "clickedButton",
        lambda self: self.defaultButton(),
    )

    for _ in range(5):
        assert window.confirm_pending_writes() == QMessageBox.Retry
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        QCoreApplication.processEvents()

    assert window.findChildren(QMessageBox) == []
