"""Computer Use Agent 系统提示词构建

将提示词的拼装逻辑从 execute 方法中抽离到独立模块，
便于单独测试与维护。
"""
from __future__ import annotations

import os

from src.kernel.logger import get_logger

logger = get_logger("cua_prompts")


def _list_workspace_files(workspace_dir: str) -> str:
    """列举工作目录下的一级文件与目录，最多展示 50 条。

    Args:
        workspace_dir: 工作目录的绝对路径字符串。

    Returns:
        格式化的文件列表字符串；若读取失败则返回提示语。
    """
    try:
        items: list[str] = []
        for name in sorted(os.listdir(workspace_dir)):
            full = os.path.join(workspace_dir, name)
            label = "[目录]" if os.path.isdir(full) else "[文件]"
            items.append(f"{label} {name}")

        result = "\n".join(items[:50])
        if len(items) > 50:
            result += f"\n... 还有 {len(items) - 50} 个项目未显示"
        return result or "（工作目录为空）"
    except Exception as e:
        logger.warning(f"列出工作目录失败: {e}")
        return "无法列出文件"


def _build_persona_text() -> tuple[str, str]:
    """读取核心配置中的 Bot 人设信息。

    Returns:
        (nickname, 完整人设文本) 元组；获取失败时均返回空字符串。
    """
    try:
        from src.core.config import get_core_config

        personality = get_core_config().personality
        nickname = personality.nickname or ""
        parts: list[str] = []
        if personality.personality_core:
            parts.append(personality.personality_core)
        if personality.personality_side:
            parts.append(personality.personality_side)
        if personality.identity:
            parts.append(personality.identity)
        return nickname, "\n".join(parts)
    except Exception as e:
        logger.warning(f"获取人设信息失败: {e}")
        return "", ""


def build_system_prompt(workspace_dir: str, custom_instructions: str = "") -> str:
    """构建计算机使用 Agent 的完整系统提示词。

    职责定位：这是 Bot 的"手脚"执行层，负责动手完成具体操作，
    把结果通过 finish_task 汇报回 Bot 的"大脑"（Chatter），
    由 Chatter 决定如何与用户沟通。本层不直接跟用户说话。

    Args:
        workspace_dir: 工作目录路径字符串（用于展示与说明）。
        custom_instructions: 用户在配置文件中填写的自定义指令，为空则不注入。

    Returns:
        最终拼装完成的系统提示词字符串。
    """
    nickname, persona_body = _build_persona_text()
    files_list = _list_workspace_files(workspace_dir)

    parts: list[str] = []

    # ── 职责锚定：我是手脚，不是嘴 ──
    identity_lines: list[str] = []
    if nickname:
        identity_lines.append(f"我是 {nickname} 的行动执行层。")
    if persona_body:
        identity_lines.append(persona_body)
    identity_lines.append(
        "我的职责是动手完成交办的任务：操作文件、搜索网络、截图、执行命令。\n"
        "我不直接和用户说话——我只负责把事情做完，然后把结果原原本本地汇报回去，\n"
        "由上层的大脑决定怎么跟用户讲。"
    )
    parts.append("# 我的职责\n" + "\n".join(identity_lines))

    # ── 当前工作区状态 ──
    parts.append(
        f"# 我的工作区\n"
        f"所有文件操作限定在：{workspace_dir}\n\n"
        f"目前工作区里有：\n{files_list}"
    )

    # ── 执行规范 ──
    parts.append(
        "# 执行规范\n"
        "按照合理的顺序一步一步来，每步完成后检查返回值是否成功。\n"
        "任何步骤失败，立刻停下来分析原因，能修复就修复，不能修复就在最终汇报中如实说明，\n"
        "绝不在失败之后继续假装成功往下走。\n"
        "全部完成后，调用 finish_task 结束本次任务——这是我把结果交还给大脑的唯一出口。"
    )

    # ── finish_task 汇报规范 ──
    parts.append(
        "# 如何汇报结果\n"
        "finish_task 的汇报内容会直接传给大脑，要写得清楚、完整：\n"
        "- 做了什么、得到了什么结果\n"
        "- 生成或修改了哪些文件（含路径）\n"
        "- 如果有失败，说清楚是哪一步、为什么失败\n"
        "不需要客套或修饰，写事实就行。"
    )

    # ── 下载文件技术约束 ──
    parts.append(
        "# 下载文件注意事项\n"
        "download_file 只接受直接下载链接（文件本身的 URL），不是网页链接。\n"
        "如果下载回来的是 HTML 页面，说明链接不对，需要先通过 web_search 或 curl 找到真正的直链。\n"
        "真正的直链通常以 .zip、.exe、.apk、.jar 等扩展名结尾。"
    )

    # ── 用户自定义指令（可选）──
    if custom_instructions.strip():
        parts.append(
            "# 自定义使用场景\n"
            + custom_instructions.strip()
        )

    return "\n\n".join(parts)
