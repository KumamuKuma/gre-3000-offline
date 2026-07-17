from __future__ import annotations

import logging
import sys
from collections.abc import Sequence

from PySide6.QtWidgets import QApplication, QMessageBox

from gre_vocab_app.bootstrap import bootstrap
from gre_vocab_app.paths import AppPaths
from gre_vocab_app.ui.theme import apply_theme


LOGGER = logging.getLogger(__name__)


def main(argv: Sequence[str] | None = None) -> int:
    application = QApplication.instance()
    owns_event_loop = application is None
    if application is None:
        application = QApplication(list(argv) if argv is not None else sys.argv)
    application.setOrganizationName("GRE Vocab Offline")
    application.setApplicationName("GRE 3000 词离线版")
    apply_theme(application)

    try:
        result = bootstrap(AppPaths.resolve())
    except Exception as error:
        LOGGER.exception("Application bootstrap failed: %s", error)
        QMessageBox.critical(
            None,
            "应用启动失败",
            "无法启动 GRE 词汇应用。请检查词库和本地数据文件；"
            "技术详情已写入应用日志。",
        )
        return 1
    application.aboutToQuit.connect(result.controller.content.close)
    application.aboutToQuit.connect(result.controller.user.close)
    if result.recovery_notice:
        result.window.statusBar().showMessage(result.recovery_notice)
    result.window.show()
    return application.exec() if owns_event_loop else 0


if __name__ == "__main__":
    raise SystemExit(main())
