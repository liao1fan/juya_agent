#!/usr/bin/env python3
"""
Juya Agent 主程序
使用 OpenAI Agents SDK 实现的橘鸦视频监控 Agent
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).resolve().parent))

from manager import JuyaManager


async def main():
    """主函数"""
    print("\n" + "="*70)
    print("🎬 橘鸦视频监控 Agent (OpenAI Agents SDK 版本)")
    print("="*70 + "\n")

    manager = JuyaManager()

    # 交互式模式
    while True:
        try:
            user_input = input("\n你: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ['exit', 'quit', '退出']:
                print("\n👋 再见！\n")
                break

            # 运行 Agent
            await manager.run(user_input)

        except KeyboardInterrupt:
            print("\n\n👋 用户中断，再见！\n")
            break
        except Exception as e:
            print(f"\n❌ 错误: {e}\n")


if __name__ == "__main__":
    asyncio.run(main())
