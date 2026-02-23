"""消息发送工具"""
from __future__ import annotations

from typing import Annotated, Any

from src.core.components import BaseTool
from src.core.models.message import MessageType
from src.app.plugin_system.api.send_api import send_text, send_image, send_custom
from src.app.plugin_system.api.stream_api import get_or_create_stream
from src.kernel.logger import get_logger

logger = get_logger("send_message_tool")


class SendMessageTool(BaseTool):
    """消息发送工具

    发送文本、图片等类型的消息到指定聊天流
    """

    tool_name: str = "send_message"
    tool_description: str = "向指定的群或好友发送消息（文本、图片、文件等）。必须提供 group_id（群聊）、user_id（私聊）或 stream_id（聊天流ID）之一作为发送目标"

    async def execute(
        self,
        content: Annotated[str, "消息内容（text=文本内容, image=base64编码, file/voice/video=文件路径(绝对路径)）"],
        group_id: Annotated[str | None, "【必填其一】目标群号，发送到群聊时必须提供此参数"] = None,
        user_id: Annotated[str | None, "【必填其一】目标好友QQ号，发送到私聊时必须提供此参数"] = None,
        stream_id: Annotated[str | None, "【必填其一】目标聊天流ID（高级用法，通常使用 group_id 或 user_id）"] = None,
        platform: Annotated[str, "平台名称"] = "qq",
        message_type: Annotated[str, "消息类型：text/image/emoji/voice/video/file"] = "text",
    ) -> tuple[bool, str | dict[str, Any]]:
        """发送消息

        Args:
            content: 消息内容（text=文本内容, image=base64编码, file/voice/video=文件路径(绝对路径)）
            group_id: 【必填其一】目标群号，发送到群聊时必须提供
            user_id: 【必填其一】目标好友QQ号，发送到私聊时必须提供
            stream_id: 【必填其一】目标聊天流ID（高级用法，通常使用 group_id 或 user_id）
            platform: 平台名称
            message_type: 消息类型

        Returns:
            (是否成功, 结果信息)
        """
        try:
            # 获取目标 stream_id
            target_stream_id = stream_id
            
            if not target_stream_id:
                # 如果没有直接提供 stream_id，则通过 group_id 或 user_id 获取
                if group_id or user_id:
                    # 通过 group_id 或 user_id 获取或创建流
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

            # 根据类型发送消息
            if message_type == "text":
                success = await send_text(content, target_stream_id, platform)
            elif message_type == "image":
                success = await send_image(content, target_stream_id, platform)
            else:
                # 使用自定义类型
                try:
                    msg_type = MessageType(message_type)
                except ValueError:
                    msg_type = MessageType.UNKNOWN
                success = await send_custom(content, msg_type, target_stream_id, platform)

            if success:
                target_info = group_id or user_id or target_stream_id
                logger.info(f"发送消息成功: {message_type} -> {target_info}")
                return True, {
                    "message": "消息发送成功",
                    "target": target_info,
                    "type": message_type
                }
            else:
                return False, {"error": "消息发送失败"}

        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            return False, {"error": str(e)}
