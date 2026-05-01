"""HID2UART 应用程序入口。"""

from __future__ import annotations

import logging
import os
import sys

os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")
os.environ.setdefault("SDL_JOYSTICK_DISABLE_XINPUT", "0")
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

from PyQt5.QtWidgets import QApplication

from ui.main_window import MainWindow
from utils.logging_config import setup_logging


def main() -> None:
    """应用程序主入口。"""
    setup_logging()
    logger = logging.getLogger(__name__)

    try:
        app: QApplication = QApplication(sys.argv)
        app.setStyle("Fusion")

        w: MainWindow = MainWindow()
        w.show()

        sys.exit(app.exec())
    except KeyboardInterrupt:
        logger.info("用户中断退出")
    except Exception:
        logger.critical("应用程序异常退出", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
