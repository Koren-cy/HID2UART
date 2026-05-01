"""鼠标输入捕获模块。

使用 pynput 库监听系统鼠标事件，
通过独立定时器轮询 GetCursorPos 计算移动位移，绕过 pynput 的坐标夹取问题。
"""

from __future__ import annotations

import ctypes
import logging
import threading
import time

from pynput import mouse

from core import FrameCallback
from protocol import build_mouse_button_frame, build_mouse_move_frame

__all__ = ["MouseCapture"]

logger: logging.Logger = logging.getLogger(__name__)


class POINT(ctypes.Structure):
    """Windows POINT 结构体。"""

    _fields_: list[tuple[str, type]] = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class MouseCapture:
    """
    鼠标事件捕获器。

    按键事件和移动/滚轮事件完全分开：
    - 按键变化 -> build_mouse_button_frame (MOUSE_BUTTON)
    - 移动/滚轮 -> build_mouse_move_frame (MOUSE_MOVE)

    所有共享状态通过 threading.Lock 保护，确保线程安全。
    """

    # 轮询间隔（秒）
    _POLL_INTERVAL: float = 0.001
    # 距离边缘多少像素时触发重置
    _EDGE_MARGIN: int = 32

    def __init__(self, on_frame: FrameCallback) -> None:
        """
        参数：
            on_frame: 帧就绪时的回调，签名为 (frame: bytes) -> None
        """
        self._on_frame: FrameCallback = on_frame
        self._listener: mouse.Listener | None = None
        self._lock: threading.Lock = threading.Lock()
        self._prev_buttons: int = 0
        self._started: bool = False

        # 轮询相关（均受 _lock 保护）
        self._poll_thread: threading.Thread | None = None
        self._last_x: int = 0
        self._last_y: int = 0
        self._accum_dx: int = 0
        self._accum_dy: int = 0
        self._accum_scroll: int = 0
        self._skip_next_poll: bool = False
        self._initialized: bool = False

        # 拖拽状态（受 _lock 保护）
        self._is_dragging: bool = False

        # Windows API（只初始化一次）
        self._user32: ctypes.WinDLL = ctypes.windll.user32

    def _get_cursor_pos(self) -> tuple[int, int]:
        """获取当前光标绝对屏幕坐标。"""
        pt: POINT = POINT()
        if not self._user32.GetCursorPos(ctypes.byref(pt)):
            raise OSError(f"GetCursorPos failed, error code: {ctypes.get_last_error()}")
        return pt.x, pt.y

    def _set_cursor_pos(self, x: int, y: int) -> None:
        """设置光标位置。"""
        if not self._user32.SetCursorPos(x, y):
            logger.warning("SetCursorPos failed, error code: %d", ctypes.get_last_error())

    def _get_screen_size(self) -> tuple[int, int]:
        """获取屏幕分辨率。"""
        return self._user32.GetSystemMetrics(0), self._user32.GetSystemMetrics(1)

    def start(self) -> None:
        """启动鼠标监听和位移轮询。"""
        with self._lock:
            if self._started:
                return
            self._started = True
            self._is_dragging = False
            self._accum_dx = 0
            self._accum_dy = 0
            self._accum_scroll = 0
            self._skip_next_poll = False
            self._initialized = False

            # 初始化位置
            cx, cy = self._get_cursor_pos()
            self._last_x = cx
            self._last_y = cy
            self._initialized = True

        # 启动 pynput 监听（仅处理点击和滚轮，移动由后台线程处理）
        self._listener = mouse.Listener(
            on_move=self._on_pynput_move,
            on_click=self._on_click,
            on_scroll=self._on_scroll,
        )
        self._listener.start()

        # 启动单后台线程轮询（替代 Timer 链，避免对象泄漏）
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()
        logger.debug("鼠标捕获器已启动")

    def stop(self) -> None:
        """停止鼠标监听和轮询线程。"""
        with self._lock:
            self._started = False
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
        if self._poll_thread is not None:
            self._poll_thread.join(timeout=2)
            self._poll_thread = None
        logger.debug("鼠标捕获器已停止")

    def _poll_loop(self) -> None:
        """后台线程轮询：计算 dx/dy，检测边缘夹取，发送移动/滚轮帧。"""
        while True:
            # 检查退出信号
            with self._lock:
                if not self._started:
                    break

            try:
                self._poll_once()
            except OSError as e:
                logger.warning("获取光标位置失败: %s", e)

            time.sleep(self._POLL_INTERVAL)

    def _poll_once(self) -> None:
        """单次轮询逻辑，由 _poll_loop 调用。"""
        cx, cy = self._get_cursor_pos()
        sw, sh = self._get_screen_size()

        with self._lock:
            if not self._initialized:
                self._last_x = cx
                self._last_y = cy
                self._initialized = True
                return

            if self._skip_next_poll:
                self._skip_next_poll = False
                self._last_x = cx
                self._last_y = cy
                return

            dx: int = cx - self._last_x
            dy: int = cy - self._last_y
            self._last_x = cx
            self._last_y = cy

            # 检测边缘夹取：位移很小但光标在边缘附近，说明被夹取了
            near_edge: bool = (
                cx < self._EDGE_MARGIN
                or cx > sw - self._EDGE_MARGIN
                or cy < self._EDGE_MARGIN
                or cy > sh - self._EDGE_MARGIN
            )

            if near_edge and not self._is_dragging:
                # 边缘夹取了，累加丢失的位移，下次移回中心后报告
                self._accum_dx += dx
                self._accum_dy += dy
                self._skip_next_poll = True
                self._set_cursor_pos(sw // 2, sh // 2)
                self._last_x = sw // 2
                self._last_y = sh // 2
                self._initialized = True
                self._emit_move(self._accum_dx, self._accum_dy, 0)
                if self._accum_scroll != 0:
                    self._emit_move(0, 0, self._accum_scroll)
                self._accum_dx = 0
                self._accum_dy = 0
                self._accum_scroll = 0
            else:
                # 正常移动或已重置后
                total_dx: int = self._accum_dx + dx
                total_dy: int = self._accum_dy + dy
                total_scroll: int = self._accum_scroll
                self._accum_dx = 0
                self._accum_dy = 0
                self._accum_scroll = 0

                if total_dx != 0 or total_dy != 0:
                    self._emit_move(total_dx, total_dy, 0)

                if total_scroll != 0:
                    self._emit_move(0, 0, total_scroll)

    def _emit_move(self, dx: int, dy: int, scroll: int = 0) -> None:
        """发送鼠标移动/滚轮帧。"""
        try:
            frame: bytes = build_mouse_move_frame(dx, dy, scroll)
            self._on_frame(frame)
        except Exception:
            logger.exception("发送鼠标移动帧失败")

    def _on_pynput_move(self, x: int, y: int) -> None:
        """pynput 的移动回调，不用于 dx/dy 计算（坐标已被夹取）。"""
        pass

    @staticmethod
    def _buttons_mask(button: mouse.Button) -> int:
        """
        将 pynput Button 转换为位掩码。

        Bit0=左 Bit1=右 Bit2=中 Bit4=X1 Bit5=X2
        """
        mask: int = 0
        if button == mouse.Button.left:
            mask |= 1 << 0
        elif button == mouse.Button.right:
            mask |= 1 << 1
        elif button == mouse.Button.middle:
            mask |= 1 << 2
        elif button == mouse.Button.x1:
            mask |= 1 << 4
        elif button == mouse.Button.x2:
            mask |= 1 << 5
        return mask

    def _on_click(
        self, x: int, y: int, button: mouse.Button, pressed: bool
    ) -> None:
        """鼠标按键点击事件回调，发送按键帧。"""
        try:
            mask: int = self._buttons_mask(button)
            with self._lock:
                if pressed:
                    self._prev_buttons |= mask
                    self._is_dragging = True
                else:
                    self._prev_buttons &= ~mask
                    if self._prev_buttons == 0:
                        self._is_dragging = False
            frame: bytes = build_mouse_button_frame(mask, pressed)
            self._on_frame(frame)
        except Exception:
            logger.exception("鼠标按键事件处理失败")

    def _on_scroll(self, x: int, y: int, dx: int, dy: int) -> None:
        """滚轮事件回调，累积滚轮值，等待下一次轮询发送。"""
        try:
            with self._lock:
                self._accum_scroll += dy
        except Exception:
            logger.exception("滚轮事件处理失败")
