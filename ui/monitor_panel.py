"""帧监视面板模块。

以十六进制 + 可读描述的形式实时显示已发送的协议帧，
自动维护最近 MAX_LINES 行记录，超出后逐行淘汰旧数据。
"""

from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from protocol import describe_frame

__all__ = ["MonitorPanel"]

# 最大显示行数
MAX_LINES: int = 500


class MonitorPanel(QWidget):
    """实时帧监视面板，显示十六进制数据和可读描述。"""

    MAX_LINES: int = 500

    def __init__(self) -> None:
        super().__init__()
        self._count: int = 0
        self._build_ui()

    def append_frame(self, raw_bytes: bytes) -> None:
        """
        追加一帧到监视视图。
        显示格式：[序号] XX XX ... XX  可读描述
        """
        hex_str: str = " ".join(f"{b:02X}" for b in raw_bytes)
        desc: str = describe_frame(raw_bytes)
        line: str = f"[{self._count:06d}] {hex_str}  {desc}"
        self._hex_view.appendPlainText(line)
        self._count += 1
        self._stat_label.setText(f"已发送: {self._count}")

        # 超出最大行数时删除最旧一行
        doc = self._hex_view.document()
        if doc.blockCount() > self.MAX_LINES:
            cursor = self._hex_view.textCursor()
            cursor.movePosition(cursor.Start)
            cursor.select(cursor.LineUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()

    def reset(self) -> None:
        """清空所有显示内容并重置计数器。"""
        self._hex_view.clear()
        self._count = 0
        self._stat_label.setText("已发送: 0")

    def _build_ui(self) -> None:
        """构建面板 UI 布局。"""
        layout: QVBoxLayout = QVBoxLayout(self)

        group: QGroupBox = QGroupBox("帧监视器")
        vlay: QVBoxLayout = QVBoxLayout(group)

        font: QFont = QFont("Courier New", 8)
        self._hex_view: QPlainTextEdit = QPlainTextEdit()
        self._hex_view.setFont(font)
        self._hex_view.setReadOnly(True)
        vlay.addWidget(self._hex_view)

        bar: QHBoxLayout = QHBoxLayout()
        self._stat_label: QLabel = QLabel("已发送: 0")
        self._stat_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        bar.addWidget(self._stat_label)
        bar.addStretch()

        self._clear_btn: QPushButton = QPushButton("清空")
        self._clear_btn.clicked.connect(self.reset)
        bar.addWidget(self._clear_btn)

        vlay.addLayout(bar)
        layout.addWidget(group)
