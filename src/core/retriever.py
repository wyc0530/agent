from typing import Any, Optional

from src.config import logger
from src.core.memory import VectorStore
from src.llm import LLMProvider


class Retriever:
    """RAG 检索引擎：检索相关内容并生成增强回答"""

    def __init__(self) -> None:
        self._store = VectorStore()
        self._llm: Optional[LLMProvider] = None

    @property
    def llm(self) -> LLMProvider:
        if self._llm is None:
            self._llm = LLMProvider()
        return self._llm

    def retrieve(self, query: str, top_k: int = 5, filter_type: Optional[str] = None) -> list[dict[str, Any]]:
        filter_meta = None
        if filter_type:
            filter_meta = {"type": filter_type}
        return self._store.search(query, top_k=top_k, filter_metadata=filter_meta)

    def retrieve_with_web(self, query: str, top_k: int = 5) -> dict[str, Any]:
        internal = self.retrieve(query, top_k=top_k)
        web_results = []
        try:
            from src.core.tools.search import WebSearchTool
            web_tool = WebSearchTool()
            web_results = web_tool.execute(query=query, num_results=3)
        except Exception as e:
            logger.warning(f"Web搜索失败: {e}")

        return {
            "internal": internal,
            "web": web_results,
        }

    def generate_rag_response(
        self,
        query: str,
        context_docs: list[dict[str, Any]],
        system_prompt: str = "",
    ) -> str:
        if not context_docs:
            return self.llm.chat(query, system_prompt=system_prompt or self._default_system_prompt())

        context_text = self._format_context(context_docs)
        rag_prompt = (
            f"{system_prompt or self._default_system_prompt()}\n\n"
            f"## 参考知识库内容\n{context_text}\n\n"
            f"## 请基于以上参考内容回答用户问题\n"
        )
        return self.llm.chat(query, system_prompt=rag_prompt)

    def retrieve_and_generate(
        self,
        query: str,
        top_k: int = 5,
        include_web: bool = False,
    ) -> dict[str, Any]:
        if include_web:
            search_results = self.retrieve_with_web(query, top_k=top_k)
            context_docs = search_results["internal"]
            web_docs = [
                {"content": f"{r['title']}\n{r['snippet']}", "metadata": {"source": r["source"]}}
                for r in search_results["web"]
            ]
            all_docs = context_docs + web_docs
        else:
            all_docs = self.retrieve(query, top_k=top_k)

        response = self.generate_rag_response(query, all_docs)
        return {
            "query": query,
            "response": response,
            "sources": all_docs,
        }

    @staticmethod
    def _format_context(docs: list[dict[str, Any]]) -> str:
        parts = []
        for i, doc in enumerate(docs, 1):
            content = doc.get("content", "")
            score = doc.get("score", 0.0)
            source = doc.get("metadata", {}).get("source", "")
            parts.append(f"[{i}] (相关性: {score:.2f}) {content}")
            if source:
                parts[-1] += f" 来源: {source}"
        return "\n\n".join(parts)

    @staticmethod
    def _default_system_prompt() -> str:
        return (
            "你是一个专业的学习助手，请基于提供的参考内容回答学生的问题。"
            "如果参考内容不足以回答问题，请结合你的知识进行补充，并明确说明。"
            "回答要清晰、有条理，适合学习场景。"
        )

    def check_health(self) -> dict[str, Any]:
        try:
            store_health = self._store.check_health()
            return {
                "status": store_health.get("status", "ok"),
                "document_count": store_health.get("document_count", 0),
                "store_health": store_health,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}


def get_retriever() -> Retriever:
    return Retriever()