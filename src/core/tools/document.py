import json
from datetime import datetime
from io import StringIO
from typing import Any

from src.config import logger
from src.core.tools.base import BaseTool, ToolCategory, ToolMetadata, ToolPermission


class DocumentGenerator(BaseTool):
    metadata = ToolMetadata(
        name="document_generator",
        description="生成结构化的学习方案、课程推荐、错题报告等文档内容。输出Markdown表格或JSON格式。",
        category=ToolCategory.DOCUMENT,
        permission=ToolPermission.READ_ONLY,
        version="1.0.0",
        tags=["document", "markdown", "table", "report"],
    )

    def execute(self, **kwargs) -> dict[str, Any]:
        doc_type = kwargs.get("doc_type", "markdown")
        data = kwargs.get("data", {})
        title = kwargs.get("title", "文档")

        if doc_type == "learning_plan":
            return self._generate_learning_plan(data, title)
        elif doc_type == "course_recommendation":
            return self._generate_course_table(data, title)
        elif doc_type == "error_report":
            return self._generate_error_report(data, title)
        elif doc_type == "markdown":
            return self._generate_markdown(data, title)
        elif doc_type == "json":
            return {"content": json.dumps(data, ensure_ascii=False, indent=2), "format": "json"}
        else:
            return {"content": str(data), "format": "text"}

    def _generate_learning_plan(self, data: dict, title: str) -> dict[str, Any]:
        buf = StringIO()
        buf.write(f"# {title}\n\n")
        buf.write(f"*生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n\n")

        goals = data.get("goals", [])
        if goals:
            buf.write("## 学习目标\n\n")
            for g in goals:
                buf.write(f"- **{g.get('title', '')}**: {g.get('description', '')}\n")
            buf.write("\n")

        phases = data.get("phases", [])
        if phases:
            buf.write("## 学习阶段\n\n")
            buf.write("| 阶段 | 主题 | 内容 | 预计天数 |\n")
            buf.write("|------|------|------|----------|\n")
            for p in phases:
                buf.write(f"| {p.get('phase_id', '')} | {p.get('title', '')} | ")
                topics = ", ".join(p.get("topics", []))
                buf.write(f"{topics} | {p.get('duration_days', '')} |\n")
            buf.write("\n")

        buf.write("## 学习建议\n\n")
        buf.write(data.get("suggestions", "根据学习方案稳步推进，保持每天学习的节奏。\n"))

        logger.info(f"学习方案文档生成 | title={title}")
        return {"content": buf.getvalue(), "format": "markdown", "title": title}

    def _generate_course_table(self, data: dict, title: str) -> dict[str, Any]:
        buf = StringIO()
        buf.write(f"# {title}\n\n")
        buf.write(f"*推荐时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n\n")

        materials = data.get("materials", [])
        if materials:
            buf.write("| 序号 | 资料名称 | 来源 | 类型 | 说明 |\n")
            buf.write("|------|----------|------|------|------|\n")
            for i, m in enumerate(materials, 1):
                buf.write(f"| {i} | [{m.get('title', '')}]({m.get('url', '')}) | ")
                buf.write(f"{m.get('source', '')} | {m.get('content_type', '')} | ")
                buf.write(f"{m.get('description', '')} |\n")

        buf.write("\n## 学习建议\n\n")
        buf.write(data.get("suggestions", "建议按照顺序逐步学习以上推荐资料。"))

        logger.info(f"课程推荐文档生成 | title={title}")
        return {"content": buf.getvalue(), "format": "markdown", "title": title}

    def _generate_error_report(self, data: dict, title: str) -> dict[str, Any]:
        buf = StringIO()
        buf.write(f"# {title}\n\n")
        buf.write(f"*生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n\n")

        weak_points = data.get("weak_points", [])
        if weak_points:
            buf.write("## 易错点分析\n\n")
            buf.write("| 知识点 | 错误率 | 错误次数 | 总尝试 | 需复习 |\n")
            buf.write("|--------|--------|----------|--------|--------|\n")
            for wp in weak_points:
                buf.write(f"| {wp.get('knowledge_point', '')} | ")
                buf.write(f"{wp.get('error_rate', 0):.1%} | ")
                buf.write(f"{wp.get('error_count', 0)} | ")
                buf.write(f"{wp.get('total_attempts', 0)} | ")
                buf.write(f"{'是' if wp.get('need_review') else '否'} |\n")

        errors = data.get("error_records", [])
        if errors:
            buf.write("\n## 错题详情\n\n")
            for i, e in enumerate(errors, 1):
                q = e.get("question", {})
                buf.write(f"### {i}. {q.get('content', '未知题目')}\n\n")
                buf.write(f"- 正确答案: {q.get('answer', '')}\n")
                buf.write(f"- 你的答案: {e.get('user_answer', '')}\n")
                buf.write(f"- 解析: {q.get('explanation', '暂无解析')}\n")
                buf.write(f"- 错误次数: {e.get('error_count', 1)}\n\n")

        buf.write("## 复习建议\n\n")
        buf.write(data.get("suggestions", "重点复习以上易错知识点，建议隔天回顾错题。"))

        logger.info(f"错题报告生成 | title={title}")
        return {"content": buf.getvalue(), "format": "markdown", "title": title}

    def _generate_markdown(self, data: dict, title: str) -> dict[str, Any]:
        content = data.get("raw", "")
        if isinstance(content, list):
            content = "\n".join(f"- {item}" for item in content)
        return {
            "content": f"# {title}\n\n{content}",
            "format": "markdown",
            "title": title,
        }