from __future__ import annotations

import sys
from collections.abc import Sequence

from PySide6.QtWidgets import QApplication

from gre_vocab_app.bootstrap import bootstrap
from gre_vocab_app.paths import AppPaths
from gre_vocab_app.ui.theme import apply_theme


def main(argv: Sequence[str] | None = None) -> int:
    application = QApplication(list(argv) if argv is not None else sys.argv)
    application.setOrganizationName("GRE Vocab Offline")
    application.setApplicationName("GRE 3000 词离线版")
    apply_theme(application)

    result = bootstrap(AppPaths.resolve())
    application.aboutToQuit.connect(result.controller.content.close)
    application.aboutToQuit.connect(result.controller.user.close)
    if result.recovery_notice:
        result.window.statusBar().showMessage(result.recovery_notice)
    result.window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
