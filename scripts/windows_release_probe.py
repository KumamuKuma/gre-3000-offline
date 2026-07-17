from __future__ import annotations

import argparse
import ctypes
import os
import struct
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from ctypes import wintypes


IMAGE_FILE_MACHINE_AMD64 = 0x8664
IMAGE_SUBSYSTEM_WINDOWS_GUI = 2
ERROR_INVALID_HANDLE = 6
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
SYNCHRONIZE = 0x00100000
WAIT_OBJECT_0 = 0x00000000
WAIT_TIMEOUT = 0x00000102
WAIT_FAILED = 0xFFFFFFFF
WM_CLOSE = 0x0010
CREATE_SUSPENDED = 0x00000004
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
JOB_OBJECT_BASIC_ACCOUNTING_INFORMATION = 1
JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9

EXIT_HAS_CONSOLE = 10
EXIT_PROBE_ERROR = 11
EXIT_PROCESS_TIMEOUT = 12
EXIT_PROCESS_NONZERO = 13
EXIT_METADATA_MISMATCH = 14


class PeFormatError(ValueError):
    """Raised when a file does not contain readable PE metadata."""


class ProcessExitError(RuntimeError):
    """Raised when a process exits with a nonzero code."""


@dataclass(frozen=True, slots=True)
class PeMetadata:
    path: Path
    machine: int
    subsystem: int
    optional_header_magic: int


@dataclass(frozen=True, slots=True)
class ConsoleProbe:
    process_id: int
    has_console: bool
    winerror: int


@dataclass(frozen=True, slots=True)
class NativeSmokeResult:
    root_process_id: int
    gui_process_id: int
    gui_exit_code: int
    root_exit_code: int
    total_processes: int
    active_processes_after_close: int


@dataclass(frozen=True, slots=True)
class _OwnedWindow:
    window_handle: int
    process_id: int
    process_handle: int
    title: str


if sys.platform == "win32":
    class _STARTUPINFOW(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("lpReserved", wintypes.LPWSTR),
            ("lpDesktop", wintypes.LPWSTR),
            ("lpTitle", wintypes.LPWSTR),
            ("dwX", wintypes.DWORD),
            ("dwY", wintypes.DWORD),
            ("dwXSize", wintypes.DWORD),
            ("dwYSize", wintypes.DWORD),
            ("dwXCountChars", wintypes.DWORD),
            ("dwYCountChars", wintypes.DWORD),
            ("dwFillAttribute", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("wShowWindow", wintypes.WORD),
            ("cbReserved2", wintypes.WORD),
            ("lpReserved2", ctypes.POINTER(ctypes.c_ubyte)),
            ("hStdInput", wintypes.HANDLE),
            ("hStdOutput", wintypes.HANDLE),
            ("hStdError", wintypes.HANDLE),
        ]


    class _PROCESS_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("hProcess", wintypes.HANDLE),
            ("hThread", wintypes.HANDLE),
            ("dwProcessId", wintypes.DWORD),
            ("dwThreadId", wintypes.DWORD),
        ]


    class _JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_longlong),
            ("PerJobUserTimeLimit", ctypes.c_longlong),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]


    class _IO_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_ulonglong),
            ("WriteOperationCount", ctypes.c_ulonglong),
            ("OtherOperationCount", ctypes.c_ulonglong),
            ("ReadTransferCount", ctypes.c_ulonglong),
            ("WriteTransferCount", ctypes.c_ulonglong),
            ("OtherTransferCount", ctypes.c_ulonglong),
        ]


    class _JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", _JOBOBJECT_BASIC_LIMIT_INFORMATION),
            ("IoInfo", _IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]


    class _JOBOBJECT_BASIC_ACCOUNTING_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("TotalUserTime", ctypes.c_longlong),
            ("TotalKernelTime", ctypes.c_longlong),
            ("ThisPeriodTotalUserTime", ctypes.c_longlong),
            ("ThisPeriodTotalKernelTime", ctypes.c_longlong),
            ("TotalPageFaultCount", wintypes.DWORD),
            ("TotalProcesses", wintypes.DWORD),
            ("ActiveProcesses", wintypes.DWORD),
            ("TotalTerminatedProcesses", wintypes.DWORD),
        ]


    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _user32 = ctypes.WinDLL("user32", use_last_error=True)

    _kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    _kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    _kernel32.SetInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
    ]
    _kernel32.SetInformationJobObject.restype = wintypes.BOOL
    _kernel32.QueryInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    _kernel32.QueryInformationJobObject.restype = wintypes.BOOL
    _kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    _kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    _kernel32.IsProcessInJob.argtypes = [
        wintypes.HANDLE,
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.BOOL),
    ]
    _kernel32.IsProcessInJob.restype = wintypes.BOOL
    _kernel32.CreateProcessW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.LPWSTR,
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.BOOL,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.LPCWSTR,
        ctypes.POINTER(_STARTUPINFOW),
        ctypes.POINTER(_PROCESS_INFORMATION),
    ]
    _kernel32.CreateProcessW.restype = wintypes.BOOL
    _kernel32.ResumeThread.argtypes = [wintypes.HANDLE]
    _kernel32.ResumeThread.restype = wintypes.DWORD
    _kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    _kernel32.TerminateProcess.restype = wintypes.BOOL

    _kernel32.FreeConsole.argtypes = []
    _kernel32.FreeConsole.restype = wintypes.BOOL
    _kernel32.AttachConsole.argtypes = [wintypes.DWORD]
    _kernel32.AttachConsole.restype = wintypes.BOOL
    _kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    _kernel32.OpenProcess.restype = wintypes.HANDLE
    _kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    _kernel32.CloseHandle.restype = wintypes.BOOL
    _kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    _kernel32.WaitForSingleObject.restype = wintypes.DWORD
    _kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    _kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    _kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]
    _kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    _user32.PostMessageW.argtypes = [
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
    ]
    _user32.PostMessageW.restype = wintypes.BOOL
    _user32.IsWindow.argtypes = [wintypes.HWND]
    _user32.IsWindow.restype = wintypes.BOOL
    _user32.IsWindowVisible.argtypes = [wintypes.HWND]
    _user32.IsWindowVisible.restype = wintypes.BOOL
    _user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    _user32.GetWindowTextLengthW.restype = ctypes.c_int
    _user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    _user32.GetWindowTextW.restype = ctypes.c_int
    _user32.GetWindowThreadProcessId.argtypes = [
        wintypes.HWND,
        ctypes.POINTER(wintypes.DWORD),
    ]
    _user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    _user32.FindWindowExW.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
    ]
    _user32.FindWindowExW.restype = wintypes.HWND


def _require_windows() -> None:
    if sys.platform != "win32":
        raise RuntimeError("Windows release probes require Windows")


def _timeout_milliseconds(timeout_seconds: float) -> int:
    if timeout_seconds < 0:
        raise ValueError("Timeout must not be negative")
    return max(0, min(0xFFFFFFFE, round(float(timeout_seconds) * 1000)))


def wait_for_process_exit(process_handle: int, timeout_seconds: float) -> int:
    _require_windows()
    result = _kernel32.WaitForSingleObject(
        process_handle, _timeout_milliseconds(timeout_seconds)
    )
    if result == WAIT_TIMEOUT:
        raise TimeoutError(
            f"Process handle did not signal within {timeout_seconds:.3f} seconds"
        )
    if result == WAIT_FAILED:
        raise ctypes.WinError(ctypes.get_last_error())
    if result != WAIT_OBJECT_0:
        raise RuntimeError(f"Unexpected process wait result 0x{result:08x}")
    exit_code = wintypes.DWORD()
    if not _kernel32.GetExitCodeProcess(process_handle, ctypes.byref(exit_code)):
        raise ctypes.WinError(ctypes.get_last_error())
    return int(exit_code.value)


class JobSupervisor:
    """Own a process tree from suspended creation through final job drain."""

    def __init__(self, job_handle: int, root_process_handle: int, root_process_id: int):
        self._job_handle = job_handle
        self._root_process_handle = root_process_handle
        self._root_exit_code: int | None = None
        self.root_process_id = int(root_process_id)

    @classmethod
    def start(
        cls,
        command: Sequence[str | os.PathLike[str]],
        *,
        current_directory: Path | None = None,
    ) -> JobSupervisor:
        _require_windows()
        if not command:
            raise ValueError("A process command is required")
        executable = Path(command[0]).resolve(strict=True)
        arguments = [str(executable), *(str(value) for value in command[1:])]
        command_line = ctypes.create_unicode_buffer(subprocess.list2cmdline(arguments))
        working_directory = (
            str(Path(current_directory).resolve(strict=True))
            if current_directory is not None
            else None
        )

        job_handle = _kernel32.CreateJobObjectW(None, None)
        if not job_handle:
            raise ctypes.WinError(ctypes.get_last_error())
        process_info = _PROCESS_INFORMATION()
        try:
            limits = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
            limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if not _kernel32.SetInformationJobObject(
                job_handle,
                JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
                ctypes.byref(limits),
                ctypes.sizeof(limits),
            ):
                raise ctypes.WinError(ctypes.get_last_error())

            startup = _STARTUPINFOW()
            startup.cb = ctypes.sizeof(startup)
            if not _kernel32.CreateProcessW(
                str(executable),
                command_line,
                None,
                None,
                False,
                CREATE_SUSPENDED,
                None,
                working_directory,
                ctypes.byref(startup),
                ctypes.byref(process_info),
            ):
                raise ctypes.WinError(ctypes.get_last_error())

            if not _kernel32.AssignProcessToJobObject(job_handle, process_info.hProcess):
                error = ctypes.get_last_error()
                _kernel32.TerminateProcess(process_info.hProcess, EXIT_PROBE_ERROR)
                _kernel32.WaitForSingleObject(process_info.hProcess, 5000)
                raise ctypes.WinError(error)
            if _kernel32.ResumeThread(process_info.hThread) == 0xFFFFFFFF:
                error = ctypes.get_last_error()
                _kernel32.TerminateProcess(process_info.hProcess, EXIT_PROBE_ERROR)
                _kernel32.WaitForSingleObject(process_info.hProcess, 5000)
                raise ctypes.WinError(error)

            _kernel32.CloseHandle(process_info.hThread)
            process_info.hThread = None
            supervisor = cls(
                job_handle,
                process_info.hProcess,
                int(process_info.dwProcessId),
            )
            job_handle = None
            process_info.hProcess = None
            return supervisor
        finally:
            if process_info.hThread:
                _kernel32.CloseHandle(process_info.hThread)
            if process_info.hProcess:
                _kernel32.CloseHandle(process_info.hProcess)
            if job_handle:
                _kernel32.CloseHandle(job_handle)

    def __enter__(self) -> JobSupervisor:
        return self

    def __exit__(self, _exc_type, _exc, _traceback) -> None:
        self.close()

    def _require_open(self) -> int:
        if not self._job_handle:
            raise RuntimeError("Job supervisor is closed")
        return self._job_handle

    def _require_root_handle(self) -> int:
        self._require_open()
        if not self._root_process_handle:
            raise RuntimeError("Root process handle has already been released")
        return self._root_process_handle

    def accounting(self):
        job_handle = self._require_open()
        information = _JOBOBJECT_BASIC_ACCOUNTING_INFORMATION()
        returned_length = wintypes.DWORD()
        if not _kernel32.QueryInformationJobObject(
            job_handle,
            JOB_OBJECT_BASIC_ACCOUNTING_INFORMATION,
            ctypes.byref(information),
            ctypes.sizeof(information),
            ctypes.byref(returned_length),
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        return information

    def active_process_count(self) -> int:
        return int(self.accounting().ActiveProcesses)

    def open_process_handle(self, process_id: int) -> int:
        self._require_open()
        handle = _kernel32.OpenProcess(
            SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION,
            False,
            int(process_id),
        )
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        return handle

    @staticmethod
    def close_process_handle(process_handle: int) -> None:
        if process_handle:
            _kernel32.CloseHandle(process_handle)

    def contains_handle(self, process_handle: int) -> bool:
        job_handle = self._require_open()
        result = wintypes.BOOL()
        if not _kernel32.IsProcessInJob(
            process_handle, job_handle, ctypes.byref(result)
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        return bool(result.value)

    def contains_process(self, process_id: int) -> bool:
        handle = self.open_process_handle(process_id)
        try:
            return self.contains_handle(handle)
        finally:
            self.close_process_handle(handle)

    def root_has_exited(self) -> bool:
        if self._root_exit_code is not None:
            return True
        root_handle = self._require_root_handle()
        result = _kernel32.WaitForSingleObject(root_handle, 0)
        if result == WAIT_OBJECT_0:
            self.wait_for_root(0)
            return True
        if result == WAIT_TIMEOUT:
            return False
        if result == WAIT_FAILED:
            raise ctypes.WinError(ctypes.get_last_error())
        raise RuntimeError(f"Unexpected process wait result 0x{result:08x}")

    def wait_for_root(self, timeout_seconds: float) -> int:
        self._require_open()
        if self._root_exit_code is not None:
            return self._root_exit_code
        root_handle = self._require_root_handle()
        exit_code = wait_for_process_exit(root_handle, timeout_seconds)
        _kernel32.CloseHandle(root_handle)
        self._root_process_handle = None
        self._root_exit_code = exit_code
        return exit_code

    def wait_for_empty(self, timeout_seconds: float) -> int:
        deadline = time.monotonic() + float(timeout_seconds)
        root_exit_code = self.wait_for_root(max(0.0, deadline - time.monotonic()))
        while self.active_process_count() != 0:
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    "Job still has active descendant processes after the root exited"
                )
            time.sleep(0.025)
        return root_exit_code

    def close(self) -> None:
        job_handle, self._job_handle = self._job_handle, None
        root_handle, self._root_process_handle = self._root_process_handle, None
        if job_handle:
            _kernel32.CloseHandle(job_handle)
        if root_handle:
            _kernel32.CloseHandle(root_handle)


def publish_release_candidate(candidate: Path, output: Path) -> None:
    source = Path(candidate).resolve(strict=True)
    destination = Path(output).resolve(strict=False)
    if source == destination:
        raise ValueError("Release candidate and output must be different paths")
    if source.drive.casefold() != destination.drive.casefold():
        raise ValueError("Atomic release publication requires a single filesystem volume")
    if not destination.parent.is_dir():
        raise FileNotFoundError(f"Release output directory not found: {destination.parent}")
    os.replace(source, destination)


def read_pe_metadata(path: Path) -> PeMetadata:
    resolved = path.resolve(strict=True)
    with resolved.open("rb") as executable:
        dos_header = executable.read(64)
        if len(dos_header) != 64 or dos_header[:2] != b"MZ":
            raise PeFormatError(f"Missing DOS MZ header: {resolved}")
        pe_offset = struct.unpack_from("<I", dos_header, 0x3C)[0]
        executable.seek(pe_offset)
        if executable.read(4) != b"PE\0\0":
            raise PeFormatError(f"Missing PE signature: {resolved}")

        coff_header = executable.read(20)
        if len(coff_header) != 20:
            raise PeFormatError(f"Truncated COFF header: {resolved}")
        machine = struct.unpack_from("<H", coff_header, 0)[0]
        optional_header_size = struct.unpack_from("<H", coff_header, 16)[0]
        optional_header = executable.read(optional_header_size)
        if len(optional_header) != optional_header_size or optional_header_size < 70:
            raise PeFormatError(f"Truncated PE optional header: {resolved}")
        optional_header_magic = struct.unpack_from("<H", optional_header, 0)[0]
        if optional_header_magic not in (0x10B, 0x20B):
            raise PeFormatError(
                f"Unsupported PE optional-header magic 0x{optional_header_magic:04x}: {resolved}"
            )
        subsystem = struct.unpack_from("<H", optional_header, 68)[0]

    return PeMetadata(resolved, machine, subsystem, optional_header_magic)


def process_image_path_from_handle(process_handle: int) -> Path:
    _require_windows()
    capacity = wintypes.DWORD(32768)
    buffer = ctypes.create_unicode_buffer(capacity.value)
    if not _kernel32.QueryFullProcessImageNameW(
        process_handle, 0, buffer, ctypes.byref(capacity)
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    return Path(buffer.value)


def probe_console_attachment(process_id: int) -> ConsoleProbe:
    _require_windows()
    # This function must run in a disposable helper process. Detaching here
    # prevents ERROR_ACCESS_DENIED merely because the helper inherited a console.
    ctypes.set_last_error(0)
    _kernel32.FreeConsole()
    ctypes.set_last_error(0)
    if _kernel32.AttachConsole(int(process_id)):
        if not _kernel32.FreeConsole():
            raise ctypes.WinError(ctypes.get_last_error())
        return ConsoleProbe(int(process_id), True, 0)

    error = ctypes.get_last_error()
    if error == ERROR_INVALID_HANDLE:
        return ConsoleProbe(int(process_id), False, error)
    raise ctypes.WinError(error)


def probe_console_in_disposable_helper(process_id: int) -> ConsoleProbe:
    """Probe without detaching the long-lived caller from its own console."""

    _require_windows()
    completed = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "_console-worker",
            "--pid",
            str(int(process_id)),
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=10,
    )
    if completed.returncode not in (0, EXIT_HAS_CONSOLE):
        details = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(
            f"Disposable console worker failed with code {completed.returncode}: {details}"
        )
    line = next(
        (
            value
            for value in reversed(completed.stdout.splitlines())
            if value.startswith("console_probe ")
        ),
        None,
    )
    if line is None:
        raise RuntimeError("Disposable console worker returned no structured result")
    fields = dict(part.split("=", 1) for part in line.split()[1:])
    result = ConsoleProbe(
        int(fields["pid"]),
        fields["has_console"] == "true",
        int(fields["winerror"]),
    )
    if result.process_id != int(process_id):
        raise RuntimeError("Disposable console worker reported a different process")
    expected_code = EXIT_HAS_CONSOLE if result.has_console else 0
    if completed.returncode != expected_code:
        raise RuntimeError("Disposable console worker result disagrees with its exit code")
    return result


def _print_console_probe(result: ConsoleProbe) -> None:
    print(
        f"console_probe pid={result.process_id} "
        f"has_console={str(result.has_console).lower()} "
        f"winerror={result.winerror}"
    )


def _process_is_active(process_handle: int) -> bool:
    result = _kernel32.WaitForSingleObject(process_handle, 0)
    if result == WAIT_TIMEOUT:
        return True
    if result == WAIT_OBJECT_0:
        return False
    if result == WAIT_FAILED:
        raise ctypes.WinError(ctypes.get_last_error())
    raise RuntimeError(f"Unexpected process wait result 0x{result:08x}")


def _find_visible_titled_job_window(
    job: JobSupervisor, expected_title: str
) -> _OwnedWindow | None:
    _require_windows()
    observed: list[tuple[int, int, str]] = []
    previous = None
    while True:
        window_handle = _user32.FindWindowExW(
            None, previous, None, expected_title
        )
        if not window_handle:
            break
        previous = window_handle
        if not _user32.IsWindowVisible(window_handle):
            continue
        process_id = wintypes.DWORD()
        _user32.GetWindowThreadProcessId(window_handle, ctypes.byref(process_id))
        observed.append((int(window_handle), int(process_id.value), expected_title))

    owned: list[_OwnedWindow] = []
    for window_handle, process_id, title in observed:
        try:
            process_handle = job.open_process_handle(process_id)
        except OSError:
            continue
        try:
            if _process_is_active(process_handle) and job.contains_handle(process_handle):
                owned.append(
                    _OwnedWindow(window_handle, process_id, process_handle, title)
                )
                process_handle = None
        finally:
            if process_handle:
                job.close_process_handle(process_handle)

    if len(owned) > 1:
        for window in owned:
            job.close_process_handle(window.process_handle)
        raise RuntimeError(
            f"More than one visible job window has the exact title {expected_title!r}"
        )
    return owned[0] if owned else None


def _request_owned_window_close(job: JobSupervisor, window: _OwnedWindow) -> None:
    if not _user32.IsWindow(window.window_handle):
        raise RuntimeError("The verified window no longer exists before WM_CLOSE")
    current_process_id = wintypes.DWORD()
    _user32.GetWindowThreadProcessId(
        window.window_handle, ctypes.byref(current_process_id)
    )
    if int(current_process_id.value) != window.process_id:
        raise RuntimeError("The verified HWND was reused by another process")
    if not _process_is_active(window.process_handle):
        raise RuntimeError("The verified window owner exited before WM_CLOSE")
    if not job.contains_handle(window.process_handle):
        raise RuntimeError("The verified window owner is no longer in the supervised job")
    length = _user32.GetWindowTextLengthW(window.window_handle)
    buffer = ctypes.create_unicode_buffer(max(1, length + 1))
    _user32.GetWindowTextW(window.window_handle, buffer, len(buffer))
    if buffer.value != window.title:
        raise RuntimeError("The verified window title changed before WM_CLOSE")
    if not _user32.PostMessageW(window.window_handle, WM_CLOSE, 0, 0):
        raise ctypes.WinError(ctypes.get_last_error())


def run_native_smoke(
    executable: Path,
    *,
    expected_title: str,
    timeout_seconds: float,
    arguments: Sequence[str] = (),
    expected_machine: int = IMAGE_FILE_MACHINE_AMD64,
    expected_subsystem: int = IMAGE_SUBSYSTEM_WINDOWS_GUI,
) -> NativeSmokeResult:
    _require_windows()
    if not expected_title:
        raise ValueError("Expected window title must not be empty")
    if timeout_seconds <= 0:
        raise ValueError("Timeout must be positive")
    metadata = read_pe_metadata(Path(executable))
    if metadata.machine != expected_machine or metadata.subsystem != expected_subsystem:
        raise PeFormatError(
            "Root executable PE metadata does not match the required architecture/subsystem"
        )

    deadline = time.monotonic() + float(timeout_seconds)
    window: _OwnedWindow | None = None
    with JobSupervisor.start([metadata.path, *arguments]) as job:
        try:
            while time.monotonic() < deadline:
                if job.root_has_exited():
                    raise ProcessExitError(
                        "Root process exited before the exact titled window appeared "
                        f"with code {job.wait_for_root(0)}"
                    )
                window = _find_visible_titled_job_window(job, expected_title)
                if window is not None:
                    break
                time.sleep(0.05)
            if window is None:
                raise TimeoutError(
                    f"Exact main window {expected_title!r} did not appear in the supervised job"
                )

            gui_metadata = read_pe_metadata(
                process_image_path_from_handle(window.process_handle)
            )
            if (
                gui_metadata.machine != expected_machine
                or gui_metadata.subsystem != expected_subsystem
            ):
                raise PeFormatError(
                    "Exact titled GUI owner PE metadata does not match the release target"
                )

            root_console = probe_console_in_disposable_helper(job.root_process_id)
            if root_console.has_console:
                raise RuntimeError("Root release process owns a console")
            if window.process_id != job.root_process_id:
                gui_console = probe_console_in_disposable_helper(window.process_id)
                if gui_console.has_console:
                    raise RuntimeError("Exact titled GUI process owns a console")

            _request_owned_window_close(job, window)
            gui_exit_code = wait_for_process_exit(
                window.process_handle,
                max(0.0, deadline - time.monotonic()),
            )
            if gui_exit_code != 0:
                raise ProcessExitError(
                    f"GUI process {window.process_id} exited with code {gui_exit_code}"
                )
            root_exit_code = job.wait_for_empty(
                max(0.0, deadline - time.monotonic())
            )
            if root_exit_code != 0:
                raise ProcessExitError(
                    f"Root process {job.root_process_id} exited with code {root_exit_code}"
                )
            accounting = job.accounting()
            active_processes = int(accounting.ActiveProcesses)
            if active_processes != 0:
                raise RuntimeError(
                    f"Supervised job still has {active_processes} active processes"
                )
            return NativeSmokeResult(
                root_process_id=job.root_process_id,
                gui_process_id=window.process_id,
                gui_exit_code=gui_exit_code,
                root_exit_code=root_exit_code,
                total_processes=int(accounting.TotalProcesses),
                active_processes_after_close=active_processes,
            )
        finally:
            if window is not None:
                job.close_process_handle(window.process_handle)


def _parse_integer(value: str) -> int:
    return int(value, 0)


def _verify_metadata(
    metadata: PeMetadata, expected_machine: int, expected_subsystem: int
) -> bool:
    print(
        "pe_metadata "
        f"path='{metadata.path}' machine=0x{metadata.machine:04x} "
        f"subsystem={metadata.subsystem}"
    )
    return (
        metadata.machine == expected_machine
        and metadata.subsystem == expected_subsystem
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Independent Win32 probes for packaged release verification."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    pe = commands.add_parser("pe", help="Verify PE metadata for a file")
    pe.add_argument("--path", required=True, type=Path)
    pe.add_argument("--expected-machine", required=True, type=_parse_integer)
    pe.add_argument("--expected-subsystem", required=True, type=_parse_integer)

    console = commands.add_parser(
        "console", help="Fail when the target process has a console"
    )
    console.add_argument("--pid", required=True, type=int)

    console_worker = commands.add_parser("_console-worker", help=argparse.SUPPRESS)
    console_worker.add_argument("--pid", required=True, type=int)

    native_smoke = commands.add_parser(
        "native-smoke",
        help="Launch the release suspended in a Job Object and verify normal shutdown",
    )
    native_smoke.add_argument("--path", required=True, type=Path)
    native_smoke.add_argument("--title", required=True)
    native_smoke.add_argument("--timeout", required=True, type=float)
    native_smoke.add_argument(
        "--expected-machine", default=IMAGE_FILE_MACHINE_AMD64, type=_parse_integer
    )
    native_smoke.add_argument(
        "--expected-subsystem",
        default=IMAGE_SUBSYSTEM_WINDOWS_GUI,
        type=_parse_integer,
    )

    publish = commands.add_parser(
        "publish", help="Atomically replace a release with a verified candidate"
    )
    publish.add_argument("--candidate", required=True, type=Path)
    publish.add_argument("--output", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _build_parser().parse_args(argv)
    try:
        if arguments.command == "pe":
            metadata = read_pe_metadata(arguments.path)
            return (
                0
                if _verify_metadata(
                    metadata,
                    arguments.expected_machine,
                    arguments.expected_subsystem,
                )
                else EXIT_METADATA_MISMATCH
            )
        if arguments.command in ("console", "_console-worker"):
            result = (
                probe_console_in_disposable_helper(arguments.pid)
                if arguments.command == "console"
                else probe_console_attachment(arguments.pid)
            )
            _print_console_probe(result)
            return EXIT_HAS_CONSOLE if result.has_console else 0
        if arguments.command == "native-smoke":
            result = run_native_smoke(
                arguments.path,
                expected_title=arguments.title,
                timeout_seconds=arguments.timeout,
                expected_machine=arguments.expected_machine,
                expected_subsystem=arguments.expected_subsystem,
            )
            print(
                f"native_smoke title={arguments.title!r} "
                f"root_pid={result.root_process_id} gui_pid={result.gui_process_id} "
                f"job_total_processes={result.total_processes} "
                f"job_active_processes={result.active_processes_after_close} "
                f"machine=0x{arguments.expected_machine:04x} "
                f"subsystem={arguments.expected_subsystem} no_console=true "
                f"wm_close=true gui_exit={result.gui_exit_code} "
                f"root_exit={result.root_exit_code}"
            )
            return 0
        if arguments.command == "publish":
            publish_release_candidate(arguments.candidate, arguments.output)
            print(
                f"release_published candidate={str(arguments.candidate)!r} "
                f"output={str(arguments.output)!r} atomic_replace=true"
            )
            return 0
        raise AssertionError(f"Unhandled command: {arguments.command}")
    except TimeoutError as error:
        print(f"process_timeout {error}", file=sys.stderr)
        return EXIT_PROCESS_TIMEOUT
    except ProcessExitError as error:
        print(f"process_nonzero {error}", file=sys.stderr)
        return EXIT_PROCESS_NONZERO
    except (OSError, PeFormatError, RuntimeError, ValueError) as error:
        print(f"probe_error {type(error).__name__}: {error}", file=sys.stderr)
        return EXIT_PROBE_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
