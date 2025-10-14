"""
Juya Agent 工具函数
定义所有业务工具函数,供 OpenAI Agents SDK 使用
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Annotated
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from agents import function_tool

from modules.bilibili_api import BilibiliAPI, parse_cookie_string
from modules.subtitle_processor_ai import AISubtitleProcessor
from modules.email_sender import EmailSender


# 加载环境变量
load_dotenv()

# 全局配置
PROJECT_ROOT = Path(__file__).resolve().parent
PROCESSED_VIDEOS_PATH = PROJECT_ROOT / "data" / "processed_videos.json"
DOCS_DIR = PROJECT_ROOT / "docs"
COOKIE_FILE = PROJECT_ROOT / "config" / "cookies.json"

# 创建必要的目录
DOCS_DIR.mkdir(exist_ok=True)
(PROJECT_ROOT / "data").mkdir(exist_ok=True)


# ============= Pydantic Models =============

class VideoInfo(BaseModel):
    """视频信息"""
    bvid: str = Field(description="视频 BV 号")
    title: str = Field(description="视频标题")
    published: str = Field(description="发布时间")


class VideoListResult(BaseModel):
    """视频列表结果"""
    videos: List[VideoInfo] = Field(description="视频列表")
    total: int = Field(description="视频总数")


class ProcessResult(BaseModel):
    """视频处理结果"""
    bvid: str = Field(description="视频 BV 号")
    title: str = Field(description="视频标题")
    markdown_path: str = Field(description="生成的 Markdown 文档路径")
    news_count: int = Field(description="提取的资讯数量")


class EmailResult(BaseModel):
    """邮件发送结果"""
    success: bool = Field(description="是否发送成功")
    message: str = Field(description="发送结果消息")


# ============= 工具辅助函数 =============

def _get_bili_api() -> BilibiliAPI:
    """获取 Bilibili API 实例"""
    if COOKIE_FILE.exists():
        with open(COOKIE_FILE) as f:
            cookies = json.load(f)
    else:
        cookie_str = os.getenv('BILI_COOKIES', '')
        if not cookie_str:
            raise ValueError("未找到 Bilibili cookies 配置")
        cookies = parse_cookie_string(cookie_str)
    return BilibiliAPI(cookies)


def _get_subtitle_processor() -> AISubtitleProcessor:
    """获取字幕处理器实例"""
    return AISubtitleProcessor()


def _get_email_sender() -> EmailSender:
    """获取邮件发送器实例"""
    return EmailSender()


def _load_processed_videos() -> dict:
    """加载已处理视频记录"""
    if PROCESSED_VIDEOS_PATH.exists():
        with open(PROCESSED_VIDEOS_PATH) as f:
            return json.load(f)
    return {}


def _save_processed_videos(data: dict):
    """保存已处理视频记录"""
    with open(PROCESSED_VIDEOS_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _parse_markdown_to_data(md_path: str) -> dict:
    """
    从 Markdown 文件解析出 processed_data 结构（用于生成邮件）

    Args:
        md_path: Markdown 文件路径

    Returns:
        processed_data 字典
    """
    import re

    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 解析元信息
    overview_match = re.search(
        r'# (.+?)\n\n\*\*📅 发布日期：\*\* (.+?)\n\*\*🎬 BV号：\*\* (.+?)\n\*\*📝 整理时间：\*\* (.+?)\n\*\*📊 资讯数量：\*\* (\d+)',
        content
    )

    if not overview_match:
        raise ValueError("无法解析 Markdown 文件的元信息")

    video_title = overview_match.group(1)
    publish_date = overview_match.group(2)
    bvid = overview_match.group(3)
    processed_time = overview_match.group(4)
    total_news = int(overview_match.group(5))

    # 解析每条新闻
    news_items = []
    news_pattern = r'### (\d+)\. (🚀|🔧|📈|📰) (.+?) \{#.+?\}\n\n\*\*标签：\*\* (.+?)\n\n(.+?)(?:\n\n\*\*🔗 相关链接：\*\*\n(.+?))?\n\n---'

    for match in re.finditer(news_pattern, content, re.DOTALL):
        index = int(match.group(1))
        emoji = match.group(2)
        title = match.group(3)
        tags_str = match.group(4)
        news_content = match.group(5).strip()
        links_str = match.group(6)

        # 解析标签
        entities = re.findall(r'`([^`]+)`', tags_str)

        # 解析链接
        sources = []
        if links_str:
            sources = re.findall(r'- (https?://[^\s]+)', links_str)

        # 判断分类
        category_map = {
            '🚀': '产品发布',
            '🔧': '技术更新',
            '📈': '行业动态',
            '📰': '其他'
        }
        category = category_map.get(emoji, '其他')

        news_items.append({
            'index': index,
            'title': title,
            'content': news_content,
            'entities': entities,
            'category': category,
            'sources': sources
        })

    # 构建 processed_data
    processed_data = {
        'overview': {
            'video_title': video_title,
            'bvid': bvid,
            'publish_date': publish_date,
            'processed_time': processed_time,
            'total_news': total_news,
            'summary': f"本期共包含 {total_news} 条资讯"
        },
        'news_items': news_items,
        'raw_subtitles': []
    }

    return processed_data


def _generate_email_html(processed_data: dict) -> str:
    """
    生成精美的HTML邮件内容

    Args:
        processed_data: 处理后的数据结构

    Returns:
        HTML 格式的邮件内容
    """
    overview = processed_data['overview']
    news_items = processed_data['news_items']

    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            background-color: white;
            border-radius: 8px;
            padding: 30px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #1a1a1a;
            border-bottom: 3px solid #4CAF50;
            padding-bottom: 10px;
            font-size: 1.5em;
        }}
        .meta {{
            color: #666;
            font-size: 0.9em;
            margin-bottom: 20px;
        }}
        .overview {{
            background-color: #f8f9fa;
            border-left: 4px solid #4CAF50;
            padding: 15px;
            margin: 20px 0;
            border-radius: 4px;
        }}
        .overview-item {{
            margin: 8px 0;
            padding-left: 10px;
        }}
        .news-item {{
            margin: 20px 0;
            padding: 15px 0;
            border-bottom: 1px solid #e8e8e8;
        }}
        .news-item:last-child {{
            border-bottom: none;
        }}
        .news-item h3 {{
            margin-top: 0;
            margin-bottom: 10px;
            color: #2c3e50;
            font-size: 1.1em;
        }}
        .tags {{
            margin: 10px 0;
        }}
        .tag {{
            display: inline-block;
            background-color: #e3f2fd;
            color: #1976d2;
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 0.85em;
            margin-right: 5px;
        }}
        .sources {{
            margin-top: 10px;
            font-size: 0.9em;
        }}
        .sources a {{
            color: #1976d2;
            text-decoration: none;
        }}
        .sources a:hover {{
            text-decoration: underline;
        }}
        .footer {{
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #e0e0e0;
            text-align: center;
            color: #999;
            font-size: 0.85em;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📺 {overview['video_title']}</h1>

        <div class="meta">
            📅 发布日期：{overview['publish_date']} |
            🎬 BV号：{overview['bvid']} |
            📊 资讯数量：{overview['total_news']} 条
        </div>

        <div class="overview">
            <strong>📋 本期概览</strong>
            <div style="margin-top: 10px;">
"""

    # 概览中列出所有新闻标题（作为目录）
    for item in news_items:
        category_emoji = {
            '产品发布': '🚀',
            '技术更新': '🔧',
            '行业动态': '📈',
            '其他': '📰'
        }.get(item['category'], '📰')
        html += f"""                <div class="overview-item">{item['index']}. {category_emoji} {item['title']}</div>
"""

    html += """            </div>
        </div>
"""

    # 详细内容部分
    for item in news_items:
        category_emoji = {
            '产品发布': '🚀',
            '技术更新': '🔧',
            '行业动态': '📈',
            '其他': '📰'
        }.get(item['category'], '📰')

        html += f"""
        <div class="news-item">
            <h3>{item['index']}. {category_emoji} {item['title']}</h3>
"""

        if item['entities']:
            html += '            <div class="tags">\n'
            for entity in item['entities']:
                html += f'                <span class="tag">{entity}</span>\n'
            html += '            </div>\n'

        html += f"""
            <p>{item['content']}</p>
"""

        if item['sources']:
            html += '            <div class="sources">\n'
            html += '                <strong>🔗 相关链接：</strong><br>\n'
            for link in item['sources']:
                html += f'                • <a href="{link}" target="_blank">{link}</a><br>\n'
            html += '            </div>\n'

        html += '        </div>\n'

    html += f"""
        <div style="margin-top: 30px; padding: 20px; background-color: #f0f8ff; border-radius: 8px; text-align: center;">
            <h3 style="margin-top: 0;">🎬 观看视频</h3>
            <p style="margin: 10px 0;">
                <a href="https://www.bilibili.com/video/{overview['bvid']}"
                   style="display: inline-block; background-color: #00a1d6; color: white; padding: 10px 20px;
                          border-radius: 5px; text-decoration: none; font-weight: bold;">
                    在 Bilibili 观看完整视频
                </a>
            </p>
            <p style="font-size: 0.9em; color: #666;">BV号：{overview['bvid']}</p>
        </div>

        <div class="footer">
            整理自橘鸦AI早报 | {overview['processed_time']}
        </div>
    </div>
</body>
</html>
"""

    return html


# ============= Agent 工具函数 =============

@function_tool
def check_new_videos(count: Annotated[int, "检查最近的视频数量，默认 10 个"] = 10) -> VideoListResult:
    """
    检查是否有新视频（未处理的视频）

    Args:
        count: 检查最近的视频数量，默认 10 个

    Returns:
        VideoListResult: 新视频列表
    """
    api = _get_bili_api()
    videos = api.get_user_videos(uid=285286947, page_size=count)
    processed = _load_processed_videos()

    new_videos = []
    for v in videos:
        if v['bvid'] not in processed:
            new_videos.append(VideoInfo(
                bvid=v['bvid'],
                title=v['title'],
                published=datetime.fromtimestamp(v['created']).strftime('%Y-%m-%d %H:%M:%S')
            ))

    return VideoListResult(videos=new_videos, total=len(new_videos))


@function_tool
def process_video(
    bvid: Annotated[str, "视频 BV 号"],
    force_regenerate: Annotated[bool, "是否强制重新生成"] = False
) -> ProcessResult:
    """
    处理单个视频：获取字幕、智能整理、保存 Markdown 文档

    如果文档已存在且 force_regenerate=False，则直接返回已有文档信息，不重新处理。

    Args:
        bvid: 视频 BV 号
        force_regenerate: 是否强制重新生成（默认 False）

    Returns:
        ProcessResult: 处理结果，包含文档路径等信息
    """
    api = _get_bili_api()
    processor = _get_subtitle_processor()

    # 先获取视频信息以构建文档路径
    video_info = api.get_video_info(bvid)
    video_date = datetime.fromtimestamp(video_info['pubdate'])
    date_str = video_date.strftime('%Y-%m-%d')
    filename = f"{bvid}_{date_str}_AI早报.md"
    filepath = DOCS_DIR / filename

    # 检查文档文件是否已存在
    if not force_regenerate and filepath.exists():
        # 文档已存在，直接返回已有信息
        print(f"📄 文档已存在，跳过重新生成: {filepath}")

        # 从已存在的文档中解析资讯数量
        try:
            processed_data = _parse_markdown_to_data(str(filepath))
            news_count = processed_data['overview']['total_news']
        except Exception as e:
            print(f"⚠️ 解析文档失败: {e}")
            news_count = 0  # 解析失败时返回 0

        # 确保记录在 processed_videos.json 中
        processed_videos = _load_processed_videos()
        if bvid not in processed_videos:
            processed_videos[bvid] = {
                'title': video_info['title'],
                'processed_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'subtitle_path': str(filepath)
            }
            _save_processed_videos(processed_videos)

        return ProcessResult(
            bvid=bvid,
            title=video_info['title'],
            markdown_path=str(filepath),
            news_count=news_count
        )

    # 需要处理：文档不存在 或 强制重新生成
    if force_regenerate:
        print(f"🔄 强制重新生成文档...")

    # 获取字幕
    subtitle = api.get_subtitle(bvid)

    # 处理字幕（如果没有字幕，会使用视频简介作为备用）
    if not subtitle:
        print(f"⚠️ 视频 {bvid} 没有字幕，将使用视频简介提取新闻...")

    processed_data = processor.process(subtitle if subtitle else [], video_info)

    # 生成 Markdown
    markdown = processor.format_markdown(processed_data)

    # 保存文档
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(markdown)

    # 更新已处理记录
    processed_videos = _load_processed_videos()
    processed_videos[bvid] = {
        'title': video_info['title'],
        'processed_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'subtitle_path': str(filepath)
    }
    _save_processed_videos(processed_videos)

    print(f"✅ 文档已生成: {filepath}")

    return ProcessResult(
        bvid=bvid,
        title=video_info['title'],
        markdown_path=str(filepath),
        news_count=processed_data['overview']['total_news']
    )


@function_tool
def send_email_report(
    bvid: Annotated[str, "视频 BV 号"],
    to_email: Annotated[str, "收件人邮箱（可选，默认使用环境变量）"] = None
) -> EmailResult:
    """
    发送邮件报告

    Args:
        bvid: 视频 BV 号
        to_email: 收件人邮箱（默认使用环境变量 EMAIL_TO）

    Returns:
        EmailResult: 邮件发送结果
    """
    to_email = to_email or os.getenv('EMAIL_TO')
    if not to_email:
        return EmailResult(success=False, message="未配置收件人邮箱")

    try:
        api = _get_bili_api()
        sender = _get_email_sender()

        # 检查是否有已处理的数据
        processed_videos = _load_processed_videos()

        if bvid in processed_videos:
            md_path = processed_videos[bvid].get('subtitle_path')
            if md_path and os.path.exists(md_path):
                # 从 Markdown 文件解析数据
                processed_data = _parse_markdown_to_data(md_path)

                # 生成精美的 HTML 邮件
                html_content = _generate_email_html(processed_data)

                video_info = api.get_video_info(bvid)

                success = sender.send_video_report(
                    to_email=to_email,
                    video_title=video_info['title'],
                    bvid=bvid,
                    html_content=html_content,
                    markdown_path=md_path
                )

                if success:
                    return EmailResult(success=True, message=f"邮件已发送到 {to_email}")
                else:
                    return EmailResult(success=False, message="邮件发送失败")

        return EmailResult(success=False, message=f"视频 {bvid} 尚未处理")

    except Exception as e:
        return EmailResult(success=False, message=f"发送邮件失败: {str(e)}")
