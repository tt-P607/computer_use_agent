"""截图工具"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any, cast

from PIL import Image
import mss

from src.core.components import BaseTool
from src.kernel.logger import get_logger

logger = get_logger("screenshot_tool")


class ScreenshotTool(BaseTool):
    """屏幕截图工具

    捕获当前屏幕并保存到文件
    """

    tool_name: str = "screenshot"
    tool_description: str = "截取当前屏幕并保存为图片文件"

    async def execute(
        self,
        monitor: Annotated[int, "显示器编号（1=主显示器，0=所有显示器）"] = 1,
        filename: Annotated[str | None, "自定义文件名（不含扩展名），留空则自动生成。不要包含路径分隔符，仅填文件名本身"] = None,
        save_path: Annotated[str, "保存目录（相对于工作目录的子目录名，不是文件名），默认保存到 screenshots/目录"] = "screenshots",
    ) -> tuple[bool, str | dict[str, Any]]:
        """截取屏幕

        Args:
            monitor: 显示器编号（1=主显示器，0=所有显示器）
            filename: 自定义文件名（不含扩展名），留空则自动生成
            save_path: 保存路径（相对于工作目录的路径）

        Returns:
            (是否成功, 文件路径或错误信息)
        """
        try:
            # 获取配置
            from ..config import ComputerUseAgentConfig
            
            config = cast(ComputerUseAgentConfig, self.plugin.config)
            screenshot_format = config.screenshot.screenshot_format
            jpeg_quality = config.screenshot.jpeg_quality
            max_width = config.screenshot.max_width
            max_height = config.screenshot.max_height
            workspace_dir = config.security.workspace_directory

            # 兼容 LLM 将完整路径（含扩展名）误填入 save_path 的情况：
            # 若 save_path 带有图片扩展名，自动拆分为目录 + 文件名
            save_path_obj = Path(save_path)
            image_exts = {".png", ".jpg", ".jpeg"}
            if save_path_obj.suffix.lower() in image_exts:
                # 最后一段视为文件名（去掉扩展名），父路径视为目录
                if not filename:
                    filename = save_path_obj.stem  # 不含扩展名
                save_path = str(save_path_obj.parent) if str(save_path_obj.parent) != "." else "screenshots"

            # 构建保存目录（相对于工作目录）
            save_dir = Path(workspace_dir) / save_path
            save_dir.mkdir(parents=True, exist_ok=True)

            # 生成文件名
            if filename:
                file_basename = filename
            else:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                file_basename = f"screenshot_{timestamp}"
            
            # 添加扩展名
            file_ext = ".jpg" if screenshot_format.lower() == "jpeg" else ".png"
            filepath = save_dir / f"{file_basename}{file_ext}"
            
            # 如果文件已存在，添加序号
            counter = 1
            while filepath.exists():
                filepath = save_dir / f"{file_basename}_{counter}{file_ext}"
                counter += 1

            # 截图
            with mss.mss() as sct:
                # 获取显示器信息
                if monitor < 0 or monitor > len(sct.monitors) - 1:
                    return False, {
                        "error": f"无效的显示器编号: {monitor}",
                        "available": f"0-{len(sct.monitors) - 1}"
                    }

                # 截取屏幕
                screenshot = sct.grab(sct.monitors[monitor])
                
                # 转换为 PIL Image
                img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

                # 调整大小
                if img.width > max_width or img.height > max_height:
                    img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)

                # 保存到文件
                if screenshot_format.lower() == "jpeg":
                    img.save(filepath, format="JPEG", quality=jpeg_quality)
                else:
                    img.save(filepath, format="PNG")

                logger.info(f"截图成功: 显示器 {monitor}, 尺寸 {img.width}x{img.height}, 保存至 {filepath}")
                return True, {
                    "filepath": str(filepath),
                    "format": screenshot_format,
                    "width": img.width,
                    "height": img.height,
                    "monitor": monitor,
                    "filesize_kb": round(os.path.getsize(filepath) / 1024, 2),
                }

        except Exception as e:
            logger.error(f"截图失败: {e}")
            return False, {"error": str(e)}
