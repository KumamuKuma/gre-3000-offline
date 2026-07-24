from PySide6.QtWidgets import QApplication, QLineEdit, QMessageBox

from gre_vocab_app.domain import StudyMode
from gre_vocab_app.ui.settings_dialog import SettingsDialog
from gre_vocab_app.services.speech import ONLINE_VOICE_NAME


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
    assert dialog.secondary_voice_combo.currentText() == "Microsoft David"

    with qtbot.waitSignal(dialog.voiceSelected) as voice:
        dialog.voice_combo.setCurrentText("Microsoft David")
    assert voice.args == ["Microsoft David"]

    dialog.set_voice_names(
        ("Microsoft Zira", "Microsoft David", "Bob"),
        "Microsoft Zira",
        "Microsoft David",
    )
    with qtbot.waitSignal(dialog.secondaryVoiceSelected) as secondary_voice:
        dialog.secondary_voice_combo.setCurrentText("Bob")
    assert secondary_voice.args == ["Bob"]

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

    with qtbot.waitSignal(dialog.quizWrongStarUpChanged) as wrong_adjustment:
        dialog.quiz_wrong_star_up_checkbox.setChecked(True)
    assert wrong_adjustment.args == [True]
    with qtbot.waitSignal(dialog.quizCorrectStarDownChanged) as correct_adjustment:
        dialog.quiz_correct_star_down_checkbox.setChecked(True)
    assert correct_adjustment.args == [True]

    with qtbot.waitSignal(dialog.exportProgressRequested):
        dialog.export_button.click()
    with qtbot.waitSignal(dialog.importProgressRequested):
        dialog.import_button.click()
    with qtbot.waitSignal(dialog.cloudTokenChanged) as token:
        dialog.cloud_token_input.setText("GRE1-test")
        dialog.cloud_token_input.editingFinished.emit()
    assert token.args == ["GRE1-test"]
    dialog.cloud_token_input.clear()
    with qtbot.waitSignal(dialog.cloudCreateCodeRequested):
        dialog.cloud_create_button.click()
    with qtbot.waitSignal(dialog.cloudUploadRequested):
        dialog.cloud_upload_button.click()
    with qtbot.waitSignal(dialog.cloudDownloadRequested):
        dialog.cloud_download_button.click()
    dialog.set_cloud_token("GRE1-secret")
    dialog.reveal_cloud_token()
    assert dialog.cloud_token_input.text() == "GRE1-secret"
    assert dialog.cloud_token_input.echoMode() == QLineEdit.Normal
    dialog.cloud_copy_button.click()
    assert QApplication.clipboard().text() == "GRE1-secret"
    dialog.set_auto_speak(False)
    assert not dialog.auto_speak_checkbox.isChecked()
    dialog.set_quiz_star_adjustments(
        add_on_wrong=False,
        remove_on_correct=False,
    )
    assert not dialog.quiz_wrong_star_up_checkbox.isChecked()
    assert not dialog.quiz_correct_star_down_checkbox.isChecked()


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
    assert not dialog.secondary_voice_combo.isEnabled()

    dialog.set_voice_names((), using_default_voice=False)
    assert "不可用" in dialog.voice_combo.currentText()

    dialog.set_voice_names(
        (),
        secondary_selected=ONLINE_VOICE_NAME,
        using_default_voice=False,
        secondary_names=(ONLINE_VOICE_NAME,),
    )
    assert dialog.secondary_voice_combo.isEnabled()
    assert dialog.secondary_voice_combo.currentText() == ONLINE_VOICE_NAME
