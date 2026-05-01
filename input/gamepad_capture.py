"""游戏手柄 / 摇杆输入捕获模块。

使用 pygame 库轮询已连接的游戏手柄状态，
仅在状态发生实际变化时通过回调发送帧，支持热插拔。

实现细节：
- 按钮和摇杆/扳机分开独立处理，互不干扰。
- 按钮：每次检测到按钮状态变化（按下或释放），发送一个按钮帧，载荷包含
  当前所有按钮的位掩码和变化的那组按钮位掩码，供接收端判断哪些按钮变了。
- 摇杆/扳机：摇杆值从 [-1,1] 映射到 [-32767,32767]，扳机从 [-1,1] 归一化到 [0,255]。
- 只有摇杆或扳机值与上次相比有实际变化时才发送摇杆帧。
"""

from __future__ import annotations

import logging
import time
import threading
from typing import Any, Optional

from core import FrameCallback
import pygame

from protocol import build_gamepad_frame, build_gamepad_stick_frame

__all__ = ["GamepadCapture"]

logger: logging.Logger = logging.getLogger(__name__)

# D-pad 方向索引 -> 位掩码映射（Bit12=左 Bit13=右 Bit14=上 Bit15=下）
_BUTTON_HAT_MAP: dict[int, int] = {0: 1, 1: 2, 2: 4, 3: 8}

# 手柄状态字典类型
GamepadState = dict[str, Any]


def _read_gamepad_state(js: pygame.joystick.JoystickType) -> GamepadState:
    """
    读取指定手柄的完整状态。

    返回字典包含：buttons, lx, ly, rx, ry, lt, rt
    """
    # 读取按钮位掩码
    button_mask: int = 0
    for i in range(min(js.get_numbuttons(), 16)):
        if js.get_button(i):
            button_mask |= 1 << i

    def axis(val: float) -> int:
        return int(val * 32767)

    # 读取摇杆轴（假设标准布局：0=LX, 1=LY, 2=RX, 3=RY）
    lx: int = axis(js.get_axis(0)) if js.get_numaxes() > 0 else 0
    ly: int = axis(js.get_axis(1)) if js.get_numaxes() > 1 else 0
    rx: int = axis(js.get_axis(2)) if js.get_numaxes() > 2 else 0
    ry: int = axis(js.get_axis(3)) if js.get_numaxes() > 3 else 0

    # 读取扳机（轴 4=LZ, 5=RZ），映射到 [0,255]
    lt: int = int((js.get_axis(4) + 1.0) * 127.5) if js.get_numaxes() > 4 else 0
    rt: int = int((js.get_axis(5) + 1.0) * 127.5) if js.get_numaxes() > 5 else 0

    # 读取 D-pad（Hat 0），映射到 Bit12-15
    hat: tuple[int, int] = js.get_hat(0) if js.get_numhats() > 0 else (0, 0)
    if hat[0] < 0:
        button_mask |= 1 << 12
    if hat[0] > 0:
        button_mask |= 1 << 13
    if hat[1] < 0:
        button_mask |= 1 << 14
    if hat[1] > 0:
        button_mask |= 1 << 15

    return {
        "buttons": button_mask,
        "lx": lx,
        "ly": ly,
        "rx": rx,
        "ry": ry,
        "lt": lt,
        "rt": rt,
    }


class GamepadCapture:
    """
    游戏手柄事件捕获器。

    内部维护每个手柄的上一帧状态，分别检测按钮和摇杆的变化，
    各自独立发送对应的协议帧：
    - 按键变化 -> build_gamepad_frame (GAMEPAD)
    - 摇杆/扳机变化 -> build_gamepad_stick_frame (GAMEPAD_STICK)
    """

    # 轮询间隔，约 8ms
    _POLL_INTERVAL: float = 0.001

    def __init__(self, on_frame: FrameCallback) -> None:
        """
        参数：
            on_frame: 帧就绪时的回调，签名为 (frame: bytes) -> None
        """
        self._on_frame: FrameCallback = on_frame
        self._running: bool = False
        self._thread: Optional[threading.Thread] = None
        self._lock: threading.Lock = threading.Lock()

    def start(self) -> None:
        """初始化 pygame 并启动轮询线程。"""
        with self._lock:
            if self._running:
                return
            pygame.init()
            pygame.joystick.init()
            self._running = True
            self._thread = threading.Thread(target=self._poll_loop, daemon=True)
            self._thread.start()
            logger.debug("游戏手柄捕获器已启动")

    def stop(self) -> None:
        """停止轮询线程并释放 pygame 资源。"""
        with self._lock:
            if not self._running:
                return
            self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None
        pygame.quit()
        logger.debug("游戏手柄捕获器已停止")

    def _poll_loop(self) -> None:
        """轮询主循环：定时检测所有手柄的按钮和摇杆状态变化。"""
        # 每个手柄的上一帧状态
        prev_button: list[Optional[int]] = []  # 上一帧按钮位掩码
        prev_stick: list[Optional[GamepadState]] = []  # 上一帧摇杆/扳机状态

        def _ensure_capacity(count: int) -> None:
            """确保 prev_* 列表与当前手柄数量同步。"""
            while len(prev_button) < count:
                prev_button.append(None)
            while len(prev_stick) < count:
                prev_stick.append(None)

        while True:
            with self._lock:
                if not self._running:
                    break

            count: int = pygame.joystick.get_count()
            _ensure_capacity(count)

            for i in range(count):
                try:
                    js: pygame.joystick.JoystickType = pygame.joystick.Joystick(i)
                    js.init()
                except pygame.error:
                    prev_button[i] = None
                    prev_stick[i] = None
                    continue

                state: GamepadState = _read_gamepad_state(js)

                # ---- 按钮变化检测 ----
                if state["buttons"] != prev_button[i]:
                    prev_buttons: Optional[int] = prev_button[i]
                    prev_button[i] = state["buttons"]
                    self._emit_button(i, state["buttons"], prev_buttons)

                # ---- 摇杆/扳机变化检测 ----
                stick_state: GamepadState = {
                    k: state[k] for k in ("lx", "ly", "rx", "ry", "lt", "rt")
                }
                if stick_state != prev_stick[i]:
                    prev_stick[i] = stick_state
                    self._emit_stick(i, **stick_state)

            # 处理 pygame 事件（热插拔、按钮事件）
            for _ in range(8):
                for event in pygame.event.get(
                    pygame.JOYBUTTONDOWN + pygame.JOYBUTTONUP
                ):
                    gp_id: int = event.joy
                    if gp_id < 0 or gp_id >= pygame.joystick.get_count():
                        continue
                    try:
                        js = pygame.joystick.Joystick(gp_id)
                        js.init()
                    except pygame.error:
                        continue
                    state = _read_gamepad_state(js)
                    prev_buttons = prev_button[gp_id] if gp_id < len(prev_button) else None
                    self._emit_button(gp_id, state["buttons"], prev_buttons)
                    prev_button[gp_id] = state["buttons"]

            time.sleep(self._POLL_INTERVAL)

    def _emit_button(
        self, gp_id: int, buttons: int, prev: Optional[int]
    ) -> None:
        """检测按钮变化，发送按下/释放帧。"""
        if prev is None:
            for bit in range(16):
                if buttons & (1 << bit):
                    frame: bytes = build_gamepad_frame(gp_id, 1 << bit, True)
                    self._on_frame(frame)
            return

        changed: int = prev ^ buttons
        pressed: int = changed & buttons
        released: int = changed & prev

        for bit in range(16):
            mask: int = 1 << bit
            if pressed & mask:
                frame = build_gamepad_frame(gp_id, mask, True)
                self._on_frame(frame)
            if released & mask:
                frame = build_gamepad_frame(gp_id, mask, False)
                self._on_frame(frame)

    def _emit_stick(self, gp_id: int, **kwargs: Any) -> None:
        """发送手柄摇杆/扳机帧。"""
        frame: bytes = build_gamepad_stick_frame(gp_id, **kwargs)
        self._on_frame(frame)
