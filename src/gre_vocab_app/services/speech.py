from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from PySide6.QtCore import QObject, Signal
from PySide6.QtTextToSpeech import QTextToSpeech, QVoice


@dataclass(frozen=True, slots=True)
class VoiceOption:
    name: str
    locale: str


class SpeechBackend(Protocol):
    @property
    def available(self) -> bool: ...

    def voices(self) -> tuple[VoiceOption, ...]: ...

    def select_voice(self, name: str) -> bool: ...

    def set_rate(self, value: float) -> None: ...

    def say(self, text: str) -> bool: ...


class QtSpeechBackend(QObject):
    errorOccurred = Signal(str, str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._engine: QTextToSpeech | None = None
        self._voices_by_name: dict[str, QVoice] = {}
        try:
            engines = list(QTextToSpeech.availableEngines())
            preferred = next(
                (name for name in ("sapi", "winrt") if name in engines),
                next((name for name in engines if name != "mock"), None),
            )
            if preferred is not None:
                self._engine = QTextToSpeech(preferred, self)
                self._engine.errorOccurred.connect(self._on_engine_error)
        except (RuntimeError, TypeError) as error:
            self.errorOccurred.emit(
                "朗读服务初始化失败，请检查 Windows 语音设置。",
                f"QTextToSpeech initialization failed: {error}",
            )

    @property
    def available(self) -> bool:
        return self._engine is not None and self._engine.state() is not QTextToSpeech.State.Error

    def _discover_voices(self) -> tuple[VoiceOption, ...]:
        if self._engine is None:
            self._voices_by_name = {}
            return ()
        discovered: dict[tuple[str, str], QVoice] = {}
        for locale in self._engine.availableLocales():
            for voice in self._engine.allVoices(locale):
                key = (voice.name(), voice.locale().name())
                discovered[key] = voice
        options = tuple(
            VoiceOption(name=name, locale=locale)
            for name, locale in sorted(
                discovered,
                key=lambda item: (item[1].casefold(), item[0].casefold()),
            )
        )
        self._voices_by_name = {}
        for option in options:
            self._voices_by_name.setdefault(
                option.name, discovered[(option.name, option.locale)]
            )
        return options

    def voices(self) -> tuple[VoiceOption, ...]:
        try:
            return self._discover_voices()
        except (RuntimeError, TypeError) as error:
            self.errorOccurred.emit(
                "无法读取 Windows 语音列表。",
                f"QTextToSpeech voice discovery failed: {error}",
            )
            return ()

    def select_voice(self, name: str) -> bool:
        if self._engine is None:
            return False
        self._discover_voices()
        voice = self._voices_by_name.get(name)
        if voice is None:
            return False
        try:
            self._engine.setLocale(voice.locale())
            self._engine.setVoice(voice)
            return True
        except (RuntimeError, TypeError) as error:
            self.errorOccurred.emit(
                "无法切换朗读语音。",
                f"QTextToSpeech setVoice failed for {name!r}: {error}",
            )
            return False

    def set_rate(self, value: float) -> None:
        if self._engine is not None:
            self._engine.setRate(value)

    def say(self, text: str) -> bool:
        if not self.available or self._engine is None:
            return False
        self._engine.say(text)
        return self._engine.state() is not QTextToSpeech.State.Error

    def _on_engine_error(
        self, reason: QTextToSpeech.ErrorReason, message: str
    ) -> None:
        detail = message or (self._engine.errorString() if self._engine else "")
        self.errorOccurred.emit(
            "朗读失败，请检查 Windows 语音设置。",
            f"QTextToSpeech {reason.name}: {detail}",
        )


class SpeechService(QObject):
    errorOccurred = Signal(str, str)

    def __init__(
        self, backend: SpeechBackend | None = None, parent: QObject | None = None
    ):
        super().__init__(parent)
        self._backend = backend or QtSpeechBackend(self)
        self._voices = tuple(
            voice
            for voice in self._backend.voices()
            if voice.locale.replace("_", "-").casefold().startswith("en")
        )
        backend_error = getattr(self._backend, "errorOccurred", None)
        if backend_error is not None and hasattr(backend_error, "connect"):
            backend_error.connect(self._relay_error)

    @property
    def available(self) -> bool:
        return bool(self._backend.available and self._voices)

    def voice_names(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(voice.name for voice in self._voices))

    def select_voice(self, name: str) -> bool:
        if not self.available or name not in self.voice_names():
            return False
        try:
            return bool(self._backend.select_voice(name))
        except (RuntimeError, TypeError) as error:
            self._emit_exception("无法切换朗读语音。", error)
            return False

    def set_rate(self, value: float) -> None:
        rate = max(-1.0, min(1.0, float(value)))
        try:
            self._backend.set_rate(rate)
        except (RuntimeError, TypeError) as error:
            self._emit_exception("无法调整朗读速度。", error)

    def speak(self, headword: str) -> bool:
        value = headword.strip()
        if not value or not self.available:
            return False
        try:
            return bool(self._backend.say(value))
        except (RuntimeError, TypeError) as error:
            self._emit_exception("朗读失败，请检查 Windows 语音设置。", error)
            return False

    def _relay_error(self, user_message: str, technical: str) -> None:
        self.errorOccurred.emit(user_message, technical)

    def _emit_exception(self, user_message: str, error: Exception) -> None:
        self.errorOccurred.emit(
            user_message, f"{type(error).__name__}: {error}"
        )

