import hashlib
import time
from typing import Any, Optional

import numpy as np

from src.config import Settings, logger


class EmbeddingCache:
    def __init__(self, max_size: int = 10000, ttl_seconds: int = 3600) -> None:
        self._cache: dict[str, tuple[list[float], float]] = {}
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds

    def _key(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def get(self, text: str) -> Optional[list[float]]:
        key = self._key(text)
        entry = self._cache.get(key)
        if entry is None:
            return None
        vector, timestamp = entry
        if time.time() - timestamp > self._ttl_seconds:
            del self._cache[key]
            return None
        return vector

    def set(self, text: str, vector: list[float]) -> None:
        key = self._key(text)
        self._cache[key] = (vector, time.time())
        if len(self._cache) > self._max_size:
            oldest = min(self._cache, key=lambda k: self._cache[k][1])
            del self._cache[oldest]

    def _cleanup_expired(self) -> int:
        now = time.time()
        expired = [k for k, (_, ts) in self._cache.items() if now - ts > self._ttl_seconds]
        for k in expired:
            del self._cache[k]
        return len(expired)

    def clear(self) -> None:
        self._cache.clear()

    @property
    def size(self) -> int:
        return len(self._cache)


class EmbeddingProvider:
    _instance: Optional["EmbeddingProvider"] = None
    _cache: Optional[EmbeddingCache] = None
    _local_model: Any = None

    def __new__(cls) -> "EmbeddingProvider":
        if cls._instance is None:
            try:
                cls._instance = super().__new__(cls)
            except (TypeError, RuntimeError, AttributeError) as e:
                cls._instance = None
                logger.error(f"EmbeddingProvider 单例创建失败: {e}")
                raise
        return cls._instance

    def __init__(self) -> None:
        if self._cache is not None:
            return
        self._local_model = None
        self._cache = EmbeddingCache()
        try:
            self._initialize()
        except Exception:
            self._local_model = None
            self._cache = None
            raise

    def _initialize(self) -> None:
        logger.info(
            f"初始化 Embedding 模块 | provider={Settings.EMBEDDING_PROVIDER} "
            f"model={Settings.EMBEDDING_MODEL} dim={Settings.EMBEDDING_DIMENSION}"
        )

        if Settings.EMBEDDING_PROVIDER == "bailian":
            try:
                import dashscope
                dashscope.api_key = Settings.DASHSCOPE_API_KEY
                logger.info("百炼 Embedding 客户端初始化成功")
            except Exception as e:
                logger.warning(f"百炼 Embedding 初始化失败: {e}")

        if Settings.LOCAL_EMBEDDING_ENABLED:
            self._init_local_model()

    def _init_local_model(self) -> None:
        try:
            from sentence_transformers import SentenceTransformer

            logger.info(
                f"加载本地 Embedding 模型 | model={Settings.LOCAL_EMBEDDING_MODEL} "
                f"device={Settings.LOCAL_EMBEDDING_DEVICE}"
            )
            self._local_model = SentenceTransformer(
                Settings.LOCAL_EMBEDDING_MODEL,
                device=Settings.LOCAL_EMBEDDING_DEVICE,
                cache_folder=Settings.LOCAL_EMBEDDING_PATH,
            )
            dim = self._local_model.get_sentence_embedding_dimension()
            logger.info(f"本地 Embedding 模型加载成功 | dimension={dim}")
        except Exception as e:
            logger.warning(f"本地 Embedding 模型加载失败，将使用百炼API作为备选: {e}")
            self._local_model = None

    def embed_text(self, text: str) -> list[float]:
        if not text or not text.strip():
            raise ValueError("embed_text 不支持空文本")

        cached = self._cache.get(text)
        if cached is not None:
            return cached

        vector = self._embed_text_impl(text)
        self._cache.set(text, vector)
        return vector

    def _embed_text_impl(self, text: str) -> list[float]:
        if Settings.EMBEDDING_PROVIDER == "bailian":
            try:
                from dashscope import TextEmbedding

                resp = TextEmbedding.call(
                    model=Settings.EMBEDDING_MODEL,
                    input=text,
                )
                if resp.status_code == 200:
                    return resp.output["embeddings"][0]["embedding"]
                else:
                    raise RuntimeError(
                        f"百炼 Embedding API 错误 | code={resp.status_code} "
                        f"message={resp.message}"
                    )
            except Exception as e:
                logger.warning(f"百炼 Embedding API 调用失败: {e}")
                if not Settings.LOCAL_EMBEDDING_ENABLED:
                    raise RuntimeError(f"Embedding 生成失败且无本地备选模型: {e}")

        if self._local_model is not None:
            result = self._local_model.encode(text, normalize_embeddings=True)
            if isinstance(result, np.ndarray):
                return result.tolist()
            return list(result)

        raise RuntimeError("没有可用的 Embedding 模型")

    def embed_batch(self, texts: list[str], chunk_size: int = 25) -> list[list[float]]:
        results: list[Optional[list[float]]] = [None] * len(texts)
        seen_uncached: dict[str, list[int]] = {}

        for i, text in enumerate(texts):
            cached = self._cache.get(text)
            if cached is not None:
                results[i] = cached
            else:
                if text not in seen_uncached:
                    seen_uncached[text] = []
                seen_uncached[text].append(i)

        unique_texts = list(seen_uncached.keys())
        for start in range(0, len(unique_texts), chunk_size):
            chunk = unique_texts[start : start + chunk_size]
            chunk_vectors = self._embed_batch_impl(chunk)
            for text, vector in zip(chunk, chunk_vectors):
                self._cache.set(text, vector)
                for idx in seen_uncached[text]:
                    results[idx] = vector

        return [r if r is not None else [] for r in results]

    def _embed_batch_impl(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        if Settings.EMBEDDING_PROVIDER == "bailian":
            try:
                from dashscope import TextEmbedding

                resp = TextEmbedding.call(
                    model=Settings.EMBEDDING_MODEL,
                    input=texts,
                )
                if resp.status_code == 200:
                    return [e["embedding"] for e in resp.output["embeddings"]]
                else:
                    raise RuntimeError(
                        f"百炼 Embedding 批量调用失败 | code={resp.status_code} "
                        f"message={resp.message}"
                    )
            except Exception as e:
                logger.warning(f"百炼 Embedding 批量调用失败: {e}")
                if not Settings.LOCAL_EMBEDDING_ENABLED:
                    raise RuntimeError(f"批量 Embedding 生成失败: {e}")

        if self._local_model is not None:
            result = self._local_model.encode(texts, normalize_embeddings=True)
            if isinstance(result, np.ndarray):
                return result.tolist()
            return [list(r) for r in result]

        return [self.embed_text(t) for t in texts]

    def similarity(self, vec1: list[float], vec2: list[float]) -> float:
        a = np.array(vec1)
        b = np.array(vec2)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    def batch_similarity(
        self, query_vec: list[float], target_vecs: list[list[float]]
    ) -> list[float]:
        query = np.array(query_vec)
        targets = np.array(target_vecs)
        query_norm = query / np.linalg.norm(query)
        targets_norm = targets / np.linalg.norm(targets, axis=1, keepdims=True)
        similarities = np.dot(targets_norm, query_norm)
        return similarities.tolist()

    def check_health(self) -> dict[str, Any]:
        health = {
            "provider": Settings.EMBEDDING_PROVIDER,
            "model": Settings.EMBEDDING_MODEL,
            "dimension": Settings.EMBEDDING_DIMENSION,
            "local_available": self._local_model is not None,
            "cache_size": self._cache.size if self._cache else 0,
            "status": "ok" if self._local_model or Settings.DASHSCOPE_API_KEY else "uninitialized",
        }
        return health


_embedding_provider: Optional[EmbeddingProvider] = None


def get_embedding() -> EmbeddingProvider:
    global _embedding_provider
    if _embedding_provider is None:
        _embedding_provider = EmbeddingProvider()
    return _embedding_provider