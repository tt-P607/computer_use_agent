"""任务完成工具"""
from __future__ import annotations

from typing import Annotated, Any

from src.core.components import BaseTool
from src.kernel.logger import get_logger

logger = get_logger("finish_task_tool")


class FinishTaskTool(BaseTool):
    """任务完成工具

    当所有操作都完成后，使用此工具标记任务完成并返回最终结果
    """

    tool_name: str = "finish_task"
    tool_description: str = "标记任务完成并返回最终结果。只有在所有步骤都执行完毕后才调用此工具。"

    async def execute(
        self,
        result: Annotated[str, "任务执行的最终结果描述"],
        success: Annotated[bool, "任务是否成功完成"] = True,
    ) -> tuple[bool, str | dict[str, Any]]:
        """标记任务完成

        Args:
            result: 任务执行的最终结果描述
            success: 任务是否成功完成

        Returns:
            (是否成功, 结果信息)
        """
        logger.info(f"任务完成标记: 成功={success}, 结果={result}")
        
        return True, {
            "task_finished": True,
            "success": success,
            "result": result,
        }
