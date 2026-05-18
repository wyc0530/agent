import os
import logging
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent.resolve()

load_dotenv(PROJECT_ROOT / ".env")


class Settings:
    PROJECT_ROOT: Path = PROJECT_ROOT

    # --- LLM ---
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openai")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.7"))
    LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "4096"))

    # --- 本地 LLM ---
    LOCAL_LLM_ENABLED: bool = os.getenv("LOCAL_LLM_ENABLED", "false").lower() == "true"
    LOCAL_LLM_MODEL: str = os.getenv("LOCAL_LLM_MODEL", "Qwen/Qwen2.5-7B-Instruct")
    LOCAL_LLM_BASE_URL: str = os.getenv("LOCAL_LLM_BASE_URL", "http://localhost:1234/v1")
    LOCAL_LLM_PATH: str = os.getenv("LOCAL_LLM_PATH", "./models/llm")
    LOCAL_LLM_DEVICE: str = os.getenv("LOCAL_LLM_DEVICE", "cpu")
    LOCAL_LLM_QUANTIZATION: Optional[str] = os.getenv("LOCAL_LLM_QUANTIZATION", "int8")

    # --- 百炼 Embedding ---
    EMBEDDING_PROVIDER: str = os.getenv("EMBEDDING_PROVIDER", "bailian")
    DASHSCOPE_API_KEY: str = os.getenv("DASHSCOPE_API_KEY", "")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-v3")
    EMBEDDING_DIMENSION: int = int(os.getenv("EMBEDDING_DIMENSION", "1024"))

    # --- 本地 Embedding ---
    LOCAL_EMBEDDING_ENABLED: bool = os.getenv("LOCAL_EMBEDDING_ENABLED", "false").lower() == "true"
    LOCAL_EMBEDDING_MODEL: str = os.getenv("LOCAL_EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")
    LOCAL_EMBEDDING_PATH: str = os.getenv("LOCAL_EMBEDDING_PATH", "./models/embedding")
    LOCAL_EMBEDDING_DEVICE: str = os.getenv("LOCAL_EMBEDDING_DEVICE", "cpu")

    # --- Qdrant 向量数据库 ---
    VECTOR_DB_TYPE: str = os.getenv("VECTOR_DB_TYPE", "qdrant")
    QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost")
    QDRANT_PORT: int = int(os.getenv("QDRANT_PORT", "6333"))
    QDRANT_API_KEY: Optional[str] = os.getenv("QDRANT_API_KEY", "")
    QDRANT_USE_LOCAL: bool = os.getenv("QDRANT_USE_LOCAL", "true").lower() == "true"
    QDRANT_LOCAL_PATH: str = os.getenv("QDRANT_LOCAL_PATH", "./data/qdrant_store")
    QDRANT_COLLECTION_NAME: str = os.getenv("QDRANT_COLLECTION_NAME", "learning_assistant")
    VECTOR_DIMENSION: int = int(os.getenv("VECTOR_DIMENSION", "1024"))

    # --- Neo4j 图数据库 ---
    NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER: str = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "")
    NEO4J_DATABASE: str = os.getenv("NEO4J_DATABASE", "neo4j")

    # --- 搜索 ---
    SEARCH_ENGINE: str = os.getenv("SEARCH_ENGINE", "serpapi")
    SERPAPI_API_KEY: str = os.getenv("SERPAPI_API_KEY", "")
    SEARCH_MAX_RESULTS: int = int(os.getenv("SEARCH_MAX_RESULTS", "5"))

    # --- 记忆 ---
    MEMORY_MAX_MESSAGES: int = int(os.getenv("MEMORY_MAX_MESSAGES", "50"))
    MEMORY_SUMMARY_ENABLED: bool = os.getenv("MEMORY_SUMMARY_ENABLED", "true").lower() == "true"
    CHECKPOINT_STORE_PATH: str = os.getenv("CHECKPOINT_STORE_PATH", "./data/checkpoints")

    # --- 服务器 ---
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    @classmethod
    def resolve_path(cls, relative_path: str) -> Path:
        p = Path(relative_path)
        if p.is_absolute():
            return p
        return cls.PROJECT_ROOT / p

    @classmethod
    def ensure_directories(cls) -> None:
        dirs = [
            cls.resolve_path(cls.QDRANT_LOCAL_PATH),
            cls.resolve_path(cls.CHECKPOINT_STORE_PATH),
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)

    @classmethod
    def display(cls) -> str:
        lines = ["=" * 60, "系统配置", "=" * 60]
        for key, value in sorted(cls.__dict__.items()):
            if key.startswith("_") or not key.isupper():
                continue
            if "KEY" in key and value:
                masked = value[:6] + "****" + value[-4:] if len(value) > 10 else "****"
                lines.append(f"  {key}: {masked}")
            elif "PASSWORD" in key and value:
                lines.append(f"  {key}: ****")
            else:
                lines.append(f"  {key}: {value}")
        lines.append("=" * 60)
        return "\n".join(lines)


def setup_logging() -> logging.Logger:
    level = getattr(logging, Settings.LOG_LEVEL.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    return logging.getLogger("learning_assistant")


logger = setup_logging()
Settings.ensure_directories()