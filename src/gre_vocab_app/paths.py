import os
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QStandardPaths


PACKAGE_ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True, slots=True)
class AppPaths:
    content_db: Path
    user_db: Path
    log_file: Path

    @classmethod
    def resolve(
        cls,
        content_override: Path | None = None,
        user_root: Path | None = None,
    ) -> "AppPaths":
        content_env = os.environ.get("GRE_WORDS_DB")
        user_env = os.environ.get("GRE_APP_DATA_ROOT")
        content = content_override or (
            Path(content_env) if content_env else PACKAGE_ROOT / "data" / "words.db"
        )
        root = user_root or (
            Path(user_env)
            if user_env
            else Path(QStandardPaths.writableLocation(QStandardPaths.AppDataLocation))
        )
        return cls(content, root / "user.db", root / "logs" / "app.log")
