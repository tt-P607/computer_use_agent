"""Computer Use Agent - 计算机使用代理"""
from __future__ import annotations

import json
from typing import Annotated, Any, cast

from src.core.components import BaseAgent
from src.core.components.types import ChatType
from src.kernel.llm import LLMPayload, ROLE
from src.kernel.llm.payload import Text, ToolResult
from src.kernel.logger import get_logger

from ..config import ComputerUseAgentConfig
from ..tools import (
    CurlTool,
    DownloadTool,
    FileCreateTool,
    FileReadTool,
    FileWriteTool,
    FinishTaskTool,
    ListDirectoryTool,
    ScreenshotTool,
    SendMessageTool,
    WebSearchTool,
)
from .prompts import build_system_prompt

logger = get_logger("computer_use_agent")


class ComputerUseAgent(BaseAgent):
    """计算机使用 Agent。

    提供文件操作、网络请求、截图、消息发送等功能。
    所有文件操作都限制在插件工作目录内，确保安全性。

    支持的任务示例：
    - 创建、读取、写入文件
    - 发送 HTTP 请求 / 下载文件
    - 截取屏幕
    - 发送消息/文件到聊天流
    """

    agent_name: str = "computer_use"
    agent_description: str = (
        "计算机使用助手，可一次性完成多步骤任务（文件操作、网络请求、截图、发送文件等）。"
        "请将用户的完整需求一次性传入，不要分步/多次调用，避免重复消耗 token。"
        "例如：'下载 XX 文件并发送给我'，agent 会自动完成下载、保存、发送等所有步骤。"
    )

    chatter_allow: list[str] = []
    chat_type: ChatType = ChatType.ALL

    associated_platforms: list[str] = []
    associated_types: list[str] = []

    dependencies: list[str] = []
    usables: list[type] = [
        FileCreateTool,
        FileWriteTool,
        FileReadTool,
        ListDirectoryTool,
        CurlTool,
        DownloadTool,
        ScreenshotTool,
        SendMessageTool,
        FinishTaskTool,
        WebSearchTool,   # 修复遗漏：补充 WebSearchTool
    ]

    async def execute(
        self,
        task_description: Annotated[
            str,
            "任务描述，请将用户的完整需求一次性传入，不要分步调用本 agent",
        ],
        **kwargs: Any,
    ) -> tuple[Annotated[bool, "是否成功"], Annotated[str | dict, "返回结果"]]:
        """执行计算机使用任务。

        Agent 会根据任务描述，编排可用工具逐步完成任务。

        Args:
            task_description: 详细的任务描述。
            **kwargs: 保留参数，暂不使用。

        Returns:
            (是否成功, 结果信息)
        """
        try:
            from src.app.plugin_system.api.llm_api import get_model_set_by_name, get_model_set_by_task

            config = cast(ComputerUseAgentConfig, self.plugin.config)
            workspace_dir = config.security.workspace_directory

            logger.info(f"开始执行任务: {task_description}")

            # 获取模型配置：优先使用配置中指定的具体模型名，回退到任务组 actor
            model_cfg = config.model
            if model_cfg.model_name:
                model_set = get_model_set_by_name(
                    model_cfg.model_name,
                    temperature=model_cfg.temperature,
                    max_tokens=model_cfg.max_tokens,
                )
                logger.info(f"使用模型: {model_cfg.model_name}")
            else:
                model_set = get_model_set_by_task("actor")
                logger.info("使用任务组模型: actor")
            request = self.create_llm_request(
                model_set=model_set,
                request_name="computer_use_task",
                with_usables=True,
            )

            # 注入系统提示词与用户任务
            system_prompt = build_system_prompt(
                workspace_dir,
                custom_instructions=config.prompt.custom_instructions,
            )
            request.add_payload(LLMPayload(ROLE.SYSTEM, Text(system_prompt)))
            request.add_payload(LLMPayload(ROLE.USER, Text(task_description)))

            logger.info(f"📋 可用工具数量: {len(self.get_local_usable_schemas())}")

            return await self._run_tool_loop(request)

        except Exception as e:
            logger.error(f"执行任务失败: {e}", exc_info=True)
            return False, {"error": str(e)}

    async def _run_tool_loop(
        self, request: Any
    ) -> tuple[bool, str | dict]:
        """执行多轮 LLM + 工具调用循环，直到任务完成或触发退出条件。

        Args:
            request: 已注入系统提示词和用户任务的 LLMRequest 对象。

        Returns:
            (是否成功, 结果信息)
        """
        max_iterations = 20    # 最多 20 轮 LLM 交互
        max_errors = 5         # 累计 LLM/解析错误上限
        max_no_tool = 3        # 连续无工具调用容忍轮数

        iteration = 0
        error_count = 0
        no_tool_count = 0

        while iteration < max_iterations and error_count < max_errors:
            # ── 发起 LLM 请求 ──
            try:
                response = await request.send(auto_append_response=True, stream=False)
            except Exception as llm_error:
                error_count += 1
                logger.error(
                    f"LLM 请求异常（{error_count}/{max_errors}）: {llm_error}",
                    exc_info=True,
                )
                iteration += 1
                continue

            if not response:
                error_count += 1
                logger.warning(f"LLM 返回空响应，跳过（{error_count}/{max_errors}）")
                iteration += 1
                continue

            # 获取响应内容，并将 response.payloads（含 ASSISTANT 消息）同步回
            # request，避免追加 TOOL_RESULT 时出现"孤立 tool_result"校验错误。
            try:
                message_content = await response
            except Exception as e:
                error_count += 1
                logger.error(f"解析响应失败（{error_count}/{max_errors}）: {e}", exc_info=True)
                iteration += 1
                continue

            log_preview = str(message_content)
            logger.info(
                f"[轮次 {iteration + 1}] 响应: "
                f"{log_preview[:500]}{'...' if len(log_preview) > 500 else ''}"
            )

            request.payloads = response.payloads

            # ── 检查工具调用 ──
            tool_calls = response.call_list
            if not tool_calls:
                no_tool_count += 1
                logger.warning(
                    f"[轮次 {iteration + 1}] 未收到工具调用"
                    f"（{no_tool_count}/{max_no_tool}）"
                )
                if no_tool_count >= max_no_tool:
                    logger.error("连续多轮无工具调用，任务无法继续")
                    return False, {
                        "error": "多轮无工具调用，任务无法完成",
                        "last_response": message_content,
                    }
                iteration += 1
                continue

            # 有工具调用，重置无工具计数
            no_tool_count = 0
            logger.info(f"[轮次 {iteration + 1}] 收到 {len(tool_calls)} 个工具调用")

            # ── 执行工具调用 ──
            task_finished, final_result = await self._execute_tool_calls(
                request, tool_calls
            )
            if task_finished:
                logger.info(f"✨ 任务成功完成: {final_result}")
                return True, final_result if final_result is not None else {"message": "任务已完成"}

            iteration += 1

        # ── 退出条件处理 ──
        if error_count >= max_errors:
            return False, {"error": f"累计错误次数过多（{error_count} 次），任务终止"}
        return False, {"error": f"达到最大交互轮次（{max_iterations}），任务未完成"}

    async def _execute_tool_calls(
        self,
        request: Any,
        tool_calls: list[Any],
    ) -> tuple[bool, str | dict | None]:
        """执行本轮所有工具调用，并将结果追加到 request.payloads。

        若触发 finish_task 工具，立即返回并携带最终结果。

        Args:
            request: 当前 LLMRequest 对象（用于追加 TOOL_RESULT payload）。
            tool_calls: LLM 返回的工具调用列表。

        Returns:
            (是否触发 finish_task, 最终结果或 None)
        """
        for idx, tool_call in enumerate(tool_calls, 1):
            tool_name: str = tool_call.name
            tool_args = tool_call.args
            tool_id: str = tool_call.id

            logger.info(
                f"  [{idx}/{len(tool_calls)}] 调用工具: {tool_name}，"
                f"参数: {tool_args!r}"
            )

            # 将 args 统一为 dict
            if isinstance(tool_args, str):
                try:
                    tool_args_dict: dict[str, Any] = json.loads(tool_args)
                except json.JSONDecodeError:
                    tool_args_dict = {}
            elif isinstance(tool_args, dict):
                tool_args_dict = tool_args
            else:
                tool_args_dict = {}

            # send_message：若未指定有效目标，自动注入当前 stream_id
            if "send_message" in tool_name:
                # stream_id 必须是 64 位 hex 字符串才视为有效
                stream_val = str(tool_args_dict.get("stream_id") or "")
                stream_valid = len(stream_val) == 64 and all(c in "0123456789abcdefABCDEF" for c in stream_val)
                # group_id / user_id 必须是纯数字字符串才视为有效
                group_val = str(tool_args_dict.get("group_id") or "")
                user_val = str(tool_args_dict.get("user_id") or "")
                group_valid = group_val.isdigit()
                user_valid = user_val.isdigit()
                if not stream_valid and not group_valid and not user_valid:
                    tool_args_dict["stream_id"] = self.stream_id
                    tool_args_dict.pop("group_id", None)
                    tool_args_dict.pop("user_id", None)
                    logger.info(f"    自动注入 stream_id: {self.stream_id}")

            # 执行工具（execute_local_usable 内部已通过 _strip_usable_prefix 处理别名）
            try:
                success, result = await self.execute_local_usable(
                    usable_name=tool_name, **tool_args_dict
                )
                logger.info(f"    结果: 成功={success}, 内容={result!r}")
            except Exception as e:
                logger.error(f"    工具执行异常: {e}", exc_info=True)
                success, result = False, f"工具执行出错: {e}"

            # 将工具结果追加到上下文
            request.add_payload(
                LLMPayload(
                    ROLE.TOOL_RESULT,
                    ToolResult(value=result, call_id=tool_id),
                )
            )

            # 检测 finish_task（兼容带前缀的 schema 名）
            if "finish_task" in tool_name:
                return True, result

        return False, None

    async def go_activate(self) -> bool:
        """Agent 激活判定，默认始终可用。"""
        return True
