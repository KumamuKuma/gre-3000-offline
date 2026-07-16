from PySide6.QtCore import QObject, Signal

from gre_vocab_app.services.speech import SpeechService, VoiceOption


class FakeSpeechBackend:
    def __init__(self, available=True, *, fail=False):
        self.available = available
        self.fail = fail
        self.rate = 0.0
        self.selected = ""
        self.spoken = []

    def voices(self):
        return (
            VoiceOption(name="Microsoft David", locale="en-US"),
            VoiceOption(name="Microsoft Huihui", locale="zh-CN"),
        )

    def select_voice(self, name):
        self.selected = name
        return name == "Microsoft David"

    def set_rate(self, value):
        self.rate = value

    def say(self, text):
        if self.fail:
            raise RuntimeError("synthetic engine failure")
        self.spoken.append(text)
        return self.available


def test_speech_service_uses_selected_english_voice_and_clamps_rate():
    backend = FakeSpeechBackend()
    service = SpeechService(backend=backend)

    assert service.available is True
    assert service.voice_names() == ("Microsoft David",)
    assert service.select_voice("Microsoft David") is True
    assert service.select_voice("Microsoft Huihui") is False
    service.set_rate(2.5)
    assert service.speak("inevitable") is True
    assert backend.spoken == ["inevitable"]
    assert backend.rate == 1.0


def test_unavailable_engine_or_blank_text_does_not_raise():
    service = SpeechService(backend=FakeSpeechBackend(available=False))
    assert service.available is False
    assert service.speak("abate") is False

    available = SpeechService(backend=FakeSpeechBackend())
    assert available.speak("   ") is False


def test_backend_failure_emits_user_and_technical_error(qtbot):
    service = SpeechService(backend=FakeSpeechBackend(fail=True))

    with qtbot.waitSignal(service.errorOccurred) as signal:
        assert service.speak("abate") is False

    user_message, technical = signal.args
    assert "朗读" in user_message
    assert "synthetic engine failure" in technical


class FailingDiscoveryBackend(QObject):
    errorOccurred = Signal(str, str)
    available = True

    def voices(self):
        self.errorOccurred.emit("无法读取语音列表。", "voice discovery exploded")
        return ()

    def select_voice(self, _name):
        return False

    def set_rate(self, _value):
        return None

    def say(self, _text):
        return False


def test_discovery_error_is_delivered_after_service_construction(qtbot):
    service = SpeechService(backend=FailingDiscoveryBackend())

    with qtbot.waitSignal(service.errorOccurred) as signal:
        pass

    assert signal.args == ["无法读取语音列表。", "voice discovery exploded"]
