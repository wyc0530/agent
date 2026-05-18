import urllib.parse
from typing import Any

import requests

from src.config import Settings, logger
from src.core.tools.base import BaseTool, ToolCategory, ToolMetadata, ToolPermission


class WebSearchTool(BaseTool):
    metadata = ToolMetadata(
        name="web_search",
        description="搜索互联网获取学习资料、课程信息和相关知识。支持多源搜索和结果过滤。",
        category=ToolCategory.SEARCH,
        permission=ToolPermission.READ_ONLY,
        version="1.0.0",
        tags=["search", "web", "learning"],
        input_schema={
            "query": {"type": "string", "description": "搜索关键词"},
            "num_results": {"type": "integer", "description": "返回结果数量", "default": 5},
            "source": {"type": "string", "description": "搜索来源", "default": "web"},
        },
    )

    def execute(self, **kwargs) -> list[dict[str, Any]]:
        query = kwargs.get("query", "")
        num_results = kwargs.get("num_results", Settings.SEARCH_MAX_RESULTS)

        if not query:
            return []

        results = []
        if Settings.SERPAPI_API_KEY and Settings.SERPAPI_API_KEY != "your-serpapi-key-here":
            try:
                results = self._search_serpapi(query, num_results)
            except Exception as e:
                logger.warning(f"SerpAPI 搜索失败: {e}")
                results = self._search_fallback(query, num_results)
        else:
            results = self._search_fallback(query, num_results)

        return results[:num_results]

    def _search_serpapi(self, query: str, num: int) -> list[dict[str, Any]]:
        base_url = "https://serpapi.com/search"
        params = {
            "q": query,
            "api_key": Settings.SERPAPI_API_KEY,
            "engine": "google",
            "num": min(num, 10),
            "hl": "zh-CN",
        }
        response = requests.get(base_url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()

        results = []
        for item in data.get("organic_results", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "snippet": item.get("snippet", ""),
                "source": item.get("source", "web"),
            })
        return results

    def _search_fallback(self, query: str, num: int) -> list[dict[str, Any]]:
        return self._search_course_directories(query, num)

    def _search_course_directories(self, query: str, num: int) -> list[dict[str, Any]]:
        platforms = {
            "中国大学MOOC": f"https://www.icourse163.org/search.htm?search={urllib.parse.quote(query)}",
            "B站": f"https://search.bilibili.com/all?keyword={urllib.parse.quote(query)}",
            "知乎": f"https://www.zhihu.com/search?type=content&q={urllib.parse.quote(query)}",
            "CSDN": f"https://so.csdn.net/so/search?q={urllib.parse.quote(query)}",
        }

        results = []
        for platform, url in platforms.items():
            results.append({
                "title": f"[{platform}] 搜索: {query}",
                "url": url,
                "snippet": f"在{platform}上搜索「{query}」相关内容",
                "source": platform,
            })
            if len(results) >= num:
                break
        return results


class MultiSourceSearcher:
    def __init__(self) -> None:
        self._web_tool = WebSearchTool()
        self._sources: list[str] = ["web", "course", "paper", "qa"]

    def search_all(self, query: str, num_per_source: int = 3) -> dict[str, list[dict[str, Any]]]:
        result: dict[str, list[dict[str, Any]]] = {}
        result["web"] = self._web_tool.execute(query=query, num_results=num_per_source)
        return result

    def search_single(self, query: str, source: str = "web", num: int = 5) -> list[dict[str, Any]]:
        if source == "web":
            return self._web_tool.execute(query=query, num_results=num)
        return []