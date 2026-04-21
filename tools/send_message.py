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
        "向指定的群或好友发送多媒体消息（图片、文件、语音等）。"
        "【警告】此工具严禁发送普通纯文本消息！你只是底层执行组件，人类对话应留给上层系统。"
        "发送的内容(content)必须是真实存在的本地文件路径（截图等）或有效的URL。"
        "可以提供 group_id（群聊）、user_id（私聊）或 stream_id（聊天流ID）来指定目标，如果都不提供则发送到当前聊天流。"
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
            raise FileNotFoundError(f"媒体文件不存在，请检查路径是否正确: {abs_path}")

        if config.file_server.enable:
            url = self._to_http_url(config, abs_path)
            logger.info(f"文件服务 URL: {url}")
            return url

        # 回退：读取并转为 base64
        logger.info(f"本地文件转 base64: {relative_or_abs!r} ({abs_path.stat().st_size // 1024} KB)")
        return self._to_base64_data_uri(abs_path)

    async def execute(
        self,
        content: Annotated[str, "消息内容（文本内容，或文件相对路径/绝对路径/URL）"],
        group_id: Annotated[str | None, "【可选】目标群号，发送到群聊时提供此参数"] = None,
        user_id: Annotated[str | None, "【可选】目标好友QQ号，发送到私聊时提供此参数"] = None,
        stream_id: Annotated[str | None, "【可选】目标聊天流ID，如果不提供则发送到当前聊天流"] = None,
        platform: Annotated[str, "平台名称"] = "qq",
        message_type: Annotated[str, "消息类型：auto(自动推断)/text/image/emoji/voice/video/file"] = "auto",
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
            # 过滤掉 LLM 可能填入的任意非法占位符：
            #   stream_id 须为 64 位 hex；group_id/user_id 须为纯数字
            _stream = str(stream_id or "")
            _group = str(group_id or "")
            _user = str(user_id or "")
            _stream_valid = len(_stream) == 64 and all(c in "0123456789abcdefABCDEF" for c in _stream)
            _group_valid = _group.isdigit()
            _user_valid = _user.isdigit()

            target_stream_id = _stream if _stream_valid else None
            group_id = _group if _group_valid else None
            user_id = _user if _user_valid else None

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
                    return False, {"error": "必须提供有效的 group_id（纯数字）、user_id（纯数字）或 stream_id（64位hex）之一"}

            logger.info(f"准备发送消息: {message_type} -> {target_stream_id}")

            # 自动推断消息类型
            if message_type == "auto":
                try:
                    # 先判断是否为 URL 等格式
                    if content.startswith(("http://", "https://", "base64://")):
                        message_type = "image" # 简化处理，默认 URL 是图片
                    else:
                        test_path = self._resolve_abs_path(config, content)
                        if test_path.exists():
                            ext = test_path.suffix.lower()
                            if ext in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}:
                                message_type = "image"
                            elif ext in {".mp4", ".avi", ".mkv", ".mov"}:
                                message_type = "video"
                            elif ext in {".mp3", ".wav", ".ogg", ".silk", ".slk", ".amr"}:
                                message_type = "voice"
                            else:
                                message_type = "file"
                            logger.info(f"自动推断消息类型为: {message_type}")
                        else:
                            message_type = "text"
                except Exception:
                    message_type = "text"

            # 根据消息类型分发处理
            if message_type == "text":
                return False, {"error": "权限被拒绝：你不能发送普通文本消息。此Agent没有说话的权利，仅用于底层执行。语言交流请交给上层主角色处理。你只被允许通过此工具发送文件、图片(image)等多媒体内容。如果要发送截图，请确保传入真实且存在的绝对/相对路径。"}
            elif message_type == "image":
                data = self._resolve_media_content(config, content)
                success = await send_image(data, target_stream_id, platform)
            elif message_type == "file":
                # 文件类型仍使用路径（napcat 支持通过路径发送文件）
                abs_path = self._resolve_abs_path(config, content)
                if not abs_path.exists():
                    raise FileNotFoundError(f"发送的文件不存在，请检查路径是否正确: {abs_path}")
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



