"""核心类型和接口定义。

集中定义项目范围内共享的类型别名和协议接口，
避免重复定义并提供统一的类型约束。
"""

from __future__ import annotations

from typing import Callable, Protocol, runtime_checkable

__all__ = ["FrameCallback", "ErrorCallback", "CaptureBackend"]


# 帧回调类型别名
FrameCallback = Callable[[bytes], None]

# 错误回调类型别名，用于错误传播
ErrorCallback = Callable[[str, Exception], None]


@runtime_checkable
class CaptureBackend(Protocol):
    """所有 HID 输入捕获器的公共接口。"""

    def start(self) -> None:
        """启动输入捕获。"""
        ...

    def stop(self) -> None:
        """停止输入捕获并清理资源。"""
        ...
