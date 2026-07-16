from PySide6.QtWidgets import QMessageBox

from gre_vocab_app.domain import StudyMode
from gre_vocab_app.ui.settings_dialog import SettingsDialog


def test_settings_voice_rate_and_mode_emit_typed_values(qtbot):
    dialog = SettingsDialog()
    qtbot.addWidget(dialog)
    dialog.set_voice_names(("Microsoft Zira", "Microsoft David"), "Microsoft Zira")
    assert dialog.voice_combo.currentText() == "Microsoft Zira"

    with qtbot.waitSignal(dialog.voiceSelected) as voice:
        dialog.voice_combo.setCurrentText("Microsoft David")
    assert voice.args == ["Microsoft David"]

    with qtbot.waitSignal(dialog.rateChanged) as rate:
        dialog.rate_slider.setValue(4)
    assert rate.args == [0.4]

    with qtbot.waitSignal(dialog.defaultModeChanged) as mode:
        dialog.mode_combo.setCurrentIndex(
            dialog.mode_combo.findData(StudyMode.RECALL)
        )
    assert mode.args == [StudyMode.RECALL]


def test_clear_all_requires_named_confirmation(qtbot, monkeypatch):
    dialog = SettingsDialog()
    qtbot.addWidget(dialog)
    calls = []

    def decline(*args, **kwargs):
        calls.append((args, kwargs))
        return QMessageBox.No

    monkeypatch.setattr(QMessageBox, "question", decline)
    with qtbot.assertNotEmitted(dialog.clearAllRequested):
        dialog.clear_button.click()
    assert calls
    assert "收藏" in calls[0][0][2] and "学习进度" in calls[0][0][2]

    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)
    with qtbot.waitSignal(dialog.clearAllRequested):
        dialog.clear_button.click()


def test_reset_position_has_separate_non_destructive_signal(qtbot):
    dialog = SettingsDialog()
    qtbot.addWidget(dialog)
    with qtbot.waitSignal(dialog.resetPositionRequested):
        dialog.reset_button.click()
