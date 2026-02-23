"""Computer Use Agent Plugin

一个功能强大的计算机使用代理插件，提供文件操作、网络请求、截图等功能。
所有文件操作都限制在工作目录内，确保安全性。
"""

from typing import cast

from src.kernel.logger import get_logger
from src.core.components import BasePlugin, register_plugin

from .config import ComputerUseAgentConfig
from .agent import ComputerUseAgent

logger = get_logger("computer_use_agent_plugin")


@register_plugin
class ComputerUseAgentPlugin(BasePlugin):
    """计算机使用 Agent 插件

    提供计算机操作能力，包括：
    - 文件创建、读取、写入（限制在工作目录内）
    - HTTP 网络请求（基于 aiohttp）
    - 屏幕截图
    - 消息发送
    """

    # 插件基本信息
    plugin_name: str = "computer_use_agent"
    plugin_description: str = "计算机使用 Agent 插件"
    plugin_version: str = "1.0.0"

    # 插件配置
    configs: list[type] = [ComputerUseAgentConfig]

    # 依赖组件
    dependent_components: list[str] = []

    def __init__(self, *args, **kwargs):
        """初始化插件"""
        super().__init__(*args, **kwargs)
        logger.info("🤖 Computer Use Agent 插件已加载")

        # 确保工作目录存在
        try:
            from pathlib import Path
            
            config = cast(ComputerUseAgentConfig, self.config)
            workspace_path = Path(config.security.workspace_directory)
            workspace_path.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"📁 工作目录: {workspace_path}")
        except Exception as e:
            logger.error(f"❌ 创建工作目录失败: {e}")

    def get_components(self) -> list[type]:
        """获取插件组件列表

        Returns:
            插件内所有组件类的列表
        """
        components = []

        # 从配置读取组件启用状态
        if self.config and isinstance(self.config, ComputerUseAgentConfig):
            if getattr(getattr(self.config, "plugin", None), "enabled", True):
                components.append(ComputerUseAgent)
        else:
            # 默认启用
            components.append(ComputerUseAgent)

        return components
