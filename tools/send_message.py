"""消息发送工具"""
from __future__ import annotations

import base64
from pathlib import Path
from typing import Annotated, Any, cast

from src.core.components import BaseTool
from src.core.models.message import MessageType
from src.app.plugin_system.api.send_api import send_text, send_image, send_custom
from src.app.plugin_system.api.stream_api import get_or_create_stream
from src.kernel.logger import get_logger
from ..utils import to_wsl_path
from ..config import ComputerUseAgentConfig

logger = get_logger("send_message_tool")


class SendMessageTool(BaseTool):
    """消息发送工具。

    向指定聊天流发送文本、图片、文件等类型的消息。
    文件类媒体内容优先通过 HTTP 文件服务 URL 传递，
    不可用时回退为 base64 编码。
    """

    tool_name: str = "send_message"
    tool_description: str = (
        "向指定的群或好友发送消息（文本、图片、文件等）。"
        "可以提供 group_id（群聊）、user_id（私聊）或 stream_id（聊天流ID）"
        "来指定目标，如果都不提供则发送到当前聊天流。"
    )

    def _get_config(self) -> ComputerUseAgentConfig:
        """获取插件配置（类型转换）。"""
        return cast(ComputerUseAgentConfig, self.plugin.config)

    def _resolve_abs_path(self, config: ComputerUseAgentConfig, relative_or_abs: str) -> Path:
        """将相对路径或绝对路径解析为工作区内的绝对 Path。

        Args:
            config: 插件配置。
            relative_or_abs: 相对或绝对路径字符串。

        Returns:
            解析后的绝对 Path 对象。
        """
        p = Path(relative_or_abs)
        if not p.is_absolute():
            p = Path(config.security.workspace_directory) / relative_or_abs
        return p.resolve()

    def _to_base64_data_uri(self, file_path: Path) -> str:
        """将本地文件读取为 base64:// 格式字符串，供 napcat 使用（回退方案）。

        NapCat NT 内核不支持通过文件路径发送富媒体，必须使用 base64 格式。

        Args:
            file_path: 本地文件绝对路径。

        Returns:
            base64:// 格式的数据字符串。
        """
        data = file_path.read_bytes()
        b64 = base64.b64encode(data).decode("ascii")
        return f"base64://{b64}"

    def _to_http_url(self, config: ComputerUseAgentConfig, file_path: Path) -> str:
        """将工作区内的文件转换为 HTTP URL，供 napcat 拉取。

        要求插件已启动 FileServerRouter，且 config.file_server.base_url 配置正确。

        Args:
            config: 插件配置（用于读取 workspace 和 base_url）。
            file_path: 工作区内的文件绝对路径。

        Returns:
            HTTP URL 字符串。
        """
        workspace = Path(config.security.workspace_directory).resolve()
        rel_posix = file_path.resolve().relative_to(workspace).as_posix()
        return f"{config.file_server.base_url.rstrip('/')}/computer_use_agent/files/{rel_posix}"

    def _resolve_media_content(self, config: ComputerUseAgentConfig, relative_or_abs: str) -> str:
        """将媒体内容解析为可传递给平台适配器的格式。

        处理逻辑：
          1. 已是 URL / base64 则直接透传；
          2. 本地路径 + file_server 已启用：返回 HTTP URL（推荐，无编码开销）；
          3. 本地路径 + file_server 未启用：回退为 base64。

        Args:
            config: 插件配置。
            relative_or_abs: 媒体内容字符串（URL、base64 或相对/绝对路径）。

        Returns:
            可传递给发送 API 的媒体内容字符串。
        """
        if relative_or_abs.startswith(("base64://", "http://", "https://")):
            return relative_or_abs

        abs_path = self._resolve_abs_path(config, relative_or_abs)
        if not abs_path.exists():
            logger.warning(f"媒体文件不存在: {abs_path}")
            return str(abs_path)

        if config.file_server.enable:
            url = self._to_http_url(config, abs_path)
            logger.info(f"文件服务 URL: {url}")
            return url

        # 回退：读取并转为 base64
        logger.info(f"本地文件转 base64: {relative_or_abs!r} ({abs_path.stat().st_size // 1024} KB)")
        return self._to_base64_data_uri(abs_path)

    async def execute(
        self,
        content: Annotated[str, "消息内容（text=文本内容, image=base64编码, file/voice/video=文件路径(相对路径)）"],
        group_id: Annotated[str | None, "【可选】目标群号，发送到群聊时提供此参数"] = None,
        user_id: Annotated[str | None, "【可选】目标好友QQ号，发送到私聊时提供此参数"] = None,
        stream_id: Annotated[str | None, "【可选】目标聊天流ID，如果不提供则发送到当前聊天流"] = None,
        platform: Annotated[str, "平台名称"] = "qq",
        message_type: Annotated[str, "消息类型：text/image/emoji/voice/video/file"] = "text",
    ) -> tuple[bool, str | dict[str, Any]]:
        """发送消息。

        Args:
            content: 消息内容。
            group_id: 目标群号（可选）。
            user_id: 目标好友 QQ 号（可选）。
            stream_id: 目标聊天流 ID（可选）。
            platform: 平台名称。
            message_type: 消息类型。

        Returns:
            (是否成功, 结果信息)
        """
        config = self._get_config()
        try:
            # 解析目标 stream_id
            target_stream_id = stream_id
            if not target_stream_id:
                if group_id or user_id:
                    stream = await get_or_create_stream(
                        platform=platform,
                        user_id=user_id or "",
                        group_id=group_id or "",
                        chat_type="group" if group_id else "private",
                    )
                    target_stream_id = stream.stream_id
                else:
                    return False, {"error": "必须提供 group_id、user_id 或 stream_id 之一"}

            logger.info(f"准备发送消息: {message_type} -> {target_stream_id}")

            # 根据消息类型分发处理
            if message_type == "text":
                success = await send_text(content, target_stream_id, platform)
            elif message_type == "image":
                data = self._resolve_media_content(config, content)
                success = await send_image(data, target_stream_id, platform)
            elif message_type == "file":
                # 文件类型仍使用路径（napcat 支持通过路径发送文件）
                abs_path = self._resolve_abs_path(config, content)
                resolved = to_wsl_path(str(abs_path)) if config.security.wsl_mode else str(abs_path)
                logger.info(f"文件路径解析: {content!r} -> {resolved!r}")
                success = await send_custom(resolved, MessageType.FILE, target_stream_id, platform)
            else:
                # voice/video 等自定义类型
                try:
                    msg_type = MessageType(message_type)
                except ValueError:
                    msg_type = MessageType.UNKNOWN
                if msg_type in (MessageType.VOICE, MessageType.VIDEO):
                    content = self._resolve_media_content(config, content)
                success = await send_custom(content, msg_type, target_stream_id, platform)

            if success:
                target_info = group_id or user_id or target_stream_id
                logger.info(f"发送消息成功: {message_type} -> {target_info}")
                return True, {"message": "消息发送成功", "target": target_info, "type": message_type}

            return False, {"error": "消息发送失败"}

        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            return False, {"error": str(e)}



