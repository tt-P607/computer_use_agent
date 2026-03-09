"""Computer Use Agent Plugin

提供文件操作、网络请求、截图等计算机使用能力的 Agent 插件。
所有文件操作限制在工作目录内，确保沙盒安全。
"""

from src.kernel.logger import get_logger
from src.core.components import BasePlugin, register_plugin
from src.core.components.base.config import BaseConfig

from .config import ComputerUseAgentConfig
from .agent import ComputerUseAgent
from .routers import FileServerRouter

logger = get_logger("computer_use_agent_plugin")


@register_plugin
class ComputerUseAgentPlugin(BasePlugin):
    """计算机使用 Agent 插件。

    提供计算机操作能力，包括：
    - 文件创建、读取、写入（限制在工作目录内）
    - HTTP 网络请求（基于 aiohttp）
    - 屏幕截图
    - 消息发送
    """

    plugin_name: str = "computer_use_agent"
    plugin_description: str = "计算机使用 Agent 插件"
    plugin_version: str = "1.0.0"

    configs: list[type[BaseConfig]] = [ComputerUseAgentConfig]
    dependent_components: list[str] = []

    def get_components(self) -> list[type]:
        """获取插件组件列表。

        根据配置决定启用哪些组件，若配置类型不符则拒绝加载，
        不使用 fallback 默认值以避免静默错误。

        Returns:
            插件内所有组件类的列表。
        """
        if not isinstance(self.config, ComputerUseAgentConfig):
            logger.error(
                "插件配置类型错误（期望 ComputerUseAgentConfig），无法加载组件"
            )
            return []

        components: list[type] = []
        if self.config.plugin.enabled:
            components.append(ComputerUseAgent)
        if self.config.file_server.enable:
            components.append(FileServerRouter)
        return components

    async def on_plugin_loaded(self) -> None:
        """插件加载时确保工作目录存在，并将自定义场景说明注入 agent 描述。"""
        from pathlib import Path

        if not isinstance(self.config, ComputerUseAgentConfig):
            logger.error("配置类型错误，跳过工作目录初始化")
            return

        workspace_path = Path(self.config.security.workspace_directory)
        workspace_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"🤖 Computer Use Agent 已加载，工作目录: {workspace_path.resolve()}")

        # 将自定义场景说明追加到 agent_description，
        # 使 Chatter 侧也能感知到用户配置的使用时机
        custom = self.config.prompt.custom_instructions.strip()
        if custom:
            ComputerUseAgent.agent_description = (
                ComputerUseAgent.agent_description.rstrip()
                + "\n\n"
                + custom
            )
            logger.debug("已将自定义场景说明追加到 agent_description")
