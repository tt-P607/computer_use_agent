"""文件创建工具"""
from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any, cast

from src.core.components import BaseTool
from src.kernel.logger import get_logger

logger = get_logger("file_create_tool")


class FileCreateTool(BaseTool):
    """创建文件工具

    在工作目录中创建新文件（包括目录结构）
    """

    tool_name: str = "create_file"
    tool_description: str = "在工作目录中创建新文件，如果目录不存在会自动创建"

    async def execute(
        self,
        file_path: Annotated[str, "相对于工作目录的文件路径，如: 'notes/memo.txt'"],
        content: Annotated[str, "文件初始内容"] = "",
    ) -> tuple[bool, str | dict[str, Any]]:
        """创建文件

        Args:
            file_path: 相对于工作目录的文件路径
            content: 文件初始内容

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
            enable_dir_creation = config.security.enable_directory_creation

            # 构建完整路径
            workspace_path = Path(workspace_dir)
            full_path = (workspace_path / file_path).resolve()

            # 安全检查：确保路径在工作目录内
            if not str(full_path).startswith(str(workspace_path.resolve())):
                return False, {"error": "路径超出工作目录范围，操作被拒绝"}

            # 检查文件扩展名
            if allowed_extensions and full_path.suffix not in allowed_extensions:
                return False, {
                    "error": f"不允许的文件类型: {full_path.suffix}",
                    "allowed": allowed_extensions
                }

            # 检查文件大小
            content_size_mb = len(content.encode("utf-8")) / (1024 * 1024)
            if content_size_mb > max_size_mb:
                return False, {
                    "error": f"文件内容过大: {content_size_mb:.2f}MB",
                    "max_size": f"{max_size_mb}MB"
                }

            # 检查文件是否已存在
            if full_path.exists():
                return False, {"error": f"文件已存在: {file_path}"}

            # 创建目录
            if not enable_dir_creation and not full_path.parent.exists():
                return False, {"error": "不允许创建目录"}

            full_path.parent.mkdir(parents=True, exist_ok=True)

            # 创建文件
            full_path.write_text(content, encoding="utf-8")

            logger.info(f"创建文件成功: {file_path}")
            return True, {
                "message": "文件创建成功",
                "file_path": file_path,
                "size": f"{content_size_mb:.2f}MB"
            }

        except Exception as e:
            logger.error(f"创建文件失败: {e}")
            return False, {"error": str(e)}
