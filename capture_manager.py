"""输入捕获管理器模块。

统一管理所有 HID 输入捕获器的生命周期，
将 MainWindow 从具体 CaptureBackend 实现中解耦。
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from core import CaptureBackend, FrameCallback

if TYPE_CHECKING:
    from input.keyboard_capture import KeyboardCapture
    from input.mouse_capture import MouseCapture
    from input.gamepad_capture import GamepadCapture

__all__ = ["CaptureManager"]

logger: logging.Logger = logging.getLogger(__name__)


class CaptureManager:
    """
    HID 输入捕获器管理器。

    统一管理 KeyboardCapture、MouseCapture、GamepadCapture 的启动和停止，
    提供统一的启动/停止接口，无需 MainWindow 了解具体捕获器实现。
    """

    def __init__(self, on_frame: FrameCallback) -> None:
        """
        参数：
            on_frame: 帧就绪时的回调
        """
        self._on_frame = on_frame
        self._kb: KeyboardCapture | None = None
        self._mouse: MouseCapture | None = None
        self._gamepad: GamepadCapture | None = None

    def start(self, types: set[str]) -> None:
        """
        启动指定类型的输入捕获器。

        参数：
            types: 要启动的捕获器类型集合，包含 "kb"、"mouse"、"gamepad"
        """
        if "kb" in types:
            from input.keyboard_capture import KeyboardCapture

            self._kb = KeyboardCapture(self._on_frame)
            self._kb.start()
            logger.info("键盘捕获已启动")

        if "mouse" in types:
            from input.mouse_capture import MouseCapture

            self._mouse = MouseCapture(self._on_frame)
            self._mouse.start()
            logger.info("鼠标捕获已启动")

        if "gamepad" in types:
            from input.gamepad_capture import GamepadCapture

            self._gamepad = GamepadCapture(self._on_frame)
            self._gamepad.start()
            logger.info("手柄捕获已启动")

    def stop(self) -> None:
        """停止所有正在运行的输入捕获器。"""
        for cap, name in [
            (self._kb, "键盘"),
            (self._mouse, "鼠标"),
            (self._gamepad, "手柄"),
        ]:
            if cap is not None:
                cap.stop()
                logger.info(f"{name}捕获已停止")

        self._kb = None
        self._mouse = None
        self._gamepad = None
