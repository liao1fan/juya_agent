"""
Juya Agent 定义
使用 OpenAI Agents SDK 定义各个专门的 Agent，并集成 schedule-task-mcp 定时任务能力
"""

import os
from pathlib import Path

from agents import Agent  # OpenAI Agents SDK
from agents.mcp import MCPServerStdio

from tools import (
    check_new_videos,
    process_video,
    send_email_report,
)


# ============= MCP Server 配置 =============

# 获取项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent

# 配置 schedule-task-mcp 服务器
def get_schedule_mcp_server():
    """
    获取 schedule-task-mcp 服务器配置

    返回 MCPServerStdio 配置对象，用于：
    1. OpenAI Agents SDK 的 MCP 工具集成（通过 mcp_servers 参数）
    2. 官方 MCP Client 的连接参数（在 manager.py 中用于 sampling 支持）

    注意：sampling_callback 在 manager.py 中通过官方 MCP Client 单独配置
    """
    # 环境变量配置
    schedule_env = {
        "SCHEDULE_TASK_TIMEZONE": os.getenv("SCHEDULE_TASK_TIMEZONE", "Asia/Shanghai"),
        "SCHEDULE_TASK_DB_PATH": os.getenv("SCHEDULE_TASK_DB_PATH", str(PROJECT_ROOT / "data" / "schedule_tasks.db")),
        "SCHEDULE_TASK_SAMPLING_TIMEOUT": os.getenv("SCHEDULE_TASK_SAMPLING_TIMEOUT", "300000"),
    }

    return MCPServerStdio(
        name="schedule-task-mcp",
        params={
            "command": "npx",
            "args": ["-y", "schedule-task-mcp"],
            "env": schedule_env,
        },
    )


# ============= Agent 定义 =============

# 视频检查 Agent
video_checker_agent = Agent(
    name="video_checker",
    instructions="""你是一个视频检查专家。你的任务是检查橘鸦（B站UP主）是否发布了新视频。

任务流程：
1. 调用 check_new_videos 工具检查最近的视频
2. 分析返回的结果
3. 如果有新视频，返回新视频的列表（包含 BV号、标题、发布时间）
4. 如果没有新视频，明确告知用户

输出要求：
- 清晰列出所有新视频的信息
- 使用友好的语言告知用户
""",
    model="gpt-4o-mini",
    tools=[check_new_videos]
)


# 报告生成 Agent
report_generator_agent = Agent(
    name="report_generator",
    instructions="""你是一个AI早报生成专家。你的任务是将橘鸦的视频字幕或简介整理成结构化的Markdown文档。

任务流程：
1. 接收视频的 BV号
2. 调用 process_video 工具处理视频
3. 工具会自动：
   - 获取视频字幕或简介
   - 使用AI提取新闻要点
   - 生成 Markdown 格式的AI早报
   - 保存到本地文件
4. 返回处理结果（包含文档路径、资讯数量等）

输出要求：
- 告知用户文档生成成功
- 提供文档路径
- 说明提取了多少条资讯
""",
    model="gpt-4o-mini",
    tools=[process_video]
)


# 邮件发送 Agent
email_sender_agent = Agent(
    name="email_sender",
    instructions="""你是一个邮件发送专家。你的任务是将生成的AI早报通过邮件发送给用户。

任务流程：
1. 接收视频的 BV号
2. 调用 send_email_report 工具发送邮件
3. 工具会自动：
   - 读取已处理的视频文档
   - 生成邮件内容
   - 发送到配置的邮箱
4. 返回发送结果

输出要求：
- 明确告知用户邮件是否发送成功
- 如果失败，说明失败原因
""",
    model="gpt-4o-mini",
    tools=[send_email_report]
)


# 主协调 Agent (Orchestrator) - 带定时任务能力
orchestrator_agent = Agent(
    name="juya_orchestrator",
    instructions="""你是橘鸦视频监控系统的主协调器。你负责协调整个工作流程，并具备定时任务管理能力。

核心工作流程（三步流水线）：
1. 【检查新视频】- 使用 check_new_videos 工具检查是否有新视频
2. 【生成AI早报】- 对于每个新视频，使用 process_video 工具生成Markdown文档
3. 【发送邮件】- 使用 send_email_report 工具将早报发送给用户

定时任务能力：
你现在可以使用 schedule-task-mcp 提供的定时任务工具执行定时任务制定和管理。

重要原则：
- 严格按照三个步骤顺序执行工作流
- 每一步都要等待前一步完成
- 如果某一步失败，要明确告知用户
- 始终保持友好和专业的语气

用户常见请求：
- "检查新视频" - 只执行步骤1
- "处理最新视频" - 执行步骤1和2
- "处理并发送邮件" - 执行完整的三步流程
- "每天早上9点自动检查新视频" - 创建定时任务
- "查看我的定时任务" - 列出所有任务
- "取消定时任务" - 删除任务

根据用户的请求，灵活调用相应的工具。
""",
    model="gpt-4o-mini",
    tools=[
        check_new_videos,
        process_video,
        send_email_report
    ]
    # MCP 服务器将在 JuyaManager 中动态添加
)
