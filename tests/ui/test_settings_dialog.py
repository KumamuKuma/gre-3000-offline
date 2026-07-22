from PySide6.QtWidgets import QMessageBox

from gre_vocab_app.domain import StudyMode
from gre_vocab_app.ui.settings_dialog import SettingsDialog


def test_settings_voice_rate_and_mode_emit_typed_values(qtbot):
    dialog = SettingsDialog()
    qtbot.addWidget(dialog)
    assert [dialog.mode_combo.itemData(index) for index in range(4)] == [
        StudyMode.READING,
        StudyMode.BRIEF,
        StudyMode.RECALL,
        StudyMode.QUIZ,
    ]
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
            dialog.mode_combo.findData(StudyMode.QUIZ)
        )
    assert mode.args == [StudyMode.QUIZ]
    assert mode.args[0] is StudyMode.QUIZ

    dialog.set_default_mode(StudyMode.BRIEF)
    assert dialog.mode_combo.currentData() == StudyMode.BRIEF

    with qtbot.waitSignal(dialog.autoSpeakChanged) as auto_speak:
        dialog.auto_speak_checkbox.setChecked(True)
    assert auto_speak.args == [True]

    with qtbot.waitSignal(dialog.exportProgressRequested):
        dialog.export_button.click()
    with qtbot.waitSignal(dialog.importProgressRequested):
        dialog.import_button.click()
    dialog.set_auto_speak(False)
    assert not dialog.auto_speak_checkbox.isChecked()


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
    message = calls[0][0][2]
    assert "List 完成次数" in message and "学习位置" in message
    assert "星级评分" in message
    assert "收藏" not in message

    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)
    with qtbot.waitSignal(dialog.clearAllRequested):
        dialog.clear_button.click()


def test_reset_position_has_separate_non_destructive_signal(qtbot):
    dialog = SettingsDialog()
    qtbot.addWidget(dialog)
    with qtbot.waitSignal(dialog.resetPositionRequested):
        dialog.reset_button.click()


def test_settings_distinguishes_default_voice_fallback_from_unavailable(qtbot):
    dialog = SettingsDialog()
    qtbot.addWidget(dialog)

    dialog.set_voice_names((), using_default_voice=True)
    assert "系统默认" in dialog.voice_combo.currentText()
    assert not dialog.voice_combo.isEnabled()

    dialog.set_voice_names((), using_default_voice=False)
    assert "不可用" in dialog.voice_combo.currentText()
