"""文件读取工具"""
from __future__ import annotations

from typing import Annotated, Any, cast

from src.core.components import BaseTool
from src.kernel.logger import get_logger
from ..utils import get_workspace, resolve_in_workspace

logger = get_logger("file_read_tool")


class FileReadTool(BaseTool):
    """文件读取工具

    读取工作目录中的文件内容
    """

    tool_name: str = "read_file"
    tool_description: str = "读取工作目录中的文件内容"

    async def execute(
        self,
        file_path: Annotated[str, "相对于工作目录的文件路径"],
        max_lines: Annotated[int, "最多读取的行数，0 表示读取全部"] = 0,
    ) -> tuple[bool, str | dict[str, Any]]:
        """读取文件

        Args:
            file_path: 相对于工作目录的文件路径
            max_lines: 最多读取的行数（0=全部）

        Returns:
            (是否成功, 文件内容或错误信息)
        """
        try:
            from ..config import ComputerUseAgentConfig

            config = cast(ComputerUseAgentConfig, self.plugin.config)
            allowed_extensions = config.security.allowed_file_extensions

            # 获取工作区目录并解析目标路径（同时执行沙盒安全检查）
            workspace = get_workspace(self.plugin)
            try:
                full_path = resolve_in_workspace(workspace, file_path)
            except ValueError as e:
                return False, {"error": str(e)}

            # 检查文件扩展名
            if allowed_extensions and full_path.suffix not in allowed_extensions:
                return False, {"error": f"不允许读取该文件类型: {full_path.suffix}"}

            # 检查文件是否存在
            if not full_path.exists():
                return False, {"error": f"文件不存在: {file_path}"}

            if not full_path.is_file():
                return False, {"error": f"{file_path} 不是一个文件"}

            # 读取文件
            content = full_path.read_text(encoding="utf-8")
            
            # 限制行数
            if max_lines > 0:
                lines = content.split("\n")
                if len(lines) > max_lines:
                    content = "\n".join(lines[:max_lines])
                    content += f"\n...(省略剩余 {len(lines) - max_lines} 行)"

            logger.info(f"读取文件成功: {file_path}")
            return True, {
                "file_path": file_path,
                "content": content,
                "size": f"{len(content.encode('utf-8')) / 1024:.2f}KB"
            }

        except Exception as e:
            logger.error(f"读取文件失败: {e}")
            return False, {"error": str(e)}
