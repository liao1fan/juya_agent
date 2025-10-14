# Juya Agent - OpenAI Agents SDK 版本

橘鸦视频监控 Agent，使用 OpenAI Agents SDK 重构，实现三步工作流：检查新视频 → 整理AI早报 → 发送邮件。

## 🎯 功能特性

- ✅ **检查新视频** - 自动检测橘鸦B站账号的最新视频
- ✅ **AI早报生成** - 智能提取视频字幕/简介，生成结构化Markdown文档
- ✅ **邮件发送** - 自动将早报通过邮件发送
- ✅ **定时任务** - 集成 schedule-task-mcp，支持创建定时任务（如"每天早上9点检查新视频"）
- ✅ **清晰架构** - 使用 OpenAI Agents SDK 的 Agent 模式，职责分离
- ✅ **类型安全** - 使用 Pydantic 定义输入输出类型
- ✅ **可追溯** - 支持 OpenAI Dashboard tracing

## 📁 项目结构

```
juya_openai/
├── main.py              # 主入口程序
├── manager.py           # Agent 协调器
├── juya_agents.py       # Agent 定义
├── tools.py             # 工具函数（带 @function_tool 装饰器）
├── modules/             # 业务模块（复用自 juya_agent）
│   ├── bilibili_api.py
│   ├── subtitle_processor_ai.py
│   └── email_sender.py
├── config/
│   └── cookies.json     # B站 cookies
├── .env                 # 环境变量配置
├── docs/                # 生成的 Markdown 文档
└── data/                # 数据文件（已处理视频记录等）
```

## 🚀 快速开始

### 1. 安装依赖

```bash
# 使用 conda 环境（juya）
conda activate juya
pip install openai-agents
```

### 2. 配置环境变量

编辑 `.env` 文件：

```bash
# OpenAI API
OPENAI_API_KEY="your-openai-api-key"

# 邮件配置
EMAIL_FROM="your-email@163.com"
SMTP_PASSWORD="your-smtp-password"
SMTP_SERVER="smtp.163.com"
SMTP_PORT="465"
SMTP_USE_SSL="true"
EMAIL_TO="receiver@example.com"

# GLM API（用于字幕AI处理）
GLM_API_KEY="your-glm-api-key"
```

### 3. 配置 B站 Cookies

将你的 B站 cookies 保存到 `config/cookies.json`：

```json
{
  "SESSDATA": "your-sessdata",
  "bili_jct": "your-bili-jct",
  "buvid3": "your-buvid3"
}
```

### 4. 运行

```bash
# 交互式运行
python main.py

# 或者运行测试
python test_workflow.py
```

## 💡 使用示例

启动后，可以输入以下命令：

### 基础功能
```
你: 检查新视频
你: 处理最新视频
你: 处理 BV1nc4yzyEYc 并发送邮件
```

### 定时任务功能
```
你: 每天早上9点检查新视频
你: 查看我的定时任务
你: 删除任务 task-xxx
你: 暂停/恢复任务 task-xxx
你: 立即执行任务 task-xxx
```

## 🏗️ 架构设计

### 三步工作流

```
用户输入 → Orchestrator Agent
           ↓
    1. check_new_videos (检查新视频)
           ↓
    2. process_video (生成AI早报)
           ↓
    3. send_email_report (发送邮件)
           ↓
        返回结果
```

### Agent 架构

- **orchestrator_agent** - 主协调器，负责整个工作流和定时任务管理
- 工具函数：
  - `check_new_videos` - 检查新视频
  - `process_video` - 处理视频生成早报
  - `send_email_report` - 发送邮件
- MCP 服务器：
  - `schedule-task-mcp` - 提供定时任务管理能力

### 关键改进

相比旧版 Agent（使用 MCP + GLM SDK）：

✅ **更简洁** - 代码更清晰，架构更合理
✅ **更标准** - 使用 OpenAI Agents SDK 官方框架
✅ **更灵活** - 工具函数使用 `@function_tool` 装饰器，易于扩展
✅ **更类型安全** - 使用 Pydantic models 定义输入输出
✅ **更易调试** - 支持 OpenAI Dashboard tracing
✅ **定时任务** - 集成 schedule-task-mcp，支持自然语言创建定时任务

## 📝 开发说明

### 添加新工具

在 `tools.py` 中添加新的工具函数：

```python
@function_tool
def your_new_tool(param: Annotated[str, "参数说明"]) -> YourResultModel:
    """工具描述"""
    # 实现逻辑
    return YourResultModel(...)
```

然后在 `juya_agents.py` 中将工具添加到 Agent：

```python
orchestrator_agent = Agent(
    name="juya_orchestrator",
    instructions="...",
    model="gpt-4o-mini",
    tools=[check_new_videos, process_video, send_email_report, your_new_tool]
)
```

## 🔧 技术栈

- **OpenAI Agents SDK** - Agent 框架
- **OpenAI API (gpt-4o-mini)** - LLM 模型
- **schedule-task-mcp** - 定时任务管理（MCP 服务器）
- **GLM API** - 字幕AI处理
- **Pydantic** - 数据验证和类型定义
- **requests** - HTTP 请求
- **python-dotenv** - 环境变量管理

## 📅 定时任务说明

项目已集成 `schedule-task-mcp`，可以通过自然语言创建和管理定时任务：

### 支持的操作

- **创建任务**：`"每天早上9点检查新视频"`
- **查看任务**：`"查看我的定时任务"`
- **删除任务**：`"删除任务 task-xxx"`
- **暂停/恢复**：`"暂停任务 task-xxx"` / `"恢复任务 task-xxx"`
- **立即执行**：`"立即执行任务 task-xxx"`

### 配置

定时任务的配置在 `.env` 中：

```bash
SCHEDULE_TASK_TIMEZONE="Asia/Shanghai"
SCHEDULE_TASK_DB_PATH="/root/code/juya_openai/data/schedule_tasks.db"
SCHEDULE_TASK_SAMPLING_TIMEOUT="300000"
```

任务数据存储在 `data/schedule_tasks.db` SQLite 数据库中。

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！
