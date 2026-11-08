from PySide6.QtCore import QPoint, QSignalBlocker, Qt
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QDialogButtonBox

from gre_vocab_app.domain import SourceList
from gre_vocab_app.ui.controls import RoundedComboBox, SegmentedControl, ToggleSwitch
from gre_vocab_app.ui.home_page import ListScopeDialog


def test_toggle_accepts_whole_row_click_and_space_without_duplicate_signals(qtbot):
    switch = ToggleSwitch("自动朗读", pill=True)
    qtbot.addWidget(switch)
    switch.resize(280, 40)
    switch.show()
    changed = QSignalSpy(switch.toggled)
    # The text area is clickable, not just the small thumb on the right.
    qtbot.mouseClick(switch, Qt.LeftButton, pos=QPoint(12, 20))
    assert switch.isChecked()
    assert changed.count() == 1
    switch.setFocus()
    qtbot.keyClick(switch, Qt.Key_Space)
    assert not switch.isChecked()
    assert changed.count() == 2
    switch.setEnabled(False)
    qtbot.mouseClick(switch, Qt.LeftButton, pos=QPoint(12, 20))
    assert not switch.isChecked()
    assert changed.count() == 2


def test_restoring_toggle_with_blocked_signals_preserves_model_state(qtbot):
    switch = ToggleSwitch("自动朗读")
    qtbot.addWidget(switch)
    changed = QSignalSpy(switch.toggled)
    with QSignalBlocker(switch):
        switch.setChecked(True)
    switch.show()
    qtbot.wait(160)
    assert switch.isChecked()
    assert changed.count() == 0
    switch.click()
    assert not switch.isChecked()
    assert changed.count() == 1


def test_list_chips_keep_book_order_and_require_at_least_one_selection(qtbot):
    lists = tuple(SourceList(f"list{i}", f"List {i}", 100, i * 100, i * 100 + 99) for i in range(32))
    dialog = ListScopeDialog(lists, ("list0",))
    qtbot.addWidget(dialog)
    dialog.list_buttons["list31"].click()
    dialog.list_buttons["list2"].click()
    assert dialog.selected_keys() == ("list0", "list2", "list31")
    assert not dialog.all_checkbox.isChecked()
    dialog.all_checkbox.click()
    assert len(dialog.selected_keys()) == 32
    dialog.list_buttons["list31"].click()
    assert not dialog.all_checkbox.isChecked()
    dialog.all_checkbox.click()
    dialog.all_checkbox.click()
    assert dialog.selected_keys() == ()
    assert not dialog.buttons.button(QDialogButtonBox.Ok).isEnabled()
    dialog.list_buttons["list31"].click()
    assert dialog.buttons.button(QDialogButtonBox.Ok).isEnabled()


def test_segmented_control_click_and_keyboard_keep_one_active_choice(qtbot):
    control = SegmentedControl((("阅读", "reading"), ("回忆", "recall")))
    qtbot.addWidget(control)
    control.show()
    changed = QSignalSpy(control.currentIndexChanged)
    qtbot.mouseClick(control.buttons[1], Qt.LeftButton)
    assert control.currentData() == "recall"
    assert changed.count() == 1
    control.buttons[1].click()
    assert changed.count() == 1
    control.buttons[0].setFocus()
    qtbot.keyClick(control.buttons[0], Qt.Key_Space)
    assert control.currentData() == "reading"
    assert [button.isChecked() for button in control.buttons] == [True, False]
    assert changed.count() == 2


def test_rounded_voice_choice_retains_keyboard_selection(qtbot):
    choice = RoundedComboBox()
    qtbot.addWidget(choice)
    choice.addItems(("Microsoft Zira", "Microsoft David"))
    choice.show()
    choice.setFocus()
    with qtbot.waitSignal(choice.currentTextChanged) as selected:
        qtbot.keyClick(choice, Qt.Key_Down)
    assert selected.args == ["Microsoft David"]
