from __future__ import annotations

import ctypes
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path


RUNTIME_NAME = "GRE3000OfflineRuntime.exe"
APP_TITLE = "GRE 3000 词离线版"
MB_OK = 0x00000000
MB_ICONERROR = 0x00000010


def embedded_runtime_path(launcher_file: Path | None = None) -> Path:
    module_file = Path(__file__) if launcher_file is None else Path(launcher_file)
    return module_file.resolve().parent / "runtime" / RUNTIME_NAME


def launch_runtime(
    runtime: Path, arguments: Sequence[str] = ()
) -> int:
    executable = Path(runtime)
    if not executable.is_file():
        raise FileNotFoundError(f"Embedded runtime not found: {executable}")
    completed = subprocess.run(
        [str(executable), *arguments],
        cwd=Path(sys.executable).resolve().parent,
        check=False,
    )
    return int(completed.returncode)


def show_error(message: str) -> None:
    if sys.platform != "win32":
        return
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.MessageBoxW.argtypes = [
        ctypes.c_void_p,
        ctypes.c_wchar_p,
        ctypes.c_wchar_p,
        ctypes.c_uint,
    ]
    user32.MessageBoxW.restype = ctypes.c_int
    user32.MessageBoxW(None, message, APP_TITLE, MB_OK | MB_ICONERROR)


def main() -> int:
    try:
        exit_code = launch_runtime(embedded_runtime_path())
    except OSError as error:
        show_error(f"应用无法启动。\n\n{error}")
        return 1
    if exit_code != 0:
        show_error(f"应用异常退出，错误码：{exit_code}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
