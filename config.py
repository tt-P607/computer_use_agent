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
            default="plugins/computer_use_agent/workspace",
            description=(
                "工作目录路径（支持相对路径，相对于项目根目录），"
                "所有文件操作限制在此目录内"
            ),
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
        wsl_mode: bool = Field(
            default=False,
            description="是否在 WSL 环境中运行（napcat 在 WSL 中时启用），启用后向 napcat 传递的文件路径将自动转换为 WSL 格式（/mnt/x/...）"
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

    @config_section("file_server")
    class FileServerSection(SectionBase):
        """HTTP 文件服务配置"""

        enable: bool = Field(
            default=False,
            description=(
                "是否启用基于 HTTP URL 发送图片/媒体文件（推荐）。"
                "启用后将利用框架中已启动的 FastAPI HTTP 服务器歌出文件，"
                "而非 base64 编码传递，适合截图等较大文件。"
                "关闭则回退为 base64 模式。"
            )
        )
        base_url: str = Field(
            default="http://127.0.0.1:8000",
            description=(
                "napcat 访问文件服务的 HTTP 基址（不含末尾斜杠）。"
                "若 napcat 在 WSL 中运行，需改为 Windows 主机对 WSL 的 IP，如 http://172.x.x.x:8000；"
                "若 napcat 在 Docker 中运行，可改为 http://host.docker.internal:8000。"
            )
        )

    @config_section("prompt")
    class PromptSection(SectionBase):
        """自定义提示词配置"""

        custom_instructions: str = Field(
            default="",
            description=(
                "追加到系统提示词末尾的自定义指令（多行字符串）。\n"
                "可在此描述希望优先使用本插件的具体场景，例如：\n"
                "  - 需要写作并保存文件时（同人文、剧本、代码等），优先用此插件完成\n"
                "  - 需要截图或下载文件时，优先用此插件完成\n"
                "这些说明只影响本插件的使用时机，不会覆盖通用安全规则。"
            ),
        )

    @config_section("model")
    class ModelSection(SectionBase):
        """执行模型配置"""

        model_name: str = Field(
            default="",
            description=(
                "Agent 执行所用的模型名称（对应 config/model.toml 中 [[models]] 的 name 字段）。\n"
                "留空时回退到任务组 'actor' 的默认配置。\n"
                "示例：\"gemini-2.5-flash-preview\""
            ),
        )
        temperature: float = Field(
            default=0.5,
            description="模型采样温度（0.0-2.0），仅在 model_name 非空时生效。",
        )
        max_tokens: int = Field(
            default=8192,
            description="最大输出 token 数，仅在 model_name 非空时生效。",
        )

    # 配置节实例
    plugin: PluginSection = Field(default_factory=PluginSection)
    security: SecuritySection = Field(default_factory=SecuritySection)
    network: NetworkSection = Field(default_factory=NetworkSection)
    screenshot: ScreenshotSection = Field(default_factory=ScreenshotSection)
    file_server: FileServerSection = Field(default_factory=FileServerSection)
    prompt: PromptSection = Field(default_factory=PromptSection)
    model: ModelSection = Field(default_factory=ModelSection)
