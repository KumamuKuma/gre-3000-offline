from __future__ import annotations

import logging
import random
import sqlite3
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from pathlib import Path

from gre_vocab_app.controller import ApplicationController
from gre_vocab_app.db.content import ContentRepository
from gre_vocab_app.db.schema import CONTENT_SCHEMA_VERSION
from gre_vocab_app.db.user import UserRepository
from gre_vocab_app.paths import AppPaths
from gre_vocab_app.services.search import SearchService
from gre_vocab_app.services.speech import SpeechService
from gre_vocab_app.services.study import StudySession
from gre_vocab_app.ui.main_window import MainWindow


LOGGER = logging.getLogger(__name__)
_HANDLER_MARKER = "_gre_vocab_app_rotating_handler"


class ContentDatabaseError(RuntimeError):
    """Raised when the immutable vocabulary database cannot be trusted."""


@dataclass(frozen=True, slots=True)
class BootstrapResult:
    controller: ApplicationController
    window: MainWindow
    recovery_notice: str | None = None


def _configure_logging(log_file: Path) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    root_logger = logging.getLogger()
    for handler in tuple(root_logger.handlers):
        if getattr(handler, _HANDLER_MARKER, False):
            root_logger.removeHandler(handler)
            handler.close()

    handler = RotatingFileHandler(
        log_file,
        maxBytes=1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    setattr(handler, _HANDLER_MARKER, True)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root_logger.addHandler(handler)
    if root_logger.level == logging.NOTSET or root_logger.level > logging.INFO:
        root_logger.setLevel(logging.INFO)


def _validate_content_database(path: Path) -> None:
    if not path.is_file():
        raise ContentDatabaseError(f"词库文件缺失：{path}")

    resolved = path.resolve()
    try:
        database = sqlite3.connect(f"{resolved.as_uri()}?mode=ro", uri=True)
    except sqlite3.Error as error:
        raise ContentDatabaseError(f"词库完整性检查失败：{error}") from error

    try:
        try:
            integrity_rows = database.execute("pragma integrity_check").fetchall()
        except sqlite3.Error as error:
            raise ContentDatabaseError(f"词库完整性检查失败：{error}") from error
        if integrity_rows != [("ok",)]:
            details = "; ".join(str(row[0]) for row in integrity_rows) or "无检查结果"
            raise ContentDatabaseError(f"词库完整性检查失败：{details}")

        try:
            row = database.execute(
                "select value from metadata where key='schema_version'"
            ).fetchone()
            version = int(row[0]) if row is not None else None
        except (sqlite3.Error, TypeError, ValueError) as error:
            raise ContentDatabaseError(f"词库版本不兼容：{error}") from error
        if version != CONTENT_SCHEMA_VERSION:
            raise ContentDatabaseError(
                f"词库版本不兼容：需要 {CONTENT_SCHEMA_VERSION}，实际 {version}"
            )
    finally:
        database.close()


def bootstrap(paths: AppPaths) -> BootstrapResult:
    _configure_logging(paths.log_file)
    _validate_content_database(paths.content_db)

    content: ContentRepository | None = None
    user: UserRepository | None = None
    try:
        content = ContentRepository(paths.content_db)
        user_open = UserRepository.open_recovering(paths.user_db)
        user = user_open.repository
        window = MainWindow()
        study = StudySession(content, user, random.Random())
        speech = SpeechService()
        controller = ApplicationController(
            window=window,
            content_repository=content,
            user_repository=user,
            study_session=study,
            search_service=SearchService(content),
            speech_service=speech,
        )
        controller.start()
    except Exception:
        if user is not None:
            user.close()
        if content is not None:
            content.close()
        raise

    recovery_notice = None
    if user_open.recovered_from is not None:
        recovery_notice = (
            "检测到损坏的用户数据库，已创建备份："
            f"{user_open.recovered_from.name}"
        )
        LOGGER.warning(
            "Recovered corrupt user database to %s", user_open.recovered_from
        )
    LOGGER.info(
        "Application bootstrap completed with content database %s",
        paths.content_db,
    )
    return BootstrapResult(controller, window, recovery_notice)
