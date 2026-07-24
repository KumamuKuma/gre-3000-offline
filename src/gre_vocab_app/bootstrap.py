from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from pathlib import Path

from gre_vocab_app.controller import ApplicationController
from gre_vocab_app.db.content import ContentDatabaseError, ContentRepository
from gre_vocab_app.db.user import UserRepository
from gre_vocab_app.paths import AppPaths
from gre_vocab_app.services.search import SearchService
from gre_vocab_app.services.speech import SpeechService
from gre_vocab_app.services.study import StudySession
from gre_vocab_app.services.dictionary import DictionaryService
from gre_vocab_app.services.translation import TranslationService
from gre_vocab_app.ui.main_window import MainWindow


LOGGER = logging.getLogger(__name__)
_HANDLER_MARKER = "_gre_vocab_app_rotating_handler"


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


def bootstrap(paths: AppPaths) -> BootstrapResult:
    _configure_logging(paths.log_file)

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
            dictionary_service=DictionaryService(),
            translation_service=TranslationService(),
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
