"""
AI驱动的字幕处理模块
使用 GLM API 智能提炼新闻要点、生成概览和提取来源链接
"""

import os
import re
from datetime import datetime
from typing import List, Dict, Optional
from zhipuai import ZhipuAI
from dotenv import load_dotenv

load_dotenv()


class AISubtitleProcessor:
    """AI驱动的字幕智能处理器"""

    def __init__(self):
        self.client = ZhipuAI(api_key=os.getenv("GLM_API_KEY"))

    def process(self, subtitle_data: List[Dict], video_info: Dict) -> Dict:
        """
        使用AI处理字幕数据，生成结构化的新闻报告

        Args:
            subtitle_data: 字幕列表，每项包含 from, to, content（可以为空，使用简介作为备用）
            video_info: 视频信息，包含 bvid, title, desc 等

        Returns:
            处理后的结构化数据
        """
        # 提取视频描述中的链接
        desc_links = self._extract_links_from_desc(video_info.get('desc', ''))

        # 如果有字幕，使用字幕提取新闻
        if subtitle_data:
            # 1. 合并字幕文本
            full_text = self._merge_subtitles(subtitle_data)

            # 2. 使用AI提炼新闻内容
            news_items = self._ai_extract_news(full_text, subtitle_data, desc_links)
        else:
            # 没有字幕时，使用视频简介作为备用
            print("⚠️ 没有字幕，使用视频简介提取新闻...")
            news_items = self._extract_news_from_description(video_info.get('desc', ''), desc_links)

        # 3. 生成概览
        overview_text = self._ai_generate_overview(news_items, video_info)

        # 4. 构建最终结构
        overview = {
            'summary': overview_text,
            'total_news': len(news_items),
            'video_title': video_info.get('title', ''),
            'bvid': video_info.get('bvid', ''),
            'publish_date': datetime.fromtimestamp(video_info.get('pubdate', 0)).strftime('%Y-%m-%d'),
            'processed_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        return {
            'overview': overview,
            'news_items': news_items,
            'raw_subtitles': subtitle_data if subtitle_data else []
        }

    def _merge_subtitles(self, subtitles: List[Dict]) -> str:
        """合并字幕为完整文本"""
        return ' '.join([s['content'] for s in subtitles])

    def _extract_links_from_desc(self, desc: str) -> List[Dict[str, any]]:
        """从视频描述中提取链接（带标题和时间戳）"""
        links_with_context = []

        # 按行分割描述
        lines = desc.split('\n')
        current_title = None
        current_time = None

        for line in lines:
            line = line.strip()

            # 匹配标题行：⬛️ 标题: 时间
            title_match = re.match(r'⬛️\s+(.+?):\s+(\d+:\d+)', line)
            if title_match:
                current_title = title_match.group(1).strip()
                current_time = title_match.group(2).strip()
                continue

            # 匹配链接行：🔗 https://...
            link_match = re.match(r'🔗\s+(https?://[^\s]+)', line)
            if link_match and current_title:
                links_with_context.append({
                    'title': current_title,
                    'time': current_time,
                    'url': link_match.group(1).strip()
                })

        return links_with_context

    def _ai_extract_news(self, full_text: str, subtitles: List[Dict], desc_links: List[Dict]) -> List[Dict]:
        """使用AI提炼新闻条目"""

        prompt = f"""你是一个专业的AI资讯编辑。请从以下AI早报的字幕文本中，提炼出结构化的新闻条目。

字幕文本：
{full_text}

要求：
1. 识别并提取每一条独立的AI新闻
2. 为每条新闻生成一个精炼的标题（10-25字，简洁明了）
3. 写一段详细的新闻报道，尽可能详细地包含：
   - 核心事件描述（什么公司/产品发布/更新了什么）
   - 关键功能、特性、技术细节的详细说明
   - 使用场景、应用价值或行业影响
   - 保留字幕中提到的所有具体数据、版本号、时间点、技术术语
4. 提取相关的公司/产品/技术名称（2-3个主要实体）
5. 保持专业客观的语气，提供充分信息量

内容写作要求：
- 详细展开每个要点，不要概括性描述
- 将字幕中的技术细节完整保留并展开说明
- 多用"功能包括"、"特点是"、"支持"等词汇来展开内容
- 避免"此外"、"同时"等生硬连接词，改用自然衔接
- 尽可能详细，但保持内容的可读性和专业性

输出JSON格式：
{{
  "news": [
    {{
      "title": "新闻标题",
      "content": "详细新闻内容（150-300字）",
      "entities": ["公司/产品名"],
      "category": "产品发布|技术更新|行业动态|其他"
    }}
  ]
}}

只返回JSON，不要其他解释。"""

        try:
            response = self.client.chat.completions.create(
                model="glm-4-plus",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                timeout=90  # 90秒超时
            )

            result_text = response.choices[0].message.content.strip()

            # 提取JSON（去除可能的markdown代码块标记）
            if result_text.startswith('```'):
                result_text = result_text.split('```')[1]
                if result_text.startswith('json'):
                    result_text = result_text[4:]

            import json
            result = json.loads(result_text)

            news_items = []
            for idx, news in enumerate(result.get('news', [])):
                # 尝试从描述链接中匹配相关链接
                source_links = self._match_links_for_news(news, desc_links)

                news_items.append({
                    'title': news.get('title', ''),
                    'content': news.get('content', ''),
                    'entities': news.get('entities', []),
                    'category': news.get('category', '其他'),
                    'sources': source_links,
                    'index': idx + 1
                })

            return news_items

        except Exception as e:
            print(f"AI提取失败: {e}")
            # 降级为简单提取
            return self._simple_extract_news(subtitles)

    def _match_links_for_news(self, news: Dict, desc_links: List[Dict]) -> List[str]:
        """尝试为新闻匹配相关链接"""
        matched_links = []

        # 策略：基于标题相似度匹配
        news_title = news.get('title', '').lower()
        news_content = news.get('content', '').lower()
        news_entities = [e.lower() for e in news.get('entities', [])]

        for link_item in desc_links:
            desc_title = link_item['title'].lower()
            url = link_item['url']

            # 计算相似度
            score = 0

            # 1. 实体匹配
            for entity in news_entities:
                if entity in desc_title:
                    score += 3

            # 2. 标题关键词匹配
            news_words = set(news_title.split())
            desc_words = set(desc_title.split())
            common_words = news_words & desc_words
            score += len(common_words)

            # 3. 内容关键词匹配
            if any(word in news_content for word in desc_title.split()):
                score += 1

            if score >= 2:  # 阈值
                matched_links.append(url)

        return matched_links[:3]  # 最多3个链接


    def _ai_generate_overview(self, news_items: List[Dict], video_info: Dict) -> str:
        """使用AI生成本期概览"""

        # 构建新闻列表
        news_list = '\n'.join([f"{i}. {item['title']}" for i, item in enumerate(news_items, 1)])

        prompt = f"""你是AI资讯编辑，请为这期AI早报写一段简洁的概览（60-120字）。

视频标题：{video_info.get('title', '')}
新闻列表：
{news_list}

要求：
1. 用2-3句话概括本期核心内容
2. 突出最重要的1-2条新闻的关键词
3. 简洁、信息密度高，不要冗余修饰
4. 避免使用"本期"、"今天"、"此外"、"同时"等词
5. 直接陈述事实，不要评论性语言

只返回概览文本，不要其他内容。"""

        try:
            response = self.client.chat.completions.create(
                model="glm-4-plus",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
                timeout=60  # 60秒超时
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            print(f"AI生成概览失败: {e}")
            return f"本期AI早报共包含 {len(news_items)} 条资讯，涵盖AI领域的最新动态。"

    def _extract_news_from_description(self, description: str, desc_links: List[Dict]) -> List[Dict]:
        """
        从视频简介中提取新闻（备用方案，当没有字幕时使用）

        Args:
            description: 视频简介文本
            desc_links: 从简介中提取的链接列表

        Returns:
            新闻列表
        """
        if not description or len(description.strip()) < 50:
            print("⚠️ 视频简介内容太少，无法提取新闻")
            return []

        prompt = f"""你是一个专业的AI资讯编辑。请从以下视频简介中，提炼出结构化的新闻条目。

视频简介：
{description}

要求：
1. 识别并提取每一条独立的AI新闻（简介中通常会列出多条新闻）
2. 为每条新闻生成一个精炼的标题（10-25字，简洁明了）
3. 写一段详细的新闻报道，尽可能详细地包含：
   - 核心事件描述（什么公司/产品发布/更新了什么）
   - 从简介中能推断出的关键功能、特性
   - 可能的应用价值或影响
   - 保留简介中的具体数据、版本号、时间点、技术术语
4. 提取相关的公司/产品/技术名称（2-3个主要实体）
5. 保持专业客观的语气

注意：
- 简介通常会用"⬛️"或数字标注每条新闻
- 简介可能比字幕简短，请根据有限信息合理补充内容
- 详细展开每个要点，但不要编造不存在的信息

输出JSON格式：
{{
  "news": [
    {{
      "title": "新闻标题",
      "content": "详细新闻内容",
      "entities": ["公司/产品名"],
      "category": "产品发布|技术更新|行业动态|其他"
    }}
  ]
}}

只返回JSON，不要其他解释。"""

        try:
            response = self.client.chat.completions.create(
                model="glm-4-plus",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                timeout=90  # 90秒超时
            )

            result_text = response.choices[0].message.content.strip()

            # 提取JSON
            if result_text.startswith('```'):
                result_text = result_text.split('```')[1]
                if result_text.startswith('json'):
                    result_text = result_text[4:]

            import json
            result = json.loads(result_text)

            news_items = []
            for idx, news in enumerate(result.get('news', [])):
                # 尝试从描述链接中匹配相关链接
                source_links = self._match_links_for_news(news, desc_links)

                news_items.append({
                    'title': news.get('title', ''),
                    'content': news.get('content', ''),
                    'entities': news.get('entities', []),
                    'category': news.get('category', '其他'),
                    'sources': source_links,
                    'index': idx + 1
                })

            print(f"✅ 从视频简介中提取到 {len(news_items)} 条新闻")
            return news_items

        except Exception as e:
            print(f"从简介提取新闻失败: {e}")
            # 如果AI提取失败，返回空列表
            return []

    def format_markdown(self, processed_data: Dict) -> str:
        """
        将处理后的数据格式化为精美的 Markdown

        Args:
            processed_data: process() 返回的结构化数据

        Returns:
            Markdown 格式的文本
        """
        overview = processed_data['overview']
        news_items = processed_data['news_items']

        md_lines = []

        # 标题
        md_lines.append(f"# {overview['video_title']}\n")

        # 元信息
        md_lines.append(f"**📅 发布日期：** {overview['publish_date']}")
        md_lines.append(f"**🎬 BV号：** {overview['bvid']}")
        md_lines.append(f"**📝 整理时间：** {overview['processed_time']}")
        md_lines.append(f"**📊 资讯数量：** {overview['total_news']} 条\n")
        md_lines.append("---\n")

        # 概览（同时作为目录）
        md_lines.append("## 📋 本期概览\n")
        for item in news_items:
            category_emoji = {
                '产品发布': '🚀',
                '技术更新': '🔧',
                '行业动态': '📈',
                '其他': '📰'
            }.get(item['category'], '📰')
            md_lines.append(f"{item['index']}. {category_emoji} {item['title']}")
        md_lines.append("\n---\n")

        # 详细内容（不需要标题）

        for item in news_items:
            category_emoji = {
                '产品发布': '🚀',
                '技术更新': '🔧',
                '行业动态': '📈',
                '其他': '📰'
            }.get(item['category'], '📰')

            md_lines.append(f"### {item['index']}. {category_emoji} {item['title']} {{#{item['index']}-{self._slugify(item['title'])}}}\n")

            # 标签
            if item['entities']:
                tags = ' '.join([f"`{entity}`" for entity in item['entities']])
                md_lines.append(f"**标签：** {tags}\n")

            # 详细内容
            md_lines.append(f"{item['content']}\n")

            # 来源链接
            if item['sources']:
                md_lines.append("**🔗 相关链接：**")
                for link in item['sources']:
                    md_lines.append(f"- {link}")
                md_lines.append("")

            md_lines.append("---\n")

        # 页脚
        md_lines.append("---\n")
        md_lines.append("## 🎬 视频链接\n")
        md_lines.append(f"**Bilibili：** https://www.bilibili.com/video/{overview['bvid']}\n")
        md_lines.append("---\n")
        md_lines.append(f"*整理自橘鸦AI早报 | BV号：{overview['bvid']} | {overview['processed_time']}*")

        return '\n'.join(md_lines)

    def _slugify(self, text: str) -> str:
        """将标题转为URL友好的slug"""
        # 简单实现：只保留字母数字
        return re.sub(r'[^\w\s-]', '', text).strip().replace(' ', '-')[:30]

    def generate_email_html(self, processed_data: Dict) -> str:
        """
        生成精美的HTML邮件内容

        Args:
            processed_data: process() 返回的结构化数据

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

        # 详细内容部分（不需要 h2 标题）
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
