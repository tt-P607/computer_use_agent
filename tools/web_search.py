"""联网搜索工具"""
from __future__ import annotations

from typing import Annotated, Any

from src.core.components import BaseTool
from src.kernel.logger import get_logger

logger = get_logger("web_search_tool")


class WebSearchTool(BaseTool):
    """联网搜索工具

    通过多种搜索引擎进行联网搜索，获取最新信息
    """

    tool_name: str = "web_search"
    tool_description: str = "联网搜索工具，用于搜索互联网信息。支持多种搜索引擎（DDG、Bing、Tavily、Exa等）和搜索策略"

    async def execute(
        self,
        query: Annotated[str, "搜索查询内容，要搜索的关键词或问题"],
        num_results: Annotated[int, "返回结果数量，默认5条"] = 5,
        time_range: Annotated[str, "时间范围：'any'(任何时间)、'week'(一周内)、'month'(一个月内)"] = "any",
        engine: Annotated[str | None, "指定搜索引擎：ddg/bing/tavily/exa/searxng/metaso/serper，不指定则使用默认引擎"] = None,
        strategy: Annotated[str | None, "搜索策略：'single'(单引擎)、'parallel'(并行多引擎)、'fallback'(回退策略)"] = None,
    ) -> tuple[bool, str | dict[str, Any]]:
        """执行联网搜索

        Args:
            query: 搜索查询内容
            num_results: 返回结果数量
            time_range: 时间范围
            engine: 指定搜索引擎
            strategy: 搜索策略

        Returns:
            (是否成功, 搜索结果或错误信息)
        """
        try:
            # 从服务管理器获取搜索服务
            from src.core.managers import get_service_manager
            
            service_manager = get_service_manager()
            search_service = service_manager.get_service("web_search_tool:service:web_search")
            
            if not search_service:
                logger.error("未找到搜索服务，请确保 web_search_tool 插件已启用")
                return False, {"error": "搜索服务不可用，请确保 web_search_tool 插件已启用"}
            
            logger.info(f"执行搜索: {query}")
            
            # 调用搜索服务
            result = await search_service.search(
                query=query,
                num_results=num_results,
                time_range=time_range,
                engine=engine,
                strategy=strategy
            )
            
            # 检查是否有错误
            if "error" in result:
                logger.error(f"搜索失败: {result['error']}")
                return False, result["error"]
            
            # 提取搜索结果内容返回给 LLM
            content = result.get("content", "")
            num_results = result.get("num_results", 0)
            engine_used = result.get("engine_used", "")
            
            logger.info(f"搜索成功，返回 {num_results} 条结果，使用引擎: {engine_used or '默认'}")
            
            # 返回搜索结果内容（字符串格式，LLM 可以直接阅读）
            return True, content

        except Exception as e:
            logger.error(f"搜索工具执行失败: {e}", exc_info=True)
            return False, {"error": f"搜索失败: {str(e)}"}
