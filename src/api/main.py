from contextlib import asynccontextmanager
import threading
import time
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware

from src.config import Settings, logger
from src.core.memory import VectorStore
from src.core.retriever import Retriever
from src.embedding import EmbeddingProvider
from src.llm import LLMProvider


_RATE_LIMIT: dict[str, list[float]] = {}
_RATE_LOCK = threading.Lock()
_RATE_WINDOW = 60
_RATE_MAX_REQUESTS = 100
_PUBLIC_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path in _PUBLIC_PATHS:
            return await call_next(request)

        client = request.client.host if request.client else "unknown"
        now = time.time()
        with _RATE_LOCK:
            if client not in _RATE_LIMIT:
                _RATE_LIMIT[client] = []
            _RATE_LIMIT[client] = [t for t in _RATE_LIMIT[client] if now - t < _RATE_WINDOW]

            if len(_RATE_LIMIT[client]) >= _RATE_MAX_REQUESTS:
                logger.warning(f"速率限制触发 | client={client}")
                return JSONResponse(
                    status_code=429,
                    content={"detail": "请求过于频繁，请在1分钟后重试"},
                )

            _RATE_LIMIT[client].append(now)
        return await call_next(request)


class ChatRequest(BaseModel):
    message: str = Field(description="用户消息")
    user_id: str = Field(default="default_user", description="用户ID")
    thread_id: str = Field(default="default_thread", description="对话线程ID")
    system_prompt: str = Field(default="", description="系统提示词")


class ChatResponse(BaseModel):
    response: str = Field(description="AI回复")
    agent_role: str = Field(default="assistant", description="处理Agent")


class SearchRequest(BaseModel):
    query: str = Field(description="搜索关键词")
    top_k: int = Field(default=5, description="返回数量")
    include_web: bool = Field(default=False, description="是否包含网络搜索")


class MemoryStoreRequest(BaseModel):
    content: str = Field(description="要存储的内容")
    user_id: str = Field(default="default_user", description="用户ID")
    memory_type: str = Field(default="interaction", description="记忆类型")


class EmbedRequest(BaseModel):
    texts: list[str] = Field(description="待向量化的文本列表", max_length=100)


class GraphSearchRequest(BaseModel):
    keyword: str = Field(description="搜索关键词")
    limit: int = Field(default=20, description="返回数量")


class GraphPathRequest(BaseModel):
    start_node_id: str = Field(description="起始节点ID")
    target_node_id: str = Field(description="目标节点ID")
    max_depth: int = Field(default=5, description="最大搜索深度")


class HealthResponse(BaseModel):
    status: str
    version: str = "1.0.0"
    components: dict[str, Any] = Field(default_factory=dict)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 50)
    logger.info("学习辅助系统 API 启动中...")
    logger.info(Settings.display())

    from src.core.tools.base import register_all_tools
    register_all_tools()
    logger.info("全部工具已自动注册")

    logger.info("=" * 50)
    yield
    logger.info("学习辅助系统 API 关闭")


app = FastAPI(
    title="学习辅助系统 API",
    description="基于 LangGraph 的多智能体学习辅助系统",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if Settings.DEBUG else ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

app.add_middleware(RateLimitMiddleware)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    components = {}
    try:
        llm = LLMProvider()
        components["llm"] = llm.check_health()
    except Exception as e:
        components["llm"] = {"status": "uninitialized", "error": str(e)}

    try:
        embedding = EmbeddingProvider()
        components["embedding"] = embedding.check_health()
    except Exception as e:
        components["embedding"] = {"status": "uninitialized", "error": str(e)}

    try:
        store = VectorStore()
        components["vector_store"] = store.check_health()
    except Exception as e:
        components["vector_store"] = {"status": "uninitialized", "error": str(e)}

    try:
        retriever = Retriever()
        components["retriever"] = retriever.check_health()
    except Exception as e:
        components["retriever"] = {"status": "uninitialized", "error": str(e)}

    try:
        from src.core.graph import get_graph_store
        graph = get_graph_store()
        components["graph_store"] = graph.check_health()
    except Exception as e:
        components["graph_store"] = {"status": "uninitialized", "error": str(e)}

    try:
        from src.core.checkpoint import get_checkpoint_manager, get_summarizer
        checkpoint = get_checkpoint_manager()
        components["checkpoint"] = checkpoint.check_health()
        summarizer = get_summarizer()
        components["summarizer"] = summarizer.check_health()
    except Exception as e:
        components["checkpoint"] = {"status": "uninitialized", "error": str(e)}

    all_ok = all(
        c.get("status") in ("ok", "passed")
        for c in components.values()
        if isinstance(c, dict)
    )
    return HealthResponse(
        status="healthy" if all_ok else "degraded",
        components=components,
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        llm = LLMProvider()
        response = llm.chat(request.message, system_prompt=request.system_prompt)
        return ChatResponse(response=response, agent_role="assistant")
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search")
async def search(request: SearchRequest):
    try:
        retriever = Retriever()
        result = retriever.retrieve_and_generate(
            query=request.query,
            top_k=request.top_k,
            include_web=request.include_web,
        )
        return result
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/embed")
async def embed_texts(request: EmbedRequest):
    try:
        embedding = EmbeddingProvider()
        vectors = embedding.embed_batch(request.texts)
        return {
            "count": len(vectors),
            "dimension": len(vectors[0]) if vectors else 0,
            "vectors": vectors,
        }
    except Exception as e:
        logger.error(f"Embed error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tools")
async def list_tools():
    try:
        from src.core.tools.base import get_tool_registry
        registry = get_tool_registry()
        return {"tools": registry.list_all()}
    except Exception as e:
        logger.error(f"Tools error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/memory/store")
async def store_memory(request: MemoryStoreRequest):
    try:
        from src.core.memory import LongTermMemory
        memory = LongTermMemory(user_id=request.user_id)
        doc_id = memory.store_learning_material(request.content, request.memory_type)
        return {"status": "stored", "doc_id": doc_id}
    except Exception as e:
        logger.error(f"Memory store error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/graph/stats")
async def graph_stats():
    try:
        from src.core.graph import get_graph_store
        graph = get_graph_store()
        return graph.get_stats()
    except Exception as e:
        logger.error(f"Graph stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/graph/search")
async def graph_search(request: GraphSearchRequest):
    try:
        from src.core.graph import get_graph_store
        graph = get_graph_store()
        nodes = graph.search_nodes(keyword=request.keyword, limit=request.limit)
        return {"keyword": request.keyword, "count": len(nodes), "nodes": nodes}
    except Exception as e:
        logger.error(f"Graph search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/graph/path")
async def graph_path(request: GraphPathRequest):
    try:
        from src.core.graph import get_graph_store
        graph = get_graph_store()
        path = graph.build_learning_path(
            start_node_id=request.start_node_id,
            target_node_id=request.target_node_id,
            max_depth=request.max_depth,
        )
        return {"start": request.start_node_id, "target": request.target_node_id, "path": path}
    except Exception as e:
        logger.error(f"Graph path error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def main():
    import uvicorn
    uvicorn.run(
        "src.api.main:app",
        host=Settings.HOST,
        port=Settings.PORT,
        reload=Settings.DEBUG,
        log_level=Settings.LOG_LEVEL.lower(),
    )


if __name__ == "__main__":
    main()