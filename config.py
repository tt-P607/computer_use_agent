"""Computer Use Agent 插件配置定义"""
from __future__ import annotations

from typing import ClassVar

from src.core.components.base.config import BaseConfig, Field, SectionBase, config_section


class ComputerUseAgentConfig(BaseConfig):
    """计算机使用 Agent 插件配置"""

    config_name: ClassVar[str] = "config"
    config_description: ClassVar[str] = "计算机使用 Agent 插件配置"

    @config_section("plugin")
    class PluginSection(SectionBase):
        """插件基本配置"""

        enabled: bool = Field(default=True, description="是否启用插件")

    @config_section("security")
    class SecuritySection(SectionBase):
        """安全配置"""

        workspace_directory: str = Field(
            default="e:\\delveoper\\mmc010\\Neo-MoFox\\plugins\\computer_use_agent\\workspace",
            description="工作目录（绝对路径），所有文件操作限制在此目录内"
        )
        max_file_size_mb: int = Field(
            default=10,
            description="最大文件大小限制（MB）"
        )
        allowed_file_extensions: list[str] = Field(
            default=[".txt", ".md", ".json", ".csv", ".log", ".py", ".js", ".html", ".css"],
            description="允许操作的文件扩展名"
        )
        enable_directory_creation: bool = Field(
            default=True,
            description="是否允许创建子目录"
        )

    @config_section("network")
    class NetworkSection(SectionBase):
        """网络配置"""

        timeout: int = Field(
            default=30,
            description="网络请求超时时间（秒）"
        )
        max_response_size_mb: int = Field(
            default=5,
            description="最大响应大小（MB）"
        )
        allowed_schemes: list[str] = Field(
            default=["http", "https"],
            description="允许的 URL 协议"
        )

    @config_section("screenshot")
    class ScreenshotSection(SectionBase):
        """截图配置"""

        screenshot_format: str = Field(
            default="png",
            description="截图格式（png/jpeg）"
        )
        jpeg_quality: int = Field(
            default=85,
            description="JPEG 质量（0-100）"
        )
        max_width: int = Field(
            default=1920,
            description="最大截图宽度"
        )
        max_height: int = Field(
            default=1080,
            description="最大截图高度"
        )

    # 配置节实例
    plugin: PluginSection = Field(default_factory=PluginSection)
    security: SecuritySection = Field(default_factory=SecuritySection)
    network: NetworkSection = Field(default_factory=NetworkSection)
    screenshot: ScreenshotSection = Field(default_factory=ScreenshotSection)
