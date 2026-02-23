"""文件写入工具"""
from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any, Literal, cast

from src.core.components import BaseTool
from src.kernel.logger import get_logger

logger = get_logger("file_write_tool")


class FileWriteTool(BaseTool):
    """文件写入工具

    向已存在的文件追加或覆盖内容
    """

    tool_name: str = "write_file"
    tool_description: str = "向文件写入内容，支持追加或覆盖模式"

    async def execute(
        self,
        file_path: Annotated[str, "相对于工作目录的文件路径"],
        content: Annotated[str, "要写入的内容"],
        mode: Annotated[Literal["append", "overwrite"], "写入模式：append(追加) 或 overwrite(覆盖)"] = "append",
    ) -> tuple[bool, str | dict[str, Any]]:
        """写入文件

        Args:
            file_path: 相对于工作目录的文件路径
            content: 要写入的内容
            mode: 写入模式（append/overwrite）

        Returns:
            (是否成功, 结果信息)
        """
        try:
            # 获取配置
            from ..config import ComputerUseAgentConfig
            
            config = cast(ComputerUseAgentConfig, self.plugin.config)
            workspace_dir = config.security.workspace_directory
            allowed_extensions = config.security.allowed_file_extensions
            max_size_mb = config.security.max_file_size_mb

            # 构建完整路径
            workspace_path = Path(workspace_dir)
            full_path = (workspace_path / file_path).resolve()

            # 安全检查
            if not str(full_path).startswith(str(workspace_path.resolve())):
                return False, {"error": "路径超出工作目录范围"}

            # 检查文件扩展名
            if allowed_extensions and full_path.suffix not in allowed_extensions:
                return False, {"error": f"不允许的文件类型: {full_path.suffix}"}

            # 检查文件是否存在
            if not full_path.exists():
                return False, {"error": f"文件不存在: {file_path}，请先使用 create_file 创建"}

            # 检查写入后的大小
            current_size = full_path.stat().st_size if mode == "append" else 0
            new_size_mb = (current_size + len(content.encode("utf-8"))) / (1024 * 1024)
            
            if new_size_mb > max_size_mb:
                return False, {
                    "error": f"写入后文件将超过大小限制: {new_size_mb:.2f}MB",
                    "max_size": f"{max_size_mb}MB"
                }

            # 写入文件
            if mode == "overwrite":
                full_path.write_text(content, encoding="utf-8")
                action = "覆盖"
            else:  # append
                with full_path.open("a", encoding="utf-8") as f:
                    f.write(content)
                action = "追加"

            logger.info(f"{action}文件成功: {file_path}")
            return True, {
                "message": f"文件{action}成功",
                "file_path": file_path,
                "size": f"{new_size_mb:.2f}MB",
                "mode": mode
            }

        except Exception as e:
            logger.error(f"写入文件失败: {e}")
            return False, {"error": str(e)}
