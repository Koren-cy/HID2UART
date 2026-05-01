"""HID 输入捕获模块包。"""
from input.gamepad_capture import GamepadCapture
from input.keyboard_capture import KeyboardCapture
from input.mouse_capture import MouseCapture

__all__ = ["KeyboardCapture", "MouseCapture", "GamepadCapture"]
