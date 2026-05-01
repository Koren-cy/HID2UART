"""HID2UART 通信协议定义。

帧格式（所有多字节整数均为小端序）：

    ┌────────┬───────┬───────┬───────┬───────┬────────┐
    │ 帧头   │ 类型  │ 长度  │ 载荷  │ CRC   │ 帧尾   │
    │ 0xFA55 │ 1字节 │ 1字节 │ N字节 │ 1字节 │ 0x0D0A │
    └────────┴───────┴───────┴───────┴───────┴────────┘

    [0-1]      帧头       0xFA55
    [2]        类型       0x01=键盘 0x02=鼠标按键 0x04=鼠标移动/滚轮 0x03=手柄 0x05=手柄摇杆
    [3]        载荷长度   payload 字节数
    [4..N]     载荷       类型相关的具体数据
    [N+1]      CRC-8      类型+载荷 的校验和
    [N+2..N+3] 帧尾       0x0D0A

典型帧长度：键盘 9 字节，鼠标按键 9 字节，鼠标移动 16 字节，手柄 11 字节，手柄摇杆 18 字节

帧示例：键盘按下 A 键（虚拟键码 0x41）

    FA 55 01 02 41 01 73 0D 0A
    │  │  │  │  │  │  │  │  │
    │  │  │  │  │  │  │  │  └── 帧尾（1）= 0x0A
    │  │  │  │  │  │  │  └───── 帧尾（0）= 0x0D
    │  │  │  │  │  │  └──────── CRC-8
    │  │  │  │  │  └─────────── 动作（按下=0x01）
    │  │  │  │  └────────────── 虚拟键码 A=0x41
    │  │  │  └───────────────── 载荷长度（2字节）
    │  │  └──────────────────── 类型（键盘=0x01）
    │  └─────────────────────── 帧头（1）= 0x55
    └────────────────────────── 帧头（0）= 0xFA
"""

from __future__ import annotations

import struct
from enum import IntEnum

from utils.crc8 import crc8

__all__ = [
    "FRAME_HEADER",
    "FRAME_TAIL",
    "FrameType",
    "VK_NAMES",
    "MOUSE_BUTTON_NAMES",
    "GP_BUTTON_NAMES",
    "build_keyboard_frame",
    "build_mouse_button_frame",
    "build_mouse_move_frame",
    "build_gamepad_frame",
    "build_gamepad_stick_frame",
    "describe_frame",
]

# 固定帧头 / 帧尾标记，便于接收端帧同步
FRAME_HEADER: bytes = b"\xFA\x55"
FRAME_TAIL: bytes = b"\x0D\x0A"


class FrameType(IntEnum):
    """帧类型枚举，对应帧的第 2 字节。"""

    KEYBOARD = 0x01         # 键盘按键事件
    MOUSE_BUTTON = 0x02     # 鼠标按键事件
    MOUSE_MOVE = 0x04       # 鼠标移动/滚轮事件
    GAMEPAD = 0x03          # 手柄按钮事件
    GAMEPAD_STICK = 0x05    # 手柄摇杆/扳机事件


# Windows 虚拟键码 -> 可读名称映射表
VK_NAMES: dict[int, str] = {
    0x01: "LeftButton",
    0x02: "RightButton",
    0x04: "MiddleButton",
    0x05: "XButton1",
    0x06: "XButton2",
    0x08: "Backspace",
    0x09: "Tab",
    0x0C: "Clear",
    0x0D: "Return",
    0x10: "Shift",
    0x11: "Ctrl",
    0x12: "Alt",
    0x14: "CapsLock",
    0x1B: "Escape",
    0x20: "Space",
    0x21: "PageUp",
    0x22: "PageDown",
    0x23: "End",
    0x24: "Home",
    0x25: "Left",
    0x26: "Up",
    0x27: "Right",
    0x28: "Down",
    0x2C: "PrintScreen",
    0x2D: "Insert",
    0x2E: "Delete",
    0x30: "0",
    0x31: "1",
    0x32: "2",
    0x33: "3",
    0x34: "4",
    0x35: "5",
    0x36: "6",
    0x37: "7",
    0x38: "8",
    0x39: "9",
    0x41: "A",
    0x42: "B",
    0x43: "C",
    0x44: "D",
    0x45: "E",
    0x46: "F",
    0x47: "G",
    0x48: "H",
    0x49: "I",
    0x4A: "J",
    0x4B: "K",
    0x4C: "L",
    0x4D: "M",
    0x4E: "N",
    0x4F: "O",
    0x50: "P",
    0x51: "Q",
    0x52: "R",
    0x53: "S",
    0x54: "T",
    0x55: "U",
    0x56: "V",
    0x57: "W",
    0x58: "X",
    0x59: "Y",
    0x5A: "Z",
    0x5B: "Win",
    0x5C: "WinR",
    0x5D: "Menu",
    0x60: "Num0",
    0x61: "Num1",
    0x62: "Num2",
    0x63: "Num3",
    0x64: "Num4",
    0x65: "Num5",
    0x66: "Num6",
    0x67: "Num7",
    0x68: "Num8",
    0x69: "Num9",
    0x6A: "NumMultiply",
    0x6B: "NumAdd",
    0x6D: "NumSubtract",
    0x6E: "NumDecimal",
    0x6F: "NumDivide",
    0x70: "F1",
    0x71: "F2",
    0x72: "F3",
    0x73: "F4",
    0x74: "F5",
    0x75: "F6",
    0x76: "F7",
    0x77: "F8",
    0x78: "F9",
    0x79: "F10",
    0x7A: "F11",
    0x7B: "F12",
    0x90: "NumLock",
    0x91: "ScrollLock",
    0xA0: "ShiftL",
    0xA1: "ShiftR",
    0xA2: "CtrlL",
    0xA3: "CtrlR",
    0xA4: "AltL",
    0xA5: "AltR",
}

# 鼠标按键位掩码 -> 可读名称映射
MOUSE_BUTTON_NAMES: dict[int, str] = {
    0: "L",
    1: "R",
    2: "M",
    4: "X1",
    5: "X2",
}

# 手柄按钮位掩码 -> 可读名称映射
GP_BUTTON_NAMES: dict[int, str] = {
    0: "A",
    1: "B",
    2: "X",
    3: "Y",
    4: "LB",
    5: "RB",
    6: "Back",
    7: "Start",
    8: "LS",
    9: "RS",
    10: "Guide",
    11: "Touch",
    12: "DPadL",
    13: "DPadR",
    14: "DPadUp",
    15: "DPadDown",
}


def build_keyboard_frame(vk: int, pressed: bool) -> bytes:
    """
    构造键盘事件帧。

    载荷格式（2 字节）：
      [0] 虚拟键码
      [1] 动作 0x01=按下 0x00=释放

    参数：
        vk: Windows 虚拟键码
        pressed: True 为按下，False 为释放

    返回：
        完整的二进制帧字节串
    """
    action: int = 0x01 if pressed else 0x00
    payload: bytes = struct.pack("<BB", vk, action)
    return _build_frame(FrameType.KEYBOARD, payload)


def build_mouse_button_frame(button: int, pressed: bool) -> bytes:
    """
    构造鼠标按键事件帧。

    载荷格式（2 字节）：
      [0] 按键位掩码
      [1] 动作 0x01=按下 0x00=释放

    参数：
        button: 触发事件的按键位掩码
        pressed: True 为按下，False 为释放

    返回：
        完整的二进制帧字节串
    """
    action: int = 0x01 if pressed else 0x00
    payload: bytes = struct.pack("<BB", button & 0xFF, action)
    return _build_frame(FrameType.MOUSE_BUTTON, payload)


def build_mouse_move_frame(dx: int, dy: int, scroll: int) -> bytes:
    """
    构造鼠标移动/滚轮事件帧。

    载荷格式（9 字节）：
      [0]   X 方向符号（0=正 1=负）
      [1]   Y 方向符号（0=正 1=负）
      [2]   滚轮符号  （0=正 1=负）
      [3-4] X 方向绝对位移（小端序 uint16）
      [5-6] Y 方向绝对位移（小端序 uint16）
      [7-8] 滚轮绝对值    （小端序 uint16）

    注意：位移采用"符号位 + 绝对值"编码，以支持负数且避免结构体歧义。

    参数：
        dx: X 方向相对位移（可正可负）
        dy: Y 方向相对位移（可正可负）
        scroll: 滚轮值    （可正可负）

    返回：
        完整的二进制帧字节串
    """
    dx_abs: int = abs(dx)
    dy_abs: int = abs(dy)
    scroll_abs: int = abs(scroll)
    dx_sign: int = 0x01 if dx < 0 else 0x00
    dy_sign: int = 0x01 if dy < 0 else 0x00
    scroll_sign: int = 0x01 if scroll < 0 else 0x00
    payload: bytes = struct.pack(
        "<BBBHHH", dx_sign, dy_sign, scroll_sign, dx_abs, dy_abs, scroll_abs
    )
    return _build_frame(FrameType.MOUSE_MOVE, payload)


def build_gamepad_frame(
    gamepad_id: int, button: int, pressed: bool
) -> bytes:
    """
    构造游戏手柄按钮事件帧。

    载荷格式（4 字节）：
      [0]     手柄索引
      [1-2]   按键位掩码（小端序 uint16）
      [3]     动作 0x01=按下 0x00=释放

    参数：
        gamepad_id: 手柄索引
        button: 触发事件的按键位掩码
        pressed: True 为按下，False 为释放

    返回：
        完整的二进制帧字节串
    """
    action: int = 0x01 if pressed else 0x00
    payload: bytes = struct.pack(
        "<BBH", gamepad_id & 0xFF, action, button & 0xFFFF
    )
    return _build_frame(FrameType.GAMEPAD, payload)


def build_gamepad_stick_frame(
    gamepad_id: int,
    lx: int,
    ly: int,
    rx: int,
    ry: int,
    lt: int,
    rt: int,
) -> bytes:
    """
    构造游戏手柄摇杆/扳机事件帧。

    载荷格式（11 字节）：
      [0]   手柄索引
      [1-2] 左摇杆 X 轴（小端序 int16）
      [3-4] 左摇杆 Y 轴（小端序 int16）
      [5-6] 右摇杆 X 轴（小端序 int16）
      [7-8] 右摇杆 Y 轴（小端序 int16）
      [9]   左扳机（0 ~ 255）
      [10]  右扳机（0 ~ 255）

    参数：
        gamepad_id: 手柄索
        lx: 左摇杆 X 轴（-32767 ~ +32767）
        ly: 左摇杆 Y 轴（-32767 ~ +32767）
        rx: 右摇杆 X 轴（-32767 ~ +32767）
        ry: 右摇杆 Y 轴（-32767 ~ +32767）
        lt: 左扳机（0 ~ 255）
        rt: 右扳机（0 ~ 255）

    返回：
        完整的二进制帧字节串
    """
    payload: bytes = struct.pack(
        "<BhhhhBB", gamepad_id, lx, ly, rx, ry, lt, rt
    )
    return _build_frame(FrameType.GAMEPAD_STICK, payload)


def _build_frame(frame_type: FrameType, payload: bytes) -> bytes:
    """组装完整帧：帧头 + 类型 + 长度 + 载荷 + CRC + 帧尾。"""
    type_and_len: bytes = bytes([frame_type, len(payload)])
    crc: int = crc8(type_and_len + payload)
    return FRAME_HEADER + type_and_len + payload + bytes([crc]) + FRAME_TAIL


def describe_frame(frame: bytes) -> str:
    """
    将原始帧字节转换为人类可读的描述字符串，用于日志和界面显示。
    若帧格式非法则返回十六进制原始数据。

    参数：
        frame: 原始帧字节串

    返回：
        可读描述字符串，格式错误时返回 <malformed: XX XX ...>
    """
    try:
        frame_type: int = frame[2]
        payload: bytes = frame[4 : 4 + frame[3]]
    except (IndexError, TypeError):
        return f"<malformed: {frame.hex(' ')}>"

    if frame_type == FrameType.KEYBOARD:
        vk: int = payload[0]
        action: int = payload[1]
        key: str = VK_NAMES.get(vk, f"0x{vk:02X}")
        state: str = "pressed" if action else "released"
        return f"KEY {key} {state}"
    elif frame_type == FrameType.MOUSE_BUTTON:
        button, action = struct.unpack("<BB", payload[:2])
        btn_names: list[str] = [
            MOUSE_BUTTON_NAMES[bit]
            for bit in range(8)
            if (button & (1 << bit)) and bit in MOUSE_BUTTON_NAMES
        ]
        btn_str: str = ",".join(btn_names) if btn_names else f"?(0x{button:02X})"
        state = "pressed" if action == 0x01 else "released"
        return f"MOUSE BTN [{btn_str}] {state}"
    elif frame_type == FrameType.MOUSE_MOVE:
        (
            dx_sign,
            dy_sign,
            scroll_sign,
            dx_abs,
            dy_abs,
            scroll_abs,
        ) = struct.unpack("<BBBHHH", payload)
        dx: int = -dx_abs if dx_sign else dx_abs
        dy: int = -dy_abs if dy_sign else dy_abs
        scroll: int = -scroll_abs if scroll_sign else scroll_abs
        parts: list[str] = []
        if dx != 0:
            parts.append(f"dx={dx:+d}")
        if dy != 0:
            parts.append(f"dy={dy:+d}")
        if scroll != 0:
            parts.append(f"scroll={scroll:+d}")
        return "MOUSE " + " ".join(parts) if parts else "MOUSE"
    elif frame_type == FrameType.GAMEPAD:
        gp_id, action, button = struct.unpack("<BBH", payload[:4])
        btn_names = [
            GP_BUTTON_NAMES[bit]
            for bit in range(16)
            if (button & (1 << bit)) and bit in GP_BUTTON_NAMES
        ]
        btn_str = ",".join(btn_names) if btn_names else f"?(0x{button:04X})"
        state = "pressed" if action == 0x01 else "released"
        return f"GP{gp_id} BTN [{btn_str}] {state}"
    elif frame_type == FrameType.GAMEPAD_STICK:
        gp_id, lx, ly, rx, ry, lt, rt = struct.unpack("<BhhhhBB", payload)
        return (
            f"GP{gp_id} STICK \n"
            f"L=({lx:+6d},{ly:+6d}) R=({rx:+6d},{ry:+6d}) "
            f"LT={lt:3d} RT={rt:3d}"
        )
    else:
        return f"<type=0x{frame_type:02X} {payload.hex(' ')}>"
