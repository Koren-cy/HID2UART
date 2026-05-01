"""串口通信面板模块。

提供串口选择、参数配置、连接/断开及数据发送功能。
每隔 3 秒自动刷新可用 COM 端口列表（热插拔支持）。
"""

from __future__ import annotations

import logging
import typing

import serial
import serial.tools.list_ports
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import (
    QComboBox,
    QGridLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

__all__ = ["SerialPanel"]

logger: logging.Logger = logging.getLogger(__name__)

# 常用波特率选项
BAUD_RATES: list[int] = [
    9600,
    19200,
    38400,
    57600,
    115200,
    230400,
    460800,
    921600,
]

# 刷新间隔（毫秒）
_REFRESH_INTERVAL_MS: int = 3000


class SerialPanel(QWidget):
    """串口配置与连接管理面板。"""

    def __init__(
        self,
        on_connected: typing.Callable[[str], None],
        on_disconnected: typing.Callable[[], None],
        on_frame_sent: typing.Callable[[bytes], None],
    ) -> None:
        """
        参数：
            on_connected: 连接成功时调用的回调，签名为 (port_name: str) -> None
            on_disconnected: 断开连接时调用的回调，签名为 () -> None
            on_frame_sent: 帧发送后调用的回调，签名为 (frame: bytes) -> None
        """
        super().__init__()
        self._on_connected: typing.Callable[[str], None] = on_connected
        self._on_disconnected: typing.Callable[[], None] = on_disconnected
        self._on_frame_sent: typing.Callable[[bytes], None] = on_frame_sent
        self._serial: serial.Serial | None = None
        self._build_ui()

        # 定时刷新 COM 端口列表
        self._refresh_timer: QTimer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_ports)
        self._refresh_timer.start(_REFRESH_INTERVAL_MS)
        self._refresh_ports()

    def is_connected(self) -> bool:
        """返回当前是否已与串口建立连接。"""
        return self._serial is not None and self._serial.is_open

    def send_frame(self, frame: bytes) -> None:
        """将一帧字节数据写入串口。"""
        if self._serial and self._serial.is_open:
            try:
                self._serial.write(frame)
                self._on_frame_sent(frame)
            except serial.SerialException as e:
                logger.error("串口写入失败: %s", e)

    def _build_ui(self) -> None:
        """构建面板 UI 布局。"""
        layout: QVBoxLayout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignTop)

        group: QGroupBox = QGroupBox("串口设置")
        glay: QGridLayout = QGridLayout(group)
        glay.setSpacing(10)

        # 端口选择
        glay.addWidget(QLabel("端口:"), 0, 0)
        self._port_combo: QComboBox = QComboBox()
        self._port_combo.setMinimumWidth(80)
        glay.addWidget(self._port_combo, 0, 1)

        self._refresh_btn: QPushButton = QPushButton("刷新")
        self._refresh_btn.clicked.connect(self._refresh_ports)
        glay.addWidget(self._refresh_btn, 0, 2)

        # 波特率
        glay.addWidget(QLabel("波特率:"), 1, 0)
        self._baud_combo: QComboBox = QComboBox()
        self._baud_combo.addItems(str(b) for b in BAUD_RATES)
        self._baud_combo.setCurrentText("115200")
        glay.addWidget(self._baud_combo, 1, 1, 1, 2)

        # 数据位
        glay.addWidget(QLabel("数据位:"), 2, 0)
        self._databits_combo: QComboBox = QComboBox()
        self._databits_combo.addItems(["8", "7", "6", "5"])
        self._databits_combo.setCurrentText("8")
        glay.addWidget(self._databits_combo, 2, 1, 1, 2)

        # 停止位
        glay.addWidget(QLabel("停止位:"), 3, 0)
        self._stopbits_combo: QComboBox = QComboBox()
        self._stopbits_combo.addItems(["1", "1.5", "2"])
        self._stopbits_combo.setCurrentText("1")
        glay.addWidget(self._stopbits_combo, 3, 1, 1, 2)

        # 校验位
        glay.addWidget(QLabel("校验位:"), 4, 0)
        self._parity_combo: QComboBox = QComboBox()
        self._parity_combo.addItems(["无", "偶校验", "奇校验", "标记", "空格"])
        self._parity_combo.setCurrentText("无")
        glay.addWidget(self._parity_combo, 4, 1, 1, 2)

        # 连接/断开按钮
        self._connect_btn: QPushButton = QPushButton("连接")
        self._connect_btn.clicked.connect(self._toggle_connection)
        glay.addWidget(self._connect_btn, 5, 0, 1, 3)

        layout.addWidget(group)

    def _refresh_ports(self) -> None:
        """扫描并更新下拉列表中的可用 COM 端口。"""
        self._port_combo.blockSignals(True)
        self._port_combo.clear()
        ports: list[serial.tools.list_ports.ListPortInfo] = (
            serial.tools.list_ports.comports()
        )
        for p in ports:
            self._port_combo.addItem(p.device, p.device)
        if not ports:
            self._port_combo.addItem("未检测到", "")
        self._port_combo.blockSignals(False)

    def _toggle_connection(self) -> None:
        """切换连接状态。"""
        if self.is_connected():
            self._disconnect()
        else:
            self._connect()

    def _connect(self) -> None:
        """根据当前 UI 配置打开串口。"""
        port: str | None = self._port_combo.currentData()
        if not port:
            self._connect_btn.setText("请选择端口")
            return
        try:
            parity_map: dict[str, int] = {
                "无": serial.PARITY_NONE,
                "偶校验": serial.PARITY_EVEN,
                "奇校验": serial.PARITY_ODD,
                "标记": serial.PARITY_MARK,
                "空格": serial.PARITY_SPACE,
            }
            stopbits_map: dict[str, float] = {
                "1": serial.STOPBITS_ONE,
                "1.5": serial.STOPBITS_ONE_POINT_FIVE,
                "2": serial.STOPBITS_TWO,
            }
            databits_map: dict[str, int] = {
                "8": serial.EIGHTBITS,
                "7": serial.SEVENBITS,
                "6": serial.SIXBITS,
                "5": serial.FIVEBITS,
            }

            self._serial = serial.Serial(
                port=port,
                baudrate=int(self._baud_combo.currentText()),
                bytesize=databits_map[self._databits_combo.currentText()],
                stopbits=stopbits_map[self._stopbits_combo.currentText()],
                parity=parity_map[self._parity_combo.currentText()],
                timeout=0,
            )
            self._connect_btn.setText("断开")
            # 连接成功后禁用配置控件
            for combo in (
                self._port_combo,
                self._baud_combo,
                self._databits_combo,
                self._stopbits_combo,
                self._parity_combo,
            ):
                combo.setEnabled(False)
            self._on_connected(port)
            logger.info("串口已连接: %s", port)
        except serial.SerialException as e:
            self._connect_btn.setText(f"连接失败")
            logger.error("串口连接失败 [%s]: %s", port, e)

    def _disconnect(self) -> None:
        """关闭串口连接并恢复 UI 控件状态。"""
        if self._serial:
            self._serial.close()
            self._serial = None
        self._connect_btn.setText("连接")
        for combo in (
            self._port_combo,
            self._baud_combo,
            self._databits_combo,
            self._stopbits_combo,
            self._parity_combo,
        ):
            combo.setEnabled(True)
        self._on_disconnected()
        logger.info("串口已断开")
