from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from PySide6.QtCore import QObject, QTimer, Signal
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
        self._pending_errors: list[tuple[str, str]] = []
        self._retain_errors = True
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
            self._report_error(
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
        selection_order = sorted(
            options,
            key=lambda option: (
                option.name.casefold(),
                not option.locale.replace("_", "-").casefold().startswith("en"),
                option.locale.casefold(),
            ),
        )
        for option in selection_order:
            self._voices_by_name.setdefault(
                option.name, discovered[(option.name, option.locale)]
            )
        return options

    def voices(self) -> tuple[VoiceOption, ...]:
        try:
            return self._discover_voices()
        except (RuntimeError, TypeError) as error:
            self._report_error(
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
            self._report_error(
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
        self._report_error(
            "朗读失败，请检查 Windows 语音设置。",
            f"QTextToSpeech {reason.name}: {detail}",
        )

    def _report_error(self, user_message: str, technical: str) -> None:
        if self._retain_errors:
            self._pending_errors.append((user_message, technical))
        self.errorOccurred.emit(user_message, technical)

    def take_pending_errors(self) -> tuple[tuple[str, str], ...]:
        errors = tuple(self._pending_errors)
        self._pending_errors.clear()
        self._retain_errors = False
        return errors


class SpeechService(QObject):
    errorOccurred = Signal(str, str)
    availabilityChanged = Signal(bool)

    def __init__(
        self, backend: SpeechBackend | None = None, parent: QObject | None = None
    ):
        super().__init__(parent)
        self._backend = backend or QtSpeechBackend(self)
        self._pending_errors: list[tuple[str, str]] = []
        self._error_flush_scheduled = False
        self._voices: tuple[VoiceOption, ...] = ()
        self._available = bool(self._backend.available)
        self._using_default_voice = self._available
        self._primary_voice_name: str | None = None
        self._active_voice_name: str | None = None
        self._availability_notice: str | None = None
        backend_error = getattr(self._backend, "errorOccurred", None)
        if backend_error is not None and hasattr(backend_error, "connect"):
            backend_error.connect(self._relay_error)
        take_pending = getattr(self._backend, "take_pending_errors", None)
        if callable(take_pending):
            for user_message, technical in take_pending():
                self._queue_error(user_message, technical)
        self._voices = tuple(
            voice
            for voice in self._backend.voices()
            if voice.locale.replace("_", "-").casefold().startswith("en")
        )
        backend_available = bool(self._backend.available)
        self._using_default_voice = backend_available and not self._voices
        self._available = backend_available
        if not backend_available:
            self._availability_notice = (
                "未检测到可用的语音引擎，朗读功能已禁用；其他功能仍可正常使用。"
            )
        elif self._using_default_voice:
            self._availability_notice = (
                "未检测到英文语音，将使用系统默认语音；建议安装英文语音包。"
            )
        else:
            self._availability_notice = None

    @property
    def available(self) -> bool:
        return self._available

    @property
    def using_default_voice(self) -> bool:
        return self._using_default_voice

    def take_availability_notice(self) -> str | None:
        notice = self._availability_notice
        self._availability_notice = None
        return notice

    def voice_names(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(voice.name for voice in self._voices))

    def select_voice(self, name: str) -> bool:
        if not self.available or name not in self.voice_names():
            return False
        try:
            selected = bool(self._backend.select_voice(name))
            if selected:
                self._primary_voice_name = name
                self._active_voice_name = name
            return selected
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
        if not self._backend.available:
            self._set_available(False)
            return False
        try:
            if (
                self._primary_voice_name
                and self._active_voice_name != self._primary_voice_name
            ):
                if not self._backend.select_voice(self._primary_voice_name):
                    return False
                self._active_voice_name = self._primary_voice_name
            spoken = bool(self._backend.say(value))
            if not spoken and not self._backend.available:
                self._set_available(False)
            return spoken
        except (RuntimeError, TypeError) as error:
            self._emit_exception("朗读失败，请检查 Windows 语音设置。", error)
            return False

    def speak_with_voice(self, text: str, voice_name: str) -> bool:
        value = text.strip()
        if (
            not value
            or not self.available
            or voice_name not in self.voice_names()
        ):
            return False
        if not self._backend.available:
            self._set_available(False)
            return False
        try:
            if self._active_voice_name != voice_name:
                if not self._backend.select_voice(voice_name):
                    return False
                self._active_voice_name = voice_name
            spoken = bool(self._backend.say(value))
            if not spoken and not self._backend.available:
                self._set_available(False)
            return spoken
        except (RuntimeError, TypeError) as error:
            self._emit_exception("备用音源朗读失败，请检查 Windows 语音设置。", error)
            return False

    def _relay_error(self, user_message: str, technical: str) -> None:
        self._set_available(bool(self._backend.available))
        self._queue_error(user_message, technical)

    def _set_available(self, available: bool) -> None:
        value = bool(available)
        if value == self._available:
            return
        self._available = value
        self.availabilityChanged.emit(value)

    def _emit_exception(self, user_message: str, error: Exception) -> None:
        self._set_available(bool(self._backend.available))
        self._queue_error(
            user_message, f"{type(error).__name__}: {error}"
        )

    def _queue_error(self, user_message: str, technical: str) -> None:
        self._pending_errors.append((user_message, technical))
        if not self._error_flush_scheduled:
            self._error_flush_scheduled = True
            QTimer.singleShot(0, self._flush_errors)

    def _flush_errors(self) -> None:
        errors = tuple(self._pending_errors)
        self._pending_errors.clear()
        self._error_flush_scheduled = False
        for user_message, technical in errors:
            self.errorOccurred.emit(user_message, technical)
