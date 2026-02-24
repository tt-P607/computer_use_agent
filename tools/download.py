"""文件下载工具（基于 aiohttp）"""
from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any, cast
from urllib.parse import urlparse

import aiohttp

from src.core.components import BaseTool
from src.kernel.logger import get_logger

logger = get_logger("download_tool")


class DownloadTool(BaseTool):
    """文件下载工具

    从 URL 下载文件到本地指定路径
    """

    tool_name: str = "download_file"
    tool_description: str = "从直链 URL 下载文件到本地（URL 必须是直接下载链接，不支持需要登录或跳转的地址）"

    async def execute(
        self,
        url: Annotated[str, "文件的直链 URL 地址（必须是可以直接下载的链接）"],
        save_path: Annotated[str, "保存文件的本地路径(相对于工作区路径)（含文件名）"],
        overwrite: Annotated[bool, "是否覆盖已存在的文件"] = False,
    ) -> tuple[bool, str | dict[str, Any]]:
        """下载文件

        Args:
            url: 文件直链 URL（必须是直接下载链接）
            save_path: 保存路径
            overwrite: 是否覆盖已存在的文件

        Returns:
            (是否成功, 结果信息或错误信息)
        """
        try:
            # 获取配置
            from ..config import ComputerUseAgentConfig

            config = cast(ComputerUseAgentConfig, self.plugin.config)
            timeout_seconds = config.network.timeout
            max_size_mb = config.network.max_response_size_mb
            allowed_schemes = config.network.allowed_schemes
            workspace = config.security.workspace_directory

            # URL 验证
            parsed = urlparse(url)
            if parsed.scheme not in allowed_schemes:
                return False, {
                    "error": f"不允许的协议: {parsed.scheme}",
                    "allowed": allowed_schemes
                }

            # 路径处理
            save_path_obj = Path(workspace) / save_path

            # 检查文件是否存在
            if save_path_obj.exists() and not overwrite:
                return False, {
                    "error": "文件已存在",
                    "path": str(save_path_obj.absolute()),
                    "hint": "设置 overwrite=True 以覆盖"
                }

            # 确保目录存在
            save_path_obj.parent.mkdir(parents=True, exist_ok=True)

            # 下载文件
            timeout = aiohttp.ClientTimeout(total=timeout_seconds)

            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    # 检查响应状态
                    if response.status != 200:
                        return False, {
                            "error": f"HTTP 错误: {response.status}",
                            "url": url,
                            "hint": "请确认 URL 是直接下载链接"
                        }

                    # 检查 Content-Type，防止下载 HTML 页面
                    content_type = response.headers.get("Content-Type", "").lower()
                    if "text/html" in content_type or "application/xhtml" in content_type:
                        return False, {
                            "error": "URL 返回的是网页而不是文件",
                            "content_type": content_type,
                            "hint": "这不是直接下载链接，请找到真正的文件下载 URL（通常是 .exe、.jar、.zip 等文件的直链）"
                        }

                    # 检查文件大小
                    content_length = response.headers.get("Content-Length")
                    if content_length:
                        size_mb = int(content_length) / (1024 * 1024)
                        if size_mb > max_size_mb:
                            return False, {
                                "error": f"文件过大: {size_mb:.2f}MB",
                                "max_size": f"{max_size_mb}MB"
                            }

                    # 流式写入文件
                    total_size = 0
                    with open(save_path_obj, "wb") as f:
                        async for chunk in response.content.iter_chunked(8192):
                            f.write(chunk)
                            total_size += len(chunk)

                            # 动态检查大小
                            if total_size > max_size_mb * 1024 * 1024:
                                # 删除部分下载的文件
                                f.close()
                                save_path_obj.unlink()
                                return False, {
                                    "error": f"文件超过大小限制: {max_size_mb}MB"
                                }

                    result = {
                        "success": True,
                        "path": str(save_path_obj.absolute()),
                        "size": total_size,
                        "size_mb": f"{total_size / (1024 * 1024):.2f}MB",
                        "url": url
                    }

                    logger.info(f"文件下载成功: {url} -> {save_path_obj}")
                    return True, result

        except aiohttp.ClientError as e:
            logger.error(f"下载失败: {e}")
            return False, {"error": f"网络错误: {str(e)}"}
        except OSError as e:
            logger.error(f"文件操作失败: {e}")
            return False, {"error": f"文件操作错误: {str(e)}"}
        except Exception as e:
            logger.error(f"下载异常: {e}")
            return False, {"error": str(e)}
