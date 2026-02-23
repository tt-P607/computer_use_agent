"""网络请求工具（基于 aiohttp）"""
from __future__ import annotations

import json
from typing import Annotated, Any, Literal, cast
from urllib.parse import urlparse

import aiohttp

from src.core.components import BaseTool
from src.kernel.logger import get_logger

logger = get_logger("curl_tool")


class CurlTool(BaseTool):
    """HTTP 网络请求工具

    支持 GET、POST、PUT、DELETE 等 HTTP 方法
    """

    tool_name: str = "curl"
    tool_description: str = "发送 HTTP 请求，支持 GET/POST/PUT/DELETE 方法(ps:如果需要搜索请调用web_search工具)"

    async def execute(
        self,
        url: Annotated[str, "请求的 URL 地址"],
        method: Annotated[Literal["GET", "POST", "PUT", "DELETE"], "HTTP 方法"] = "GET",
        headers: Annotated[dict[str, str] | None, "请求头，如: {'Content-Type': 'application/json'}"] = None,
        data: Annotated[dict[str, Any] | str | None, "请求体数据（POST/PUT）"] = None,
        params: Annotated[dict[str, str] | None, "URL 查询参数"] = None,
    ) -> tuple[bool, str | dict[str, Any]]:
        """发送 HTTP 请求

        Args:
            url: 请求的 URL
            method: HTTP 方法
            headers: 请求头
            data: 请求体
            params: URL 参数

        Returns:
            (是否成功, 响应内容或错误信息)
        """
        try:
            # 获取配置
            from ..config import ComputerUseAgentConfig
            
            config = cast(ComputerUseAgentConfig, self.plugin.config)
            timeout_seconds = config.network.timeout
            max_size_mb = config.network.max_response_size_mb
            allowed_schemes = config.network.allowed_schemes

            # URL 验证
            parsed = urlparse(url)
            if parsed.scheme not in allowed_schemes:
                return False, {
                    "error": f"不允许的协议: {parsed.scheme}",
                    "allowed": allowed_schemes
                }

            # 准备请求
            timeout = aiohttp.ClientTimeout(total=timeout_seconds)
            headers = headers or {}
            
            # 如果 data 是字典，转换为 JSON
            if isinstance(data, dict):
                headers["Content-Type"] = headers.get("Content-Type", "application/json")
                json_data = data
                str_data = None
            else:
                json_data = None
                str_data = data

            # 发送请求
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=json_data,
                    data=str_data,
                    params=params,
                ) as response:
                    # 检查响应大小
                    content_length = response.headers.get("Content-Length")
                    if content_length:
                        size_mb = int(content_length) / (1024 * 1024)
                        if size_mb > max_size_mb:
                            return False, {
                                "error": f"响应过大: {size_mb:.2f}MB",
                                "max_size": f"{max_size_mb}MB"
                            }

                    # 读取响应
                    content = await response.text()
                    
                    # 尝试解析为 JSON
                    try:
                        content_json = json.loads(content)
                    except json.JSONDecodeError:
                        content_json = None

                    result = {
                        "status": response.status,
                        "headers": dict(response.headers),
                        "content": content_json if content_json is not None else content,
                        "url": str(response.url),
                    }

                    logger.info(f"HTTP 请求成功: {method} {url} -> {response.status}")
                    return True, result

        except aiohttp.ClientError as e:
            logger.error(f"HTTP 请求失败: {e}")
            return False, {"error": f"网络错误: {str(e)}"}
        except Exception as e:
            logger.error(f"HTTP 请求异常: {e}")
            return False, {"error": str(e)}
