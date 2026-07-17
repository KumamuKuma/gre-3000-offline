from __future__ import annotations

import argparse
import ctypes
import struct
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Sequence

from ctypes import wintypes


IMAGE_FILE_MACHINE_AMD64 = 0x8664
IMAGE_SUBSYSTEM_WINDOWS_GUI = 2
ERROR_INVALID_HANDLE = 6
ERROR_NO_MORE_FILES = 18
TH32CS_SNAPPROCESS = 0x00000002
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
SYNCHRONIZE = 0x00100000
WAIT_OBJECT_0 = 0x00000000
WAIT_TIMEOUT = 0x00000102
WAIT_FAILED = 0xFFFFFFFF
WM_CLOSE = 0x0010

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


if sys.platform == "win32":
    class _PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        ]


    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _user32 = ctypes.WinDLL("user32", use_last_error=True)

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
    _kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    _kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    _kernel32.Process32FirstW.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(_PROCESSENTRY32W),
    ]
    _kernel32.Process32FirstW.restype = wintypes.BOOL
    _kernel32.Process32NextW.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(_PROCESSENTRY32W),
    ]
    _kernel32.Process32NextW.restype = wintypes.BOOL

    _user32.PostMessageW.argtypes = [
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
    ]
    _user32.PostMessageW.restype = wintypes.BOOL


def _require_windows() -> None:
    if sys.platform != "win32":
        raise RuntimeError("Windows release probes require Windows")


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


def process_image_path(process_id: int) -> Path:
    _require_windows()
    handle = _kernel32.OpenProcess(
        PROCESS_QUERY_LIMITED_INFORMATION, False, int(process_id)
    )
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        capacity = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(capacity.value)
        if not _kernel32.QueryFullProcessImageNameW(
            handle, 0, buffer, ctypes.byref(capacity)
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        return Path(buffer.value)
    finally:
        _kernel32.CloseHandle(handle)


def process_tree_ids(root_process_id: int) -> tuple[int, ...]:
    """Return a stable snapshot of a process and all of its descendants."""

    _require_windows()
    root_process_id = int(root_process_id)
    if root_process_id <= 0:
        raise ValueError("Root process ID must be positive")

    invalid_handle_value = ctypes.c_void_p(-1).value
    snapshot = _kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == invalid_handle_value:
        raise ctypes.WinError(ctypes.get_last_error())

    records: list[tuple[int, int]] = []
    try:
        entry = _PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        if not _kernel32.Process32FirstW(snapshot, ctypes.byref(entry)):
            error = ctypes.get_last_error()
            if error != ERROR_NO_MORE_FILES:
                raise ctypes.WinError(error)
        else:
            while True:
                records.append(
                    (int(entry.th32ProcessID), int(entry.th32ParentProcessID))
                )
                entry.dwSize = ctypes.sizeof(entry)
                if not _kernel32.Process32NextW(snapshot, ctypes.byref(entry)):
                    error = ctypes.get_last_error()
                    if error != ERROR_NO_MORE_FILES:
                        raise ctypes.WinError(error)
                    break
    finally:
        _kernel32.CloseHandle(snapshot)

    known = {root_process_id}
    while True:
        descendants = {
            process_id
            for process_id, parent_process_id in records
            if parent_process_id in known
        }
        expanded = known | descendants
        if expanded == known:
            return tuple(sorted(known))
        known = expanded


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


@contextmanager
def _open_process_handles(process_ids: Sequence[int]) -> Iterator[list[tuple[int, int]]]:
    _require_windows()
    handles: list[tuple[int, int]] = []
    try:
        for process_id in dict.fromkeys(int(value) for value in process_ids):
            handle = _kernel32.OpenProcess(
                SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION,
                False,
                process_id,
            )
            if not handle:
                raise ctypes.WinError(ctypes.get_last_error())
            handles.append((process_id, handle))
        yield handles
    finally:
        for _process_id, handle in handles:
            _kernel32.CloseHandle(handle)


def _wait_for_open_handles(
    handles: Sequence[tuple[int, int]], timeout_seconds: float
) -> dict[int, int]:
    deadline = time.monotonic() + float(timeout_seconds)
    exit_codes: dict[int, int] = {}
    for process_id, handle in handles:
        remaining = deadline - time.monotonic()
        timeout_ms = max(0, min(0xFFFFFFFE, round(remaining * 1000)))
        result = _kernel32.WaitForSingleObject(handle, timeout_ms)
        if result == WAIT_TIMEOUT:
            raise TimeoutError(
                f"Process {process_id} did not exit within {timeout_seconds:.3f} seconds"
            )
        if result == WAIT_FAILED:
            raise ctypes.WinError(ctypes.get_last_error())
        if result != WAIT_OBJECT_0:
            raise RuntimeError(
                f"Unexpected wait result 0x{result:08x} for process {process_id}"
            )

        exit_code = wintypes.DWORD()
        if not _kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            raise ctypes.WinError(ctypes.get_last_error())
        exit_codes[process_id] = int(exit_code.value)

    for process_id, exit_code in exit_codes.items():
        if exit_code != 0:
            raise ProcessExitError(f"Process {process_id} exited with code {exit_code}")
    return exit_codes


def wait_for_clean_process_exit(
    process_ids: Sequence[int], timeout_seconds: float
) -> dict[int, int]:
    with _open_process_handles(process_ids) as handles:
        return _wait_for_open_handles(handles, timeout_seconds)


def close_window_and_wait(
    window_handle: int, process_ids: Sequence[int], timeout_seconds: float
) -> dict[int, int]:
    _require_windows()
    # Open both process handles before WM_CLOSE so rapid clean exits cannot race
    # the verification or hide their exit codes.
    with _open_process_handles(process_ids) as handles:
        if not _user32.PostMessageW(int(window_handle), WM_CLOSE, 0, 0):
            raise ctypes.WinError(ctypes.get_last_error())
        return _wait_for_open_handles(handles, timeout_seconds)


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

    process_pe = commands.add_parser(
        "process-pe", help="Verify PE metadata for a running process image"
    )
    process_pe.add_argument("--pid", required=True, type=int)
    process_pe.add_argument("--expected-machine", required=True, type=_parse_integer)
    process_pe.add_argument("--expected-subsystem", required=True, type=_parse_integer)

    process_tree = commands.add_parser(
        "process-tree", help="List a process and all descendants from Toolhelp"
    )
    process_tree.add_argument("--pid", required=True, type=int)

    console = commands.add_parser(
        "console", help="Fail when the target process has a console"
    )
    console.add_argument("--pid", required=True, type=int)

    close_wait = commands.add_parser(
        "close-wait", help="Post WM_CLOSE and require every process to exit zero"
    )
    close_wait.add_argument("--window-handle", required=True, type=_parse_integer)
    close_wait.add_argument("--pid", required=True, type=int, action="append")
    close_wait.add_argument("--timeout", required=True, type=float)
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
        if arguments.command == "process-pe":
            metadata = read_pe_metadata(process_image_path(arguments.pid))
            return (
                0
                if _verify_metadata(
                    metadata,
                    arguments.expected_machine,
                    arguments.expected_subsystem,
                )
                else EXIT_METADATA_MISMATCH
            )
        if arguments.command == "process-tree":
            process_ids = process_tree_ids(arguments.pid)
            print(
                f"process_tree root={arguments.pid} "
                f"pids={','.join(str(value) for value in process_ids)}"
            )
            return 0
        if arguments.command == "console":
            result = probe_console_attachment(arguments.pid)
            print(
                f"console_probe pid={result.process_id} "
                f"has_console={str(result.has_console).lower()} "
                f"winerror={result.winerror}"
            )
            return EXIT_HAS_CONSOLE if result.has_console else 0
        if arguments.command == "close-wait":
            exit_codes = close_window_and_wait(
                arguments.window_handle,
                arguments.pid,
                arguments.timeout,
            )
            details = ",".join(
                f"{process_id}:{exit_code}"
                for process_id, exit_code in exit_codes.items()
            )
            print(
                f"normal_exit wm_close=true processes={details} "
                "all_exited=true"
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
