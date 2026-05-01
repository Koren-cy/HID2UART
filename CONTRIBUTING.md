# 贡献指南

感谢您对 HID2UART 项目的关注！以下是帮助您快速上手的指南。

## 开发环境设置

### 1. 克隆项目

```bash
git clone https://github.com/your-repo/hid2uart.git
cd hid2uart
```

### 2. 创建虚拟环境（推荐）

```bash
python -m venv venv
.\venv\Scripts\activate
```

### 3. 安装依赖

开发环境（包含所有工具）：

```bash
pip install -e ".[dev]"
```

仅运行时依赖：

```bash
pip install -r requirements.txt
```

## 代码规范

### 格式化工具

本项目使用 [ruff](https://docs.astral.sh/ruff/) 作为代码检查和格式化工具。

```bash
# 检查代码
ruff check .

# 自动修复可修复的问题
ruff check --fix .
```

### 类型检查

使用 [mypy](https://mypy.readthedocs.io/) 进行静态类型检查：

```bash
mypy .
```

### 文档字符串规范

所有公共函数必须包含中文 docstring，推荐使用 Google 风格：

```python
def build_keyboard_frame(vk: int, pressed: bool) -> bytes:
    """
    构造键盘事件帧。

    载荷格式（2 字节）：
      [0] 虚拟键码 (vk)
      [1] 动作 0x01=按下 0x00=释放

    参数：
        vk: Windows 虚拟键码
        pressed: True 为按下，False 为释放

    返回：
        完整的二进制帧字节串
    """
```

### 模块公共 API

每个模块必须通过 `__all__` 显式声明其公共 API：

```python
__all__ = [
    "FRAME_HEADER",
    "FRAME_TAIL",
    "FrameType",
    "build_keyboard_frame",
    ...
]
```

## 运行测试

```bash
# 运行所有测试
pytest

# 运行特定文件
pytest tests/test_protocol.py

# 带覆盖率报告
pytest --cov=. --cov-report=term-missing

# 仅运行上次失败过的测试
pytest --lf
```

## 分支管理

- `main` - 稳定版本，始终可发布
- 功能开发请创建新分支：`git checkout -b feature/your-feature-name`

## 提交流序

1. Fork 本仓库
2. 创建功能分支：`git checkout -b feature/your-feature-name`
3. 编写代码，添加测试
4. 确保通过所有检查：`ruff check . && mypy . && pytest`
5. 提交代码：`git commit -m "描述您的更改"`
6. 推送到 Fork 的仓库：`git push origin feature/your-feature-name`
7. 打开 Pull Request

## 报告问题

请使用 GitHub Issues 报告 bug 或提出功能请求。报告时请包含：

- 您的操作系统和 Python 版本
- 复现步骤
- 预期行为 vs 实际行为
- 相关日志或截图

## 代码审查

所有提交的代码都会经过审查。请注意：

- 审查是建设性的，目的是提高代码质量
- 请积极响应审查意见
- 测试覆盖不足的代码可能不会被接受
