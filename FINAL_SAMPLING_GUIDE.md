# 最终版 Sampling Callback 使用指南

## 🎯 核心函数：`create_sampling_callback_with_agent`

这是最终推荐的实现方式，专门为 OpenAI Agents SDK 设计。

### 📝 函数签名

```python
def create_sampling_callback_with_agent(orchestrator_agent) -> SamplingCallbackFunction:
    """
    创建一个使用指定 Agent 的 sampling callback

    Args:
        orchestrator_agent: 主程序的 Agent 实例（带有所有工具）

    Returns:
        async function: 符合 MCP sampling callback 签名的函数
    """
```

### 🔄 工作流程

```
┌─────────────────────────────────────────────────────────────┐
│ 1. schedule-task-mcp 定时任务到期                            │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. schedule-task-mcp 发送 sampling/createMessage 请求        │
│                                                               │
│    params: {                                                  │
│      messages: [{                                             │
│        role: 'user',                                          │
│        content: {                                             │
│          type: 'text',                                        │
│          text: task.agent_prompt  ← 这是关键！                │
│        }                                                       │
│      }],                                                       │
│      maxTokens: 2000                                          │
│    }                                                           │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. MCP ClientSession 接收请求                                 │
│    调用 sampling_callback(prompt, system_prompt)             │
│    其中 prompt = task.agent_prompt                            │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. sampling_callback 内部                                     │
│    调用 Runner.run(orchestrator_agent, input=prompt)         │
│                                                               │
│    orchestrator_agent 会：                                    │
│    - 分析 prompt（任务描述）                                   │
│    - 决定调用哪些工具                                          │
│    - 执行工具并返回结果                                        │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. 返回 Agent 的执行结果给 schedule-task-mcp                  │
│    结果被记录到任务历史中                                      │
└─────────────────────────────────────────────────────────────┘
```

## 💻 完整使用示例

### 步骤 1：准备 orchestrator_agent

```python
# juya_agents.py
from agents import Agent
from tools import check_new_videos, process_video, send_email_report

orchestrator_agent = Agent(
    name="juya_orchestrator",
    instructions="""你是橘鸦视频监控系统的主协调器。

当收到定时任务时：
1. 分析任务描述
2. 根据描述决定需要调用哪些工具
3. 按顺序执行工具
4. 返回执行结果

可用工具：
- check_new_videos: 检查是否有新视频
- process_video: 处理视频生成AI早报
- send_email_report: 发送邮件报告
    """,
    model="gpt-4o-mini",
    tools=[
        check_new_videos,
        process_video,
        send_email_report
    ]
)
```

### 步骤 2：创建 sampling callback

```python
# manager.py 或者单独的 mcp_integration.py
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from test_mcp_client import create_sampling_callback_with_agent
from juya_agents import orchestrator_agent

async def start_mcp_with_sampling():
    """启动支持 sampling 的 MCP 客户端"""

    # 配置 schedule-task-mcp 服务器
    server_params = StdioServerParameters(
        command="npx",
        args=["-y", "schedule-task-mcp"],
        env={
            "SCHEDULE_TASK_TIMEZONE": "Asia/Shanghai",
            "SCHEDULE_TASK_DB_PATH": "./data/schedule_tasks.db",
            "SCHEDULE_TASK_SAMPLING_TIMEOUT": "300000",
        }
    )

    # 创建 sampling callback
    sampling_callback = create_sampling_callback_with_agent(orchestrator_agent)

    # 连接到 MCP 服务器
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(
            read,
            write,
            sampling_callback=sampling_callback  # ← 关键！
        ) as session:
            await session.initialize()

            print("✅ MCP 服务器已连接，支持 sampling")

            # 保持连接，等待定时任务触发
            # 这个函数需要一直运行，不能退出
            await keep_alive()
```

### 步骤 3：创建定时任务

```python
async def create_schedule_task(session):
    """创建定时任务"""

    result = await session.call_tool(
        "create_task",
        arguments={
            "name": "每天早上9点检查新视频",
            "trigger_type": "cron",
            "trigger_config": {
                "expression": "0 9 * * *"
            },
            "agent_prompt": "检查橘鸦的新视频，如果有新视频则生成AI早报并发送到邮箱"
            #              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
            #              这个字符串会在定时任务触发时传给 orchestrator_agent
        }
    )

    print(f"任务创建成功: {result}")
```

### 步骤 4：定时任务自动执行

```python
# 第二天早上9点，定时任务自动触发：

# schedule-task-mcp 发送 sampling 请求:
#   prompt = "检查橘鸦的新视频，如果有新视频则生成AI早报并发送到邮箱"

# orchestrator_agent 接收到 prompt，开始处理：
#   1. 分析任务: "需要检查新视频、生成早报、发送邮件"
#   2. 调用 check_new_videos() 工具
#   3. 如果有新视频，调用 process_video(bv_id) 工具
#   4. 调用 send_email_report(bv_id) 工具
#   5. 返回执行结果

# 结果被记录到 schedule-task-mcp 的任务历史中
```

## 📊 与其他方案对比

| 方案 | 优点 | 缺点 | 适用场景 |
|------|------|------|---------|
| **create_sampling_callback_with_agent** | ✅ 可以调用工具<br>✅ 复用现有 Agent<br>✅ 简单清晰 | ⚠️ 每次创建新 Agent 实例（开销中等） | **推荐用于生产** |
| OpenAI API 直接调用 | ✅ 延迟低<br>✅ 实现简单 | ❌ 无法调用工具<br>❌ 需要手动解析和调度 | 简单任务，不需要工具 |
| 每次创建临时 Agent | ✅ 可以调用工具 | ❌ 开销大<br>❌ 重复初始化 | 不推荐 |

## ⚠️ 重要注意事项

### 1. ClientSession 生命周期

**ClientSession 必须长期运行！**

```python
# ❌ 错误示例
async with ClientSession(...) as session:
    await session.initialize()
    await session.call_tool("create_task", ...)
# session 关闭了，定时任务触发时无法接收 sampling 请求！

# ✅ 正确示例
async with ClientSession(...) as session:
    await session.initialize()
    await session.call_tool("create_task", ...)

    # 保持连接，一直运行
    await keep_alive()  # 永远不退出
```

### 2. Agent 的重用

当前实现每次 sampling 都使用传入的 `orchestrator_agent`，这是好的，但如果 Agent 有状态（context），需要注意状态管理。

### 3. 错误处理

callback 内部已经包含了异常处理，会返回错误信息给 schedule-task-mcp。

## 🚀 测试方法

```bash
# 测试最终版 callback
python test_mcp_client.py agent
```

## 📝 实际集成到 juya_openai 的步骤

1. **将 `create_sampling_callback_with_agent` 函数复制到项目中**
   - 创建新文件 `mcp_integration.py`
   - 或者添加到 `manager.py`

2. **修改 `manager.py`**
   ```python
   from mcp_integration import create_sampling_callback_with_agent
   from juya_agents import orchestrator_agent

   # 在初始化时创建 sampling callback
   sampling_callback = create_sampling_callback_with_agent(orchestrator_agent)
   ```

3. **启动长期运行的 MCP 客户端**
   - 作为后台任务运行
   - 或者作为独立的服务

4. **测试定时任务**
   - 创建短期任务（30秒后触发）
   - 观察 Agent 是否正确执行

## 💡 总结

**最终推荐方案**：使用 `create_sampling_callback_with_agent` 工厂函数

**关键点**：
1. ✅ 传入 `orchestrator_agent`（带有所有工具）
2. ✅ task.agent_prompt 会作为 input 传给 Agent
3. ✅ Agent 根据 prompt 决定调用哪些工具
4. ✅ ClientSession 需要长期运行

**这个方案完美结合了**：
- MCP 官方 SDK 的 sampling 支持
- OpenAI Agents SDK 的工具调用能力
- schedule-task-mcp 的定时任务功能
