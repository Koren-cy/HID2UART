"""输入捕获管理器模块。

统一管理所有 HID 输入捕获器的生命周期，
将 MainWindow 从具体 CaptureBackend 实现中解耦。
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

from core import CaptureBackend, FrameCallback

if TYPE_CHECKING:
    from input.gamepad_capture import GamepadCapture
    from input.keyboard_capture import KeyboardCapture
    from input.mouse_capture import MouseCapture

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
        self._start_if_requested(types, "kb", "键盘", self._init_keyboard)
        self._start_if_requested(types, "mouse", "鼠标", self._init_mouse)
        self._start_if_requested(types, "gamepad", "手柄", self._init_gamepad)

    def _start_if_requested(
        self,
        types: set[str],
        key: str,
        name: str,
        init_fn: Callable[[], CaptureBackend],
    ) -> None:
        """如果请求的类型包含 key，则调用 init_fn 初始化并启动捕获器。"""
        if key in types:
            instance: CaptureBackend = init_fn()
            instance.start()
            logger.info(f"{name}捕获已启动")

    def _init_keyboard(self) -> KeyboardCapture:
        """初始化键盘捕获器。"""
        from input.keyboard_capture import KeyboardCapture

        self._kb = KeyboardCapture(self._on_frame)
        return self._kb

    def _init_mouse(self) -> MouseCapture:
        """初始化鼠标捕获器。"""
        from input.mouse_capture import MouseCapture

        self._mouse = MouseCapture(self._on_frame)
        return self._mouse

    def _init_gamepad(self) -> GamepadCapture:
        """初始化手柄捕获器。"""
        from input.gamepad_capture import GamepadCapture

        self._gamepad = GamepadCapture(self._on_frame)
        return self._gamepad

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
