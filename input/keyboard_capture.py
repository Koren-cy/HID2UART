"""键盘输入捕获模块。

使用 pynput 库监听系统键盘事件，
并通过回调将键盘事件封装为协议帧。
"""

from __future__ import annotations

import logging

from pynput import keyboard

from core import FrameCallback
from protocol import build_keyboard_frame

__all__ = ["KeyboardCapture"]

logger: logging.Logger = logging.getLogger(__name__)


_KEY_TO_VK: dict[keyboard.Key | keyboard.KeyCode, int] = {
    # 修饰键
    keyboard.Key.ctrl: 0x11,
    keyboard.Key.ctrl_l: 0xA2,
    keyboard.Key.ctrl_r: 0xA3,
    keyboard.Key.shift: 0x10,
    keyboard.Key.shift_l: 0xA0,
    keyboard.Key.shift_r: 0xA1,
    keyboard.Key.alt: 0x12,
    keyboard.Key.alt_l: 0xA4,
    keyboard.Key.alt_r: 0xA5,
    keyboard.Key.cmd: 0x5B,
    keyboard.Key.cmd_l: 0x5B,
    keyboard.Key.cmd_r: 0x5C,
    # 控制键
    keyboard.Key.tab: 0x09,
    keyboard.Key.enter: 0x0D,
    keyboard.Key.esc: 0x1B,
    keyboard.Key.backspace: 0x08,
    keyboard.Key.space: 0x20,
    keyboard.Key.caps_lock: 0x14,
    # 编辑键
    keyboard.Key.insert: 0x2D,
    keyboard.Key.delete: 0x2E,
    keyboard.Key.home: 0x24,
    keyboard.Key.end: 0x23,
    keyboard.Key.page_up: 0x21,
    keyboard.Key.page_down: 0x22,
    # 方向键
    keyboard.Key.up: 0x26,
    keyboard.Key.down: 0x28,
    keyboard.Key.left: 0x25,
    keyboard.Key.right: 0x27,
    # 功能键
    keyboard.Key.f1: 0x70,
    keyboard.Key.f2: 0x71,
    keyboard.Key.f3: 0x72,
    keyboard.Key.f4: 0x73,
    keyboard.Key.f5: 0x74,
    keyboard.Key.f6: 0x75,
    keyboard.Key.f7: 0x76,
    keyboard.Key.f8: 0x77,
    keyboard.Key.f9: 0x78,
    keyboard.Key.f10: 0x79,
    keyboard.Key.f11: 0x7A,
    keyboard.Key.f12: 0x7B,
    # 其他
    keyboard.Key.num_lock: 0x90,
    keyboard.Key.scroll_lock: 0x91,
    keyboard.Key.print_screen: 0x2C,
    keyboard.Key.pause: 0x13,
    keyboard.Key.menu: 0x5D,
}


class KeyboardCapture:
    """
    键盘事件捕获器。

    每当检测到按键按下或释放时，构造一个键盘帧并调用 on_frame 回调。
    """

    def __init__(self, on_frame: FrameCallback) -> None:
        """
        参数：
            on_frame: 帧就绪时的回调，签名为 (frame: bytes) -> None
        """
        self._on_frame: FrameCallback = on_frame
        self._listener: keyboard.Listener | None = None

    def start(self) -> None:
        """启动键盘监听。"""
        if self._listener is None:
            self._listener = keyboard.Listener(
                on_press=self._on_press,
                on_release=self._on_release,
            )
            self._listener.start()
            logger.debug("键盘监听器已启动")

    def stop(self) -> None:
        """停止键盘监听并清理资源。"""
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
            logger.debug("键盘监听器已停止")

    def _on_press(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        """按键按下事件回调。"""
        try:
            vk: int | None = self._vk_from_key(key)
            if vk is not None:
                frame: bytes = build_keyboard_frame(vk, pressed=True)
                self._on_frame(frame)
        except Exception:
            logger.exception("键盘事件处理失败")

    def _on_release(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        """按键释放事件回调。"""
        try:
            vk: int | None = self._vk_from_key(key)
            if vk is not None:
                frame: bytes = build_keyboard_frame(vk, pressed=False)
                self._on_frame(frame)
        except Exception:
            logger.exception("键盘事件处理失败")

    @staticmethod
    def _vk_from_key(key: keyboard.Key | keyboard.KeyCode) -> int | None:
        """
        从 pynput Key / KeyCode 对象中提取 Windows 虚拟键码。

        - KeyCode 对象（普通字符）：优先使用 key.vk，
          在 Windows 上 from_char 创建的 KeyCode 的 vk=None，改用 ord(key.char)
        - Key 枚举对象（修饰键、功能键等）：查映射表

        参数：
            key: pynput 键盘事件对象

        返回：
            Windows 虚拟键码，查不到时返回 None
        """
        # 普通字符键，有 vk 属性
        if isinstance(key, keyboard.KeyCode):
            if key.vk is not None:
                return key.vk
            # Windows 平台：from_char 创建的 KeyCode 的 vk=None，用 char 转换
            if key.char is not None:
                return ord(key.char)
            return None
        # 修饰键、功能键等特殊键，查映射表
        if key in _KEY_TO_VK:
            return _KEY_TO_VK[key]
        return None
