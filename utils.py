"""Computer Use Agent 工具函数

提供公共路径处理与配置访问辅助，供工具类和 Agent 复用。
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.components.base.plugin import BasePlugin


def to_wsl_path(windows_path: str) -> str:
    """将 Windows 绝对路径转换为 WSL 挂载路径。

    例如：``E:\\foo\\bar.png`` → ``/mnt/e/foo/bar.png``

    Args:
        windows_path: Windows 格式的绝对路径字符串。

    Returns:
        WSL 格式的绝对路径字符串；若传入路径不含盘符则原样返回。
    """
    path = Path(windows_path)
    drive = path.drive  # 例如 'E:'
    if not drive:
        # 不是带盘符的绝对路径，无法转换，原样返回
        return windows_path

    drive_letter = drive[0].lower()  # 'e'
    # path.as_posix() 形如 'E:/foo/bar.png'，去掉盘符部分再拼 /mnt/x
    posix = path.as_posix()
    rest = posix[len(drive):]  # '/foo/bar.png'
    return f"/mnt/{drive_letter}{rest}"


def get_workspace(plugin: "BasePlugin") -> Path:
    """从插件配置中获取工作区目录的绝对 Path 对象。

    Args:
        plugin: 插件实例，其 config 应为 ComputerUseAgentConfig。

    Returns:
        工作区目录的已 resolve 绝对 Path 对象。
    """
    from typing import cast
    from .config import ComputerUseAgentConfig

    config = cast(ComputerUseAgentConfig, plugin.config)
    return Path(config.security.workspace_directory).resolve()


def resolve_in_workspace(workspace: Path, relative_path: str) -> Path:
    """将相对路径解析为工作区内的绝对路径，并执行沙盒安全检查。

    使用 Path.is_relative_to()（Python 3.9+）进行路径比较，
    比字符串 startswith 更准确，不受大小写与尾部斜杠影响。

    Args:
        workspace: 工作区根目录（已 resolve 的绝对 Path）。
        relative_path: 相对于工作区的路径字符串。

    Returns:
        解析后的绝对 Path 对象。

    Raises:
        ValueError: 若解析后的路径越出工作区范围（沙盒违规）。
    """
    full = (workspace / relative_path).resolve()
    if not full.is_relative_to(workspace):
        raise ValueError(f"路径越出工作目录范围（沙盒违规）: {relative_path!r}")
    return full
