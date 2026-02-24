"""Computer Use Agent - 计算机使用代理"""
from __future__ import annotations

from typing import Annotated, Any, cast

from plugins.computer_use_agent.config import ComputerUseAgentConfig
from plugins.computer_use_agent.tools.download import DownloadTool
from src.core.components import BaseAgent
from src.core.components.types import ChatType
from src.kernel.logger import get_logger

# 导入所有工具
from ..tools import (
    FileCreateTool,
    FileWriteTool,
    FileReadTool,
    CurlTool,
    ScreenshotTool,
    SendMessageTool,
    FinishTaskTool,
    ListDirectoryTool,
)

logger = get_logger("computer_use_agent")


class ComputerUseAgent(BaseAgent):
    """计算机使用 Agent

    提供文件操作、网络请求、截图、消息发送等功能。
    所有文件操作都限制在插件的工作目录内，确保安全性。
    
    可执行的任务包括：
    - 创建、读取、写入文件
    - 发送 HTTP 请求
    - 截取屏幕
    - 发送消息到聊天流
    """

    agent_name: str = "computer_use"
    agent_description: str = (
        "计算机使用助手，可以一次性完成多步骤任务（文件操作、网络请求、截图、发送文件等）。"
        "重要：请将用户的完整需求一次性传入，不要分步/多次调用本agent，这会导致用户的token像雪花般消逝。"
        "例如用户说'下载XX文件并发送给我'，应该将完整需求传入，agent会自动完成下载、保存、发送等所有步骤。"
        "文件操作限制在工作目录内以确保安全。"
    )

    # 允许所有 Chatter 调用
    chatter_allow: list[str] = []
    chat_type: ChatType = ChatType.ALL

    # 关联平台和类型
    associated_platforms: list[str] = []
    associated_types: list[str] = []

    # 依赖和私有工具
    dependencies: list[str] = []
    usables: list[type] = [
        FileCreateTool,
        FileWriteTool,
        FileReadTool,
        CurlTool,
        ScreenshotTool,
        SendMessageTool,
        FinishTaskTool,
        ListDirectoryTool,
        DownloadTool
    ]

    async def execute(
        self,
        task_description: Annotated[str, "任务描述，详细说明需要完成的操作,请将用户的完整需求一次性传入，不要分步调用本agent"],
        **kwargs: Any,
    ) -> tuple[Annotated[bool, "是否成功"], Annotated[str | dict, "返回结果"]]:
        """执行计算机使用任务

        Agent 会根据任务描述，使用可用的工具来完成任务。
        
        Args:
            task_description: 详细的任务描述
            **kwargs: 其他参数

        Returns:
            (是否成功, 结果信息)
        """
        try:
            config = cast(ComputerUseAgentConfig, self.plugin.config)
            workspace_dir = config.security.workspace_directory
            from src.kernel.llm import LLMPayload, ROLE
            from src.kernel.llm.payload import Text
            from src.app.plugin_system.api.llm_api import get_model_set_by_task
            from src.core.config import get_core_config

            logger.info(f"开始执行任务: {task_description}")

            # 获取模型配置
            model_set = get_model_set_by_task("actor")

            # 创建 LLM 请求，注入所有可用工具
            request = self.create_llm_request(
                model_set=model_set,
                request_name="computer_use_task",
                with_usables=True,
            )

            # 构建人设信息
            try:
                core_config = get_core_config()
                personality = core_config.personality
                
                persona_parts = []
                if personality.nickname:
                    persona_parts.append(f"你的名字是 {personality.nickname}")
                if personality.alias_names:
                    persona_parts.append(f"也有人叫你 {'、'.join(personality.alias_names)}")
                if personality.personality_core:
                    persona_parts.append(personality.personality_core)
                if personality.personality_side:
                    persona_parts.append(personality.personality_side)
                if personality.identity:
                    persona_parts.append(personality.identity)
                
                persona_text = "\n".join(persona_parts) if persona_parts else ""
            except Exception as e:
                logger.warning(f"获取人设信息失败: {e}")
                persona_text = ""

            # 添加系统提示和用户任务
            system_prompt_parts = []
            
            if persona_text:
                system_prompt_parts.append(f"# 你的身份\n{persona_text}")
            
            # 列出当前工作目录下的文件
            import os
            try:
                workspace_files = []
                for item in os.listdir(workspace_dir):
                    item_path = os.path.join(workspace_dir, item)
                    if os.path.isdir(item_path):
                        workspace_files.append(f"[目录] {item}/")
                    else:
                        workspace_files.append(f"[文件] {item}")
                
                files_list = "\n".join(workspace_files[:50])  # 限制最多显示50个项目
                if len(workspace_files) > 50:
                    files_list += f"\n... 还有 {len(workspace_files) - 50} 个项目"
            except Exception as e:
                logger.warning(f"列出工作目录文件失败: {e}")
                files_list = "无法列出文件"
            
            system_prompt_parts.append(
                "# 你的能力\n"
                "你是一个计算机使用助手，可以使用各种工具来完成用户的任务。\n"
                f"所有文件操作都限制在工作目录{workspace_dir}内,你现在所处的聊天流是{self.stream_id}。\n\n"
                f"# 当前工作目录内容\n"
                f"工作目录: {workspace_dir}\n"
                f"{files_list}\n\n"
                "# 最高规则\n"
                "1. 按照逻辑顺序执行所有必要的步骤（例如：先用download_file下载文件，再用send_message发送文件）\n"
                "2. **必须检查每个工具的返回值**：工具返回格式为 (success, result)，success=True 表示成功，success=False 表示失败\n"
                "3. **如果任何步骤失败（success=False），必须立即停止后续操作**，分析失败原因并尝试修复，或向用户报告错误\n"
                "4. **严禁在步骤失败后继续执行**，更不能在失败后调用 finish_task 标记成功\n"
                "5. 完成所有操作后，必须调用 finish_task 工具来标记任务完成\n"
                "6. **只有所有步骤都成功（success=True）执行后才能调用 finish_task**\n\n"
                "# 发送消息的正确方式\n"
                "调用 send_message 工具时，如果不提供任何参数（stream_id/group_id/user_id），会自动发送到当前聊天流\n"
                f"当前聊天流 ID: {self.stream_id}\n"
                "示例：\n"
                "  - 发送文本（自动发送到当前流）: send_message(content='任务完成', message_type='text')\n"
                f"  - 发送文本（明确指定）: send_message(content='任务完成', message_type='text', stream_id='{self.stream_id}')\n"
                "  - 发送文件（使用相对路径）: send_message(content='filename.jar', message_type='file')\n"
                "# 下载文件的注意事项\n"
                "1. **download_file 只接受直接下载链接**（文件 URL，不是网页 URL）\n"
                "2. 如果 URL 返回 HTML 页面，工具会拒绝下载并提示错误\n"
                "3. 如果遇到 403 错误或下载到 HTML，说明 URL 不是直链，需要先访问网页找到真正的下载链接\n"
                "4. 真正的下载链接通常以 .exe、.jar、.zip、.apk 等文件扩展名结尾"
            )
            
            request.add_payload(
                LLMPayload(
                    ROLE.SYSTEM,
                    Text("\n\n".join(system_prompt_parts))
                )
            )
            request.add_payload(LLMPayload(ROLE.USER, Text(task_description)))

            # 🔍 调试：输出工具 schemas
            schemas = self.get_local_usable_schemas()
            logger.info(f"📋 可用工具数量: {len(schemas)}")

            # 执行 LLM 请求（带工具调用）
            max_iterations = 20  # 最多20轮工具调用
            max_errors = 5  # 最多允许5次错误
            iteration = 0
            error_count = 0

            while iteration < max_iterations and error_count < max_errors:
                try:
                    response = await request.send(auto_append_response=True,stream=False)
                    
                    if not response:
                        logger.warning("LLM 请求返回空响应，重试...")
                        error_count += 1
                        iteration += 1
                        continue

                    # 获取响应内容
                    message_content = await response
                    logger.info(f"响应内容:{message_content if len(str(message_content)) <= 500 else str(message_content)[:500] + '...'}")
                    
                    # 检查是否有工具调用
                    tool_calls = response.call_list
                    
                    if not tool_calls:
                        # 没有工具调用，但Agent可能还在思考，继续等待
                        logger.warning(f"第{iteration + 1}轮未收到工具调用，Agent响应:{message_content}")
                        # 如果连续多轮都没有工具调用，可能是任务无法完成
                        if iteration >= 3:
                            logger.error("多轮未收到工具调用，任务可能无法完成")
                            return False, {"error": "未能生成有效的工具调用", "response": message_content}
                        iteration += 1
                        continue
                
                except Exception as llm_error:
                    # 捕获 LLM 相关错误（包括 tool_call_compat 解析错误）
                    error_count += 1
                    logger.error(f"LLM 执行出错 ({error_count}/{max_errors}): {llm_error}", exc_info=True)            
                    iteration += 1
                    continue

                logger.info(f"🔧 收到 {len(tool_calls)} 个工具调用")
                
                # 执行工具调用
                task_finished = False
                final_result = None
                
                for idx, tool_call in enumerate(tool_calls, 1):
                    tool_name = tool_call.name
                    tool_args = tool_call.args  # 可能是 dict 或 str
                    tool_id = tool_call.id

                    logger.info(f"📞 [{idx}/{len(tool_calls)}] 调用工具: {tool_name}")
                    logger.info(f"   参数类型: {type(tool_args).__name__}")
                    logger.info(f"   参数内容: {tool_args}")
                    logger.info(f"   Call ID: {tool_id}")

                    try:
                        # 确保 args 是 dict
                        if isinstance(tool_args, str):
                            import json
                            tool_args_dict = json.loads(tool_args)
                        elif isinstance(tool_args, dict):
                            tool_args_dict = tool_args
                        else:
                            tool_args_dict = {}
                        
                        # 如果是 send_message 工具且没有提供目标参数，自动注入当前 stream_id
                        if tool_name in ("send_message", "tool:send_message"):
                            if not any(k in tool_args_dict for k in ("stream_id", "group_id", "user_id")):
                                tool_args_dict["stream_id"] = self.stream_id
                                logger.info(f"   自动注入 stream_id: {self.stream_id}")
                        
                        # 执行工具
                        success, result = await self.execute_local_usable(
                            usable_name=tool_name,
                            **tool_args_dict
                        )

                        logger.info(f"✅ 工具执行结果: 成功={success}, 结果={result}")

                        # 检查是否是 finish_task 工具
                        if tool_name == "finish_task":
                            task_finished = True
                            final_result = result
                            logger.info(f"🎉 任务完成标记已触发: {result}")

                        # 添加工具结果到上下文
                        from src.kernel.llm.payload import ToolResult
                        
                        request.add_payload(
                            LLMPayload(
                                ROLE.TOOL_RESULT,
                                ToolResult(
                                    value=result,
                                    call_id=tool_id
                                )
                            )
                        )

                    except Exception as e:
                        logger.error(f"工具调用失败: {e}", exc_info=True)
                        from src.kernel.llm.payload import ToolResult
                        
                        request.add_payload(
                            LLMPayload(
                                ROLE.TOOL_RESULT,
                                ToolResult(
                                    value=f"错误: {str(e)}",
                                    call_id=tool_id
                                )
                            )
                        )
                
                # 如果任务已完成，返回结果
                if task_finished:
                    logger.info(f"✨ 任务成功完成: {final_result}")
                    return True, final_result if final_result is not None else {"message": "任务已完成"}

                iteration += 1

            # 达到终止条件
            if error_count >= max_errors:
                return False, {"error": f"累计错误次数过多 ({error_count} 次)，任务终止"}
            else:
                return False, {"error": "达到最大工具调用次数，任务未完成"}

        except Exception as e:
            logger.error(f"执行任务失败: {e}", exc_info=True)
            return False, {"error": str(e)}

    async def go_activate(self) -> bool:
        """Agent 激活判定"""
        return True
