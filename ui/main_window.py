"""主窗口模块。

协调所有 UI 面板与输入捕获模块：
- 顶栏：选择要捕获的输入类型，开始/停止 按钮
- 下方左右分栏：左侧串口配置面板，右侧帧监视面板
- 状态栏：显示连接状态和捕获状态

帧流向：输入捕获 -> 协议帧 ->  监视面板 + 串口发送
"""

from __future__ import annotations

import logging

from PyQt5.QtCore import QEvent, QObject, Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from capture_manager import CaptureManager

__all__ = ["MainWindow"]

logger: logging.Logger = logging.getLogger(__name__)

# 面板宽度常量（像素）
_SERIAL_PANEL_WIDTH: int = 280
_MONITOR_PANEL_WIDTH: int = 620


class _Signals(QObject):
    """跨线程帧传递信号。

    由于 pynput 的监听回调运行在独立后台线程，此信号将帧发往主线程，
    确保所有 PyQt 操作在主线程执行。
    """

    frame_out: pyqtSignal = pyqtSignal(bytes)


class MainWindow(QMainWindow):
    """主窗口，协调输入捕获、串口通信和帧监视。"""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("HID2UART - HID转串口工具")
        self.resize(900, 600)

        self._signals: _Signals = _Signals()
        self._capture_running: bool = False

        self._manager: CaptureManager = CaptureManager(
            lambda frame: self._signals.frame_out.emit(frame)
        )

        # 帧信号连接到主窗口槽，在主线程执行
        self._signals.frame_out.connect(self._on_frame_out)

        self._build_ui()
        logger.info("主窗口初始化完成")

    def start_capture(self) -> None:
        """根据勾选项启动对应的输入捕获器。"""
        if self._capture_running:
            return
        self._capture_running = True

        types: set[str] = set()
        if self._kb_cb.isChecked():
            types.add("kb")
        if self._mouse_cb.isChecked():
            types.add("mouse")
        if self._gamepad_cb.isChecked():
            types.add("gamepad")

        self._manager.start(types)

        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._status_label.setText("正在捕获...")

    def stop_capture(self) -> None:
        """停止所有正在运行的输入捕获器。"""
        if not self._capture_running:
            return
        self._capture_running = False

        self._manager.stop()

        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._status_label.setText("已停止")

    def _on_frame_out(self, frame: bytes) -> None:
        """帧信号处理槽：同时输出到监视面板和串口。"""
        self._monitor.append_frame(frame)
        self._serial.send_frame(frame)

    def _build_ui(self) -> None:
        """构建主窗口 UI 布局。"""
        central: QWidget = QWidget()
        self.setCentralWidget(central)
        root: QVBoxLayout = QVBoxLayout(central)

        # ---- 捕获控制栏 ----
        ctrl: QGroupBox = QGroupBox("捕获控制")
        hlay: QHBoxLayout = QHBoxLayout(ctrl)

        self._kb_cb: QCheckBox = QCheckBox("键盘")
        self._kb_cb.setChecked(True)
        hlay.addWidget(self._kb_cb)

        self._mouse_cb: QCheckBox = QCheckBox("鼠标")
        self._mouse_cb.setChecked(True)
        hlay.addWidget(self._mouse_cb)

        self._gamepad_cb: QCheckBox = QCheckBox("手柄")
        self._gamepad_cb.setChecked(True)
        hlay.addWidget(self._gamepad_cb)

        hlay.addStretch()

        self._start_btn: QPushButton = QPushButton("开始捕获")
        self._start_btn.clicked.connect(self.start_capture)
        hlay.addWidget(self._start_btn)

        self._stop_btn: QPushButton = QPushButton("停止捕获")
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self.stop_capture)
        hlay.addWidget(self._stop_btn)

        root.addWidget(ctrl)

        # ---- 串口 + 监视面板 ----
        splitter: QSplitter = QSplitter(Qt.Horizontal)

        from ui.serial_panel import SerialPanel

        self._serial: SerialPanel = SerialPanel(
            on_connected=lambda p: self._status_label.setText(f"已连接到 {p}"),
            on_disconnected=lambda: self._status_label.setText("已断开连接"),
            on_frame_sent=lambda _: None,
        )
        splitter.addWidget(self._serial)

        from ui.monitor_panel import MonitorPanel

        self._monitor: MonitorPanel = MonitorPanel()
        splitter.addWidget(self._monitor)

        splitter.setSizes([_SERIAL_PANEL_WIDTH, _MONITOR_PANEL_WIDTH])
        root.addWidget(splitter, 1)

        # ---- 状态栏 ----
        bar: QStatusBar = QStatusBar()
        self.setStatusBar(bar)
        self._status_label: QLabel = QLabel("就绪")
        bar.addWidget(self._status_label)

    def closeEvent(self, event: QEvent) -> None:
        """窗口关闭时确保所有捕获器停止。"""
        self.stop_capture()
        logger.info("应用程序关闭")
        event.accept()
