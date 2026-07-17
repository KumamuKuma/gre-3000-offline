from __future__ import annotations

import logging
import sys
from collections.abc import Sequence

from PySide6.QtWidgets import QApplication, QMessageBox

from gre_vocab_app.bootstrap import bootstrap
from gre_vocab_app.paths import AppPaths
from gre_vocab_app.ui.theme import apply_theme


LOGGER = logging.getLogger(__name__)
STARTUP_ERROR_REPORTED_EXIT_CODE = 20


def main(argv: Sequence[str] | None = None) -> int:
    application = QApplication.instance()
    owns_event_loop = application is None
    if application is None:
        application = QApplication(list(argv) if argv is not None else sys.argv)
    application.setOrganizationName("GRE Vocab Offline")
    application.setApplicationName("GRE 3000 词离线版")
    apply_theme(application)

    paths: AppPaths | None = None
    try:
        paths = AppPaths.resolve()
        result = bootstrap(paths)
    except Exception as error:
        LOGGER.exception("Application bootstrap failed: %s", error)
        technical = f"{type(error).__name__}: {error}"
        log_target = str(paths.log_file) if paths is not None else "无法确定"
        QMessageBox.critical(
            None,
            "应用启动失败",
            "无法启动 GRE 词汇应用。请检查词库和本地数据文件。\n\n"
            f"技术信息：{technical}\n"
            f"日志位置（若可写）：{log_target}",
        )
        return STARTUP_ERROR_REPORTED_EXIT_CODE
    application.aboutToQuit.connect(result.controller.shutdown)
    if result.recovery_notice:
        result.window.statusBar().showMessage(result.recovery_notice)
    result.window.show()
    return application.exec() if owns_event_loop else 0


if __name__ == "__main__":
    raise SystemExit(main())
