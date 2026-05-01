"""HID2UART 应用程序入口。"""

from __future__ import annotations

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

    app: QApplication = QApplication(sys.argv)
    app.setStyle("Fusion")

    w: MainWindow = MainWindow()
    w.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
