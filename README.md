# Juya Agent

橘鸦视频监控 Agent，自动检测 B 站新视频并生成 AI 早报。

## 功能

- 🎥 检查橘鸦 B 站账号的最新视频
- 📝 从视频字幕/简介提取新闻，生成结构化 Markdown 文档
- 📧 自动发送邮件通知
- ⏰ 支持定时任务（通过自然语言创建，如"每天早上9点检查新视频"）
- 💬 交互式对话界面

## 技术栈

- OpenAI Agents SDK
- OpenAI API (gpt-4o-mini)
- schedule-task-mcp（定时任务）
- Python 3.10+

## 快速开始

### 1. 安装依赖

```bash
pip install openai openai-agents python-dotenv requests
npm install -g schedule-task-mcp
```

### 2. 配置环境变量

创建 `.env` 文件：

```bash
# OpenAI API
OPENAI_API_KEY="your-api-key"
OPENAI_BASE_URL="https://ai.devtool.tech/proxy/v1"

# 邮件配置
EMAIL_FROM="your-email@163.com"
SMTP_PASSWORD="your-smtp-password"
SMTP_SERVER="smtp.163.com"
SMTP_PORT="465"
SMTP_USE_SSL="true"
EMAIL_TO="receiver@example.com"

# 定时任务配置
SCHEDULE_TASK_TIMEZONE="Asia/Shanghai"
SCHEDULE_TASK_DB_PATH="./data/schedule_tasks.db"
SCHEDULE_TASK_SAMPLING_TIMEOUT="300000"
```

### 3. 配置 B 站 Cookies

创建 `config/cookies.json`：

```json
{
  "SESSDATA": "your-sessdata",
  "bili_jct": "your-bili-jct",
  "buvid3": "your-buvid3"
}
```

### 4. 运行

```bash
python chat.py
```

## 使用示例

### 基础功能
```
💬 你: 检查新视频
💬 你: 处理 BV1234567890
💬 你: 处理最新视频并发送邮件
```

### 定时任务
```
💬 你: 每天早上9点检查新视频
💬 你: 查看我的定时任务
💬 你: 删除任务 task-xxx
```

## 项目结构

```
juya_openai/
├── chat.py                  # 交互式对话入口
├── juya_agents.py           # Agent 定义
├── tools.py                 # 工具函数
├── modules/                 # 业务模块
│   ├── bilibili_api.py      # B站API封装
│   ├── subtitle_processor_ai.py  # AI字幕处理
│   └── email_sender.py      # 邮件发送
├── config/
│   └── cookies.json         # B站 cookies（需自行配置）
├── data/                    # 数据文件（已处理视频、定时任务数据库）
├── docs/                    # 生成的 Markdown 文档
└── .env                     # 环境变量配置（需自行配置）
```

## 工作流程

```
用户输入 → orchestrator_agent
    ↓
1. check_new_videos（检查新视频）
    ↓
2. process_video（生成 AI 早报）
    ↓
3. send_email_report（发送邮件）
    ↓
返回结果
```

## 开发

### 添加新工具

在 `tools.py` 中定义：

```python
@function_tool
def your_tool(param: Annotated[str, "参数说明"]) -> YourResultModel:
    """工具描述"""
    return YourResultModel(...)
```

在 `juya_agents.py` 中注册：

```python
orchestrator_agent = Agent(
    name="juya_orchestrator",
    model="gpt-4o-mini",
    tools=[check_new_videos, process_video, send_email_report, your_tool]
)
```

## License

MIT
