"""目录列表工具"""
from __future__ import annotations

from typing import Annotated, Any

from src.core.components import BaseTool
from src.kernel.logger import get_logger
from ..utils import get_workspace, resolve_in_workspace

logger = get_logger("list_directory_tool")


class ListDirectoryTool(BaseTool):
    """目录列表工具

    列出工作目录中的文件和子目录
    """

    tool_name: str = "list_directory"
    tool_description: str = "列出指定目录中的文件和子目录"

    async def execute(
        self,
        directory_path: Annotated[str, "相对于工作目录的路径，留空表示根目录"] = "",
        show_hidden: Annotated[bool, "是否显示隐藏文件"] = False,
        max_items: Annotated[int, "最多返回的项目数，0 表示无限制"] = 100,
    ) -> tuple[bool, str | dict[str, Any]]:
        """列出目录内容

        Args:
            directory_path: 相对于工作目录的路径
            show_hidden: 是否显示隐藏文件
            max_items: 最多返回的项目数（0=无限制）

        Returns:
            (是否成功, 目录内容或错误信息)
        """
        try:
            # 获取工作区目录
            workspace = get_workspace(self.plugin)

            # 解析目标目录（含沙盒安全检查）
            if directory_path:
                try:
                    full_path = resolve_in_workspace(workspace, directory_path)
                except ValueError as e:
                    return False, {"error": str(e)}
            else:
                full_path = workspace

            # 检查目录是否存在
            if not full_path.exists():
                return False, {"error": f"目录不存在: {directory_path or '/'}"}

            if not full_path.is_dir():
                return False, {"error": f"{directory_path or '/'} 不是一个目录"}

            # 列出目录内容
            items = []
            count = 0
            
            for item in sorted(full_path.iterdir()):
                # 过滤隐藏文件
                if not show_hidden and item.name.startswith('.'):
                    continue
                
                # 限制数量
                if max_items > 0 and count >= max_items:
                    break
                
                # 获取项目信息
                item_info = {
                    "name": item.name,
                    "type": "directory" if item.is_dir() else "file",
                    "path": str(item.relative_to(workspace))
                }
                
                # 如果是文件，添加额外信息
                if item.is_file():
                    try:
                        size_bytes = item.stat().st_size
                        item_info["size"] = self._format_size(size_bytes)
                        item_info["extension"] = item.suffix
                    except Exception:
                        pass
                
                items.append(item_info)
                count += 1

            # 统计信息
            total_dirs = sum(1 for item in items if item["type"] == "directory")
            total_files = sum(1 for item in items if item["type"] == "file")
            
            logger.info(f"列出目录成功: {directory_path or '/'} ({total_files} 文件, {total_dirs} 目录)")
            
            result = {
                "directory": directory_path or "/",
                "items": items,
                "total_items": len(items),
                "files": total_files,
                "directories": total_dirs,
            }
            
            # 如果有更多项目被截断，添加提示
            if max_items > 0 and count >= max_items:
                result["truncated"] = True
                result["message"] = f"仅显示前 {max_items} 项"
            
            return True, result

        except Exception as e:
            logger.error(f"列出目录失败: {e}")
            return False, {"error": str(e)}

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """格式化文件大小"""
        if size_bytes < 1024:
            return f"{size_bytes}B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.2f}KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.2f}MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f}GB"
