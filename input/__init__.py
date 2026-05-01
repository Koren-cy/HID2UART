"""HID 输入捕获模块包。"""
from input.keyboard_capture import KeyboardCapture
from input.mouse_capture import MouseCapture
from input.gamepad_capture import GamepadCapture

__all__ = ["KeyboardCapture", "MouseCapture", "GamepadCapture"]
