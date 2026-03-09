"""工作区文件服务路由。

为工作区目录提供 HTTP 静态文件服务，使 napcat 等外部进程可通过 URL 直接拉取
截图、下载产物等文件，避免 base64 编码开销和文件路径兼容性问题。

路由挂载前缀：/computer_use_agent/files
访问示例：GET /computer_use_agent/files/screenshots/xxx.png
"""
from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import cast, TYPE_CHECKING

from fastapi import HTTPException
from fastapi.responses import FileResponse

from src.core.components.base.router import BaseRouter
from src.kernel.logger import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger("cua_file_server")


class FileServerRouter(BaseRouter):
    """工作区文件服务路由。

    将 workspace_directory 内的文件通过 HTTP 暴露出来，
    供 napcat 等外部进程通过 URL 访问（无需 base64 或挂载路径）。

    端点：
        GET /computer_use_agent/files/{path:path}
    """

    router_name: str = "file_server"
    router_description: str = "Computer Use Agent 工作区文件服务"
    custom_route_path: str = "/computer_use_agent/files"
    cors_origins: list[str] = ["*"]

    def register_endpoints(self) -> None:
        """注册文件服务端点。"""

        @self.app.get("/{file_path:path}")
        async def serve_file(file_path: str) -> FileResponse:
            """提供工作区内任意文件的下载。

            Args:
                file_path: 相对于 workspace_directory 的路径

            Returns:
                文件响应

            Raises:
                HTTPException 403: 路径越界
                HTTPException 404: 文件不存在
            """
            from ..config import ComputerUseAgentConfig

            config = cast(ComputerUseAgentConfig, self.plugin.config)
            workspace = Path(config.security.workspace_directory).resolve()

            # 解析并做沙盒检查：使用 is_relative_to 比字符串字头比较更准确，
            # 防止 Windows 大小写异常导致的越界问题。
            target = (workspace / file_path).resolve()
            if not target.is_relative_to(workspace):
                logger.warning(f"文件服务：越界访问被拒绝: {file_path!r}")
                raise HTTPException(status_code=403, detail="路径越界，访问被拒绝")

            if not target.exists() or not target.is_file():
                raise HTTPException(status_code=404, detail=f"文件不存在: {file_path}")

            media_type, _ = mimetypes.guess_type(str(target))
            logger.debug(f"文件服务：提供文件 {target.name} ({target.stat().st_size // 1024} KB)")
            return FileResponse(
                path=str(target),
                media_type=media_type or "application/octet-stream",
                filename=target.name,
            )
