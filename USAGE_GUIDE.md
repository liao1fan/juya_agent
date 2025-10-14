# Juya Agent 使用指南

## 快速开始

### 方式一：对话机器人模式（推荐）

最简单的使用方式，像聊天一样与 Agent 交互：

```bash
python chat.py
```

启动后你可以：
- 💬 自然语言对话
- 📋 创建和管理定时任务
- 🎬 检查视频、生成早报、发送邮件
- 🔄 定时任务会在后台自动触发

#### 对话示例

```
💬 你: 检查橘鸦有没有新视频
🤖 Juya Agent: 正在检查...
[Agent 调用 check_new_videos 工具]

💬 你: 每天早上9点自动检查新视频并发送早报
🤖 Juya Agent: 已创建定时任务...
[Agent 调用 create_task 工具]

💬 你: 列出所有定时任务
🤖 Juya Agent: 以下是您的定时任务...
[Agent 调用 list_tasks 工具]

💬 你: exit
👋 再见！
```

### 方式二：单次命令模式

适合只执行一次任务的场景：

```bash
# 不保持运行，执行完即退出
python run_with_sampling.py --query "列出所有定时任务" --no-keep-alive

# 执行后保持运行，等待定时任务触发
python run_with_sampling.py --query "每天早上9点检查新视频"
```

### 方式三：持续服务模式

适合作为后台服务运行，只接收定时任务：

```bash
# 不执行任何初始查询，只等待定时任务
python run_with_sampling.py

# 或使用 nohup 后台运行
nohup python run_with_sampling.py > juya.log 2>&1 &
```

## 功能介绍

### 1. 视频监控功能

#### 检查新视频
```
💬 你: 检查橘鸦的新视频
```
Agent 会调用 `check_new_videos` 工具获取最新视频列表。

#### 处理视频生成早报
```
💬 你: 处理视频 BV1234567890
```
Agent 会：
1. 获取视频字幕或简介
2. 使用 AI 提取新闻要点
3. 生成 Markdown 格式的 AI 早报
4. 保存到本地文件

#### 发送邮件
```
💬 你: 发送 BV1234567890 的早报到邮箱
```
Agent 会读取已生成的早报并发送到配置的邮箱。

#### 完整流程
```
💬 你: 检查新视频，如果有就生成早报并发送邮件
```
Agent 会自动执行完整的三步流程。

### 2. 定时任务功能

#### 创建定时任务

使用自然语言描述：
```
💬 你: 每天早上9点检查橘鸦的新视频并发送早报
💬 你: 每小时检查一次新视频
💬 你: 明天下午3点处理视频 BV1234567890
💬 你: 每周一早上8点发送本周视频汇总
```

Agent 会自动将自然语言转换为正确的触发器配置。

#### 列出所有任务
```
💬 你: 列出所有定时任务
💬 你: 查看我的定时任务
💬 你: 有哪些定时任务
```

#### 查看任务详情
```
💬 你: 查看任务 task-xxx 的详细信息
💬 你: 任务 task-xxx 的执行历史
```

#### 修改任务
```
💬 你: 把每天9点的任务改成每天10点
💬 你: 修改任务 task-xxx 的执行时间为每周一
```

#### 暂停/恢复任务
```
💬 你: 暂停任务 task-xxx
💬 你: 恢复任务 task-xxx
```

#### 立即执行任务
```
💬 你: 立即执行任务 task-xxx
💬 你: 现在就运行任务 task-xxx
```

#### 删除任务
```
💬 你: 删除任务 task-xxx
💬 你: 取消每天9点的定时任务
```

### 3. 定时任务自动触发

当你创建了带有 `agent_prompt` 的定时任务后，到达指定时间时：

1. schedule-task-mcp 会自动触发任务
2. 通过 MCP Sampling 机制发送请求
3. Agent 接收到请求并自动执行
4. 执行结果会被记录到任务历史中

**无需人工干预！** 🎉

## 对话技巧

### 使用清晰的指令

✅ 好的指令：
```
检查橘鸦的新视频
创建每天早上9点的定时任务来检查新视频
列出所有定时任务
删除任务 task-1760356327548-g580l3q
```

❌ 模糊的指令：
```
看看
做点什么
帮我
那个任务
```

### 一次做一件事

✅ 清晰：
```
💬 你: 检查新视频
[等待响应]
💬 你: 处理 BV1234567890
[等待响应]
💬 你: 发送邮件
```

❌ 混乱：
```
💬 你: 检查新视频然后处理所有视频还有发送邮件另外创建个定时任务
```

虽然 Agent 可以处理复杂指令，但分步骤更清晰。

### 使用完整流程

当你想要完整的工作流时：
```
💬 你: 检查橘鸦的新视频，如果有新视频则生成AI早报并发送到邮箱
```

Agent 会自动：
1. 检查新视频
2. 对每个新视频生成早报
3. 发送邮件

## 环境配置

### 必需的环境变量

确保 `.env` 文件包含：

```bash
# OpenAI API（必需）
OPENAI_API_KEY="your-api-key"

# 邮件配置（发送早报时需要）
EMAIL_FROM="your-email@example.com"
SMTP_PASSWORD="your-smtp-password"
SMTP_SERVER="smtp.example.com"
SMTP_PORT="465"
SMTP_USE_SSL="true"
EMAIL_TO="recipient@example.com"

# GLM API（处理字幕时需要，可选）
GLM_API_KEY="your-glm-key"
GLM_API_BASE_URL="https://open.bigmodel.cn/api/paas/v4"

# Schedule Task MCP 配置（可选，有默认值）
SCHEDULE_TASK_TIMEZONE="Asia/Shanghai"
SCHEDULE_TASK_DB_PATH="/root/code/juya_openai/data/schedule_tasks.db"
SCHEDULE_TASK_SAMPLING_TIMEOUT="300000"
```

### 代理配置

如果需要代理访问 OpenAI API：

```bash
# 在启动前设置
export http_proxy=http://127.0.0.1:1081
export https_proxy=http://127.0.0.1:1081

# 或在 .env 文件中配置
# chat.py 会自动读取
```

## 常见使用场景

### 场景 1: 每日自动监控

```bash
# 启动对话机器人
python chat.py
```

```
💬 你: 创建每天早上9点的定时任务，检查橘鸦的新视频，如果有新视频就生成AI早报并发送到我的邮箱

🤖 Juya Agent: 已成功创建定时任务...
- 任务ID: task-xxx
- 触发时间: 每天 09:00
- 任务描述: 检查橘鸦的新视频，如果有新视频就生成AI早报并发送到邮箱

💬 你: exit
```

现在保持服务运行，每天早上9点会自动执行！

### 场景 2: 立即处理最新视频

```bash
python chat.py
```

```
💬 你: 检查新视频

🤖 Juya Agent: 找到 1 个新视频：
- BV1234567890: 【AI资讯】2025年10月14日

💬 你: 处理这个视频并发送邮件

🤖 Juya Agent:
1. ✅ 已生成 AI 早报
2. ✅ 已发送到邮箱

💬 你: exit
```

### 场景 3: 管理定时任务

```bash
python chat.py
```

```
💬 你: 列出所有定时任务

🤖 Juya Agent: 你有以下定时任务：
1. 每天早上9点检查新视频 (task-xxx)
2. 每周一汇总视频 (task-yyy)

💬 你: 暂停第一个任务

🤖 Juya Agent: 已暂停任务 task-xxx

💬 你: 下周再恢复它

🤖 Juya Agent: 你可以随时使用 "恢复任务 task-xxx" 来恢复

💬 你: exit
```

### 场景 4: 后台服务模式

适合在服务器上长期运行：

```bash
# 使用 screen 或 tmux
screen -S juya
python chat.py

# 然后 Ctrl+A, D 分离会话

# 或使用 nohup
nohup python run_with_sampling.py > juya.log 2>&1 &

# 查看日志
tail -f juya.log
```

## 特殊命令

在对话机器人中，有一些特殊命令：

- `exit` / `quit` / `q` - 退出对话
- `clear` - 清屏

## 故障排查

### 问题 1: 连接失败

```
❌ 错误: 连接 MCP 服务器失败
```

**解决**：确保已安装 `schedule-task-mcp`：
```bash
npx -y schedule-task-mcp --help
```

### 问题 2: OpenAI API 错误

```
❌ 错误: The api_key client option must be set
```

**解决**：检查 `.env` 文件中的 `OPENAI_API_KEY` 配置。

### 问题 3: 定时任务没有触发

**检查**：
1. 服务是否保持运行？
2. 任务是否启用？（`enabled: true`）
3. 任务状态是否为 `scheduled`？

**查看**：
```
💬 你: 查看任务 task-xxx 的详细信息
```

### 问题 4: 邮件发送失败

```
❌ 发送邮件失败
```

**检查**：
1. `.env` 中的邮件配置是否正确
2. SMTP 服务器是否可访问
3. 密码是否正确（某些邮箱需要专用密码）

## 高级用法

### 编程方式使用

如果你想在自己的代码中集成：

```python
import asyncio
from manager import JuyaManager

async def main():
    manager = JuyaManager()

    # 方式1: 单次执行
    result = await manager.run("检查新视频")
    print(result)

    # 方式2: 带 sampling 支持
    result = await manager.run_with_sampling(
        user_query="创建定时任务",
        keep_alive=True  # 保持运行
    )

asyncio.run(main())
```

### 自定义 Agent

修改 `juya_agents.py` 中的 `orchestrator_agent` 配置：

```python
orchestrator_agent = Agent(
    name="juya_orchestrator",
    instructions="你自定义的指令...",
    model="gpt-4o-mini",  # 或其他模型
    tools=[
        check_new_videos,
        process_video,
        send_email_report,
        # 你的自定义工具
    ]
)
```

## 总结

Juya Agent 提供了三种使用方式：

1. **对话机器人**（`chat.py`）- 最友好，适合交互使用
2. **命令行**（`run_with_sampling.py`）- 适合脚本化
3. **编程接口**（`manager.py`）- 适合集成到其他系统

选择最适合你的方式，享受 AI Agent 带来的自动化体验！🚀
