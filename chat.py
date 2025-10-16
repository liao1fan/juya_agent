#!/usr/bin/env python3
"""
Juya Agent 对话机器人

使用修改后的 OpenAI Agents SDK，完整支持 MCP Sampling 机制。

功能特点：
- 交互式对话界面
- 支持 MCP 工具调用（创建/管理定时任务）
- 支持 MCP Sampling（定时任务自动触发 Agent 执行）
- 使用单一 MCP 服务器进程，避免冲突

使用方法:
    python chat.py
"""

import asyncio
import os
import sys
import logging
import subprocess
from dotenv import load_dotenv
from agents import Agent, Runner
from agents.mcp import MCPServerStdio
from agents.tracing import set_tracing_disabled
from mcp.types import CreateMessageResult, TextContent
from juya_agents import orchestrator_agent
from pathlib import Path

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_sampling_callback(base_agent):
    """
    创建 MCP Sampling callback

    当 schedule-task-mcp 触发定时任务时，这个 callback 会被调用。
    它会使用基础 Agent（不包含 MCP 工具）来执行任务，避免递归调用。

    Args:
        base_agent: 基础 Agent 实例（包含核心工具，不包含 MCP 工具）

    Returns:
        async function: Sampling callback 函数
    """
    async def sampling_callback(context, params):
        """处理 MCP Sampling 请求"""
        # 从 params.messages 中提取任务描述
        agent_prompt = ""
        for message in params.messages:
            if message.role == "user":
                content = message.content
                if hasattr(content, 'text'):
                    agent_prompt = content.text
                elif hasattr(content, 'type') and content.type == 'text':
                    agent_prompt = content.text if hasattr(content, 'text') else str(content)
                break

        print(f"\n{'='*70}")
        print(f"🔔 定时任务触发！")
        print(f"{'='*70}")
        print(f"📝 任务: {agent_prompt}")
        print(f"🤖 执行中...")

        try:
            # 使用基础 Agent 执行任务（不包含 MCP 工具，避免递归）
            result = await Runner.run(
                starting_agent=base_agent,
                input=agent_prompt,
                max_turns=10
            )

            response_text = str(result.final_output) if hasattr(result, 'final_output') else str(result)

            print(f"\n✅ 任务执行完成！")
            print(f"结果: {response_text[:300]}...")
            print(f"{'='*70}\n")

            # 返回符合 MCP Sampling 规范的响应
            return CreateMessageResult(
                model=base_agent.model.model if hasattr(base_agent.model, 'model') else str(base_agent.model) if base_agent.model else "gpt-5-mini",
                role="assistant",
                content=TextContent(type="text", text=response_text),
                stopReason="endTurn"
            )

        except Exception as e:
            error_msg = f"执行失败: {str(e)}"
            print(f"\n❌ {error_msg}\n")
            logger.exception("Sampling callback 执行失败")

            # 即使失败也返回规范的响应
            return CreateMessageResult(
                model=base_agent.model.model if hasattr(base_agent.model, 'model') else str(base_agent.model) if base_agent.model else "gpt-5-mini",
                role="assistant",
                content=TextContent(type="text", text=f"⚠️ {error_msg}"),
                stopReason="endTurn"
            )

    return sampling_callback


class JuyaChatBot:
    """Juya 对话机器人"""

    def __init__(self):
        self.mcp_server = None
        self.agent_with_mcp = None
        self.current_agent = None
        self.input_items = []

    async def start(self):
        """启动对话机器人"""
        # 清除代理设置（新的 API 地址不需要代理）
        for key in ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY']:
            os.environ.pop(key, None)
        set_tracing_disabled(True)  # 禁用 tracing，避免无效的网络请求告警

        # # 输出 MCP Server 版本，便于诊断
        # try:
        #     version_result = subprocess.run(
        #         ["npx", "-y", "schedule-task-mcp", "--version"],
        #         check=True,
        #         capture_output=True,
        #         text=True
        #     )
        #     logger.info("schedule-task-mcp version: %s", version_result.stdout.strip())
        # except Exception as exc:
        #     logger.warning("Unable to determine schedule-task-mcp version: %s", exc)

        print("\n" + "="*70)
        print("🤖 Juya Agent 对话机器人")
        print("="*70)
        print("\n正在启动...")

        # 获取项目根目录
        PROJECT_ROOT = Path(__file__).resolve().parent

        # 配置环境变量
        schedule_env = {
            "SCHEDULE_TASK_TIMEZONE": os.getenv("SCHEDULE_TASK_TIMEZONE", "Asia/Shanghai"),
            "SCHEDULE_TASK_DB_PATH": os.getenv("SCHEDULE_TASK_DB_PATH", str(PROJECT_ROOT / "data" / "schedule_tasks.db")),
            "SCHEDULE_TASK_SAMPLING_TIMEOUT": os.getenv("SCHEDULE_TASK_SAMPLING_TIMEOUT", "300000"),
        }

        # 显示数据库路径
        print(f"📂 数据库路径: {schedule_env['SCHEDULE_TASK_DB_PATH']}")

        # 创建 sampling callback（使用基础 Agent，不包含 MCP 工具）
        callback = create_sampling_callback(orchestrator_agent)

        # 创建带 sampling 支持的 MCP 服务器
        self.mcp_server = MCPServerStdio(
            name="schedule-task-mcp",
            params={
                "command": "npx",
                "args": ["-y", "schedule-task-mcp@0.2.0"],
                "env": schedule_env,
            },
            sampling_callback=callback,  # ✨ 启用 Sampling 支持
            client_session_timeout_seconds=30,
        )

        print(f"🔌 连接 MCP 服务器: {self.mcp_server.name}")
        print(f"✅ Sampling 支持: 已启用")

        # 使用 async with 连接 MCP 服务器
        async with self.mcp_server as server:
            # 创建带 MCP 工具的 Agent
            self.agent_with_mcp = Agent(
                name=orchestrator_agent.name,
                instructions=orchestrator_agent.instructions,
                model=orchestrator_agent.model,
                tools=orchestrator_agent.tools,
                mcp_servers=[server],
            )
            self.current_agent = self.agent_with_mcp
            self.input_items = []

            print(f"✅ Agent 已创建: {self.agent_with_mcp.name}")
            print(f"\n提示:")
            print(f"  - 输入你的问题或指令")
            print(f"  - 输入 'exit' 或 'quit' 退出")
            print(f"  - 输入 'clear' 清屏")
            print(f"  - 定时任务会在后台自动触发并执行")
            print("\n" + "="*70 + "\n")

            # 进入对话循环
            await self.chat_loop()

    async def chat_loop(self):
        """对话循环"""
        while True:
            try:
                # 获取用户输入
                user_input = await self.get_user_input()

                # 处理特殊命令
                if user_input.lower() in ['exit', 'quit', 'q']:
                    print("\n👋 再见！\n")
                    break
                elif user_input.lower() == 'clear':
                    os.system('clear' if os.name != 'nt' else 'cls')
                    self.input_items = []
                    self.current_agent = self.agent_with_mcp
                    continue
                elif not user_input.strip():
                    continue

                # 调用 Agent 处理
                print(f"\n🤖 思考中...\n")
                response = await self.process_message(user_input)

                # 显示响应
                print(f"\n{'─'*70}")
                print(f"🤖 Juya Agent:")
                print(f"{'─'*70}\n")
                print(response)
                print(f"\n{'─'*70}\n")

            except KeyboardInterrupt:
                print("\n\n👋 再见！\n")
                break
            except Exception as e:
                print(f"\n❌ 错误: {e}\n")
                logger.exception("对话处理失败")

    async def get_user_input(self):
        """获取用户输入（异步方式）"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._sync_input)

    def _sync_input(self):
        """同步获取输入"""
        return input("💬 你: ")

    async def process_message(self, message: str):
        """处理用户消息"""
        try:
            # 添加本轮用户消息
            self.input_items.append({"role": "user", "content": message})

            # 使用 Runner 运行带 MCP 工具的 Agent，传入完整上下文
            result = await Runner.run(
                starting_agent=self.current_agent,
                input=self.input_items,
                max_turns=10
            )

            # 更新当前 Agent（防止出现 handoff）和上下文
            self.current_agent = result.last_agent
            self.input_items = result.to_input_list()

            # 提取响应
            response = result.final_output if hasattr(result, 'final_output') else str(result)
            return response

        except Exception as e:
            logger.exception("消息处理失败")
            return f"抱歉，处理消息时遇到错误: {str(e)}"


async def main():
    """主函数"""
    bot = JuyaChatBot()
    await bot.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 再见！\n")
        sys.exit(0)
