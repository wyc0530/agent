import uuid
from datetime import datetime
from typing import Any, Optional

from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models

from src.config import Settings, logger
from src.core.state import ErrorRecord
from src.embedding import EmbeddingProvider


class VectorStore:
    _instance: Optional["VectorStore"] = None
    _client: Optional[QdrantClient] = None

    def __new__(cls) -> "VectorStore":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self._initialize()

    def _initialize(self) -> None:
        self._collection_name = Settings.QDRANT_COLLECTION_NAME
        self._embedding = EmbeddingProvider()
        self._vector_dim = Settings.VECTOR_DIMENSION

        if Settings.QDRANT_USE_LOCAL:
            persist_dir = Settings.resolve_path(Settings.QDRANT_LOCAL_PATH)
            persist_dir.mkdir(parents=True, exist_ok=True)
            self._client = QdrantClient(path=str(persist_dir))
            logger.info(f"Qdrant 本地模式初始化 | path={persist_dir}")
        else:
            url = Settings.QDRANT_URL
            if not url.startswith("https://"):
                url = f"{url}:{Settings.QDRANT_PORT}"
            self._client = QdrantClient(
                url=url,
                api_key=Settings.QDRANT_API_KEY or None,
            )
            logger.info(f"Qdrant 远程模式初始化 | url={url}")

        try:
            self._client.get_collection(self._collection_name)
            logger.info(f"Qdrant 集合已存在 | collection={self._collection_name}")
        except Exception:
            self._client.create_collection(
                collection_name=self._collection_name,
                vectors_config=qdrant_models.VectorParams(
                    size=self._vector_dim,
                    distance=qdrant_models.Distance.COSINE,
                ),
            )
            logger.info(f"Qdrant 集合已创建 | collection={self._collection_name} dim={self._vector_dim}")

    @property
    def client(self) -> QdrantClient:
        if self._client is None:
            raise RuntimeError("Qdrant client 未初始化")
        return self._client

    def add(
        self,
        documents: list[str],
        metadatas: Optional[list[dict[str, Any]]] = None,
        ids: Optional[list[str]] = None,
    ) -> None:
        if not documents:
            return

        embeddings = self._embedding.embed_batch(documents)
        if ids is None:
            ids = [str(uuid.uuid4()) for _ in documents]
        else:
            ids = [self._sanitize_id(id_) for id_ in ids]
        if metadatas is None:
            metadatas = [{} for _ in documents]

        points = []
        for i, (doc_id, vector, meta, text) in enumerate(zip(ids, embeddings, metadatas, documents)):
            payload = {**meta, "_text": text}
            points.append(
                qdrant_models.PointStruct(
                    id=doc_id,
                    vector=vector,
                    payload=payload,
                )
            )

        self._client.upsert(
            collection_name=self._collection_name,
            points=points,
        )
        logger.debug(f"Qdrant 向量数据添加 | count={len(documents)}")

    @staticmethod
    def _sanitize_id(original_id: str) -> str:
        try:
            uuid.UUID(original_id)
            return original_id
        except (ValueError, AttributeError):
            namespace = uuid.NAMESPACE_DNS
            return str(uuid.uuid5(namespace, original_id))

    def add_document(
        self, text: str, metadata: Optional[dict[str, Any]] = None, doc_id: Optional[str] = None
    ) -> str:
        if doc_id is not None:
            doc_id = self._sanitize_id(doc_id)
        else:
            doc_id = str(uuid.uuid4())
        embedding = self._embedding.embed_text(text)
        payload = {**(metadata or {}), "_text": text}

        self._client.upsert(
            collection_name=self._collection_name,
            points=[
                qdrant_models.PointStruct(
                    id=doc_id,
                    vector=embedding,
                    payload=payload,
                )
            ],
        )
        return doc_id

    def search(
        self, query: str, top_k: int = 5, filter_metadata: Optional[dict[str, Any]] = None
    ) -> list[dict[str, Any]]:
        if not query or not query.strip():
            return []
        query_embedding = self._embedding.embed_text(query)

        query_filter = None
        if filter_metadata:
            conditions = [
                qdrant_models.FieldCondition(
                    key=k,
                    match=qdrant_models.MatchValue(value=v),
                )
                for k, v in filter_metadata.items()
            ]
            query_filter = qdrant_models.Filter(must=conditions)

        results = self._client.query_points(
            collection_name=self._collection_name,
            query=query_embedding,
            limit=top_k,
            query_filter=query_filter,
            with_payload=True,
        )

        items = []
        for r in results.points:
            payload = r.payload or {}
            items.append({
                "id": r.id,
                "content": payload.get("_text", ""),
                "metadata": {k: v for k, v in payload.items() if k != "_text"},
                "score": float(r.score),
            })
        return items

    def delete(self, ids: list[str]) -> None:
        self._client.delete(
            collection_name=self._collection_name,
            points_selector=qdrant_models.PointIdsList(
                points=ids,
            ),
        )

    def count(self) -> int:
        info = self._client.get_collection(self._collection_name)
        return info.points_count or 0

    def check_health(self) -> dict[str, Any]:
        try:
            count = self.count()
            info = self._client.get_collection(self._collection_name)
            if Settings.QDRANT_USE_LOCAL:
                storage = "local"
            elif Settings.QDRANT_URL.startswith("https://"):
                storage = Settings.QDRANT_URL
            else:
                storage = f"{Settings.QDRANT_URL}:{Settings.QDRANT_PORT}"
            return {
                "status": "ok",
                "collection": self._collection_name,
                "document_count": count,
                "vector_dimension": info.config.params.vectors.size if info.config.params.vectors else 0,
                "storage": storage,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}


class LongTermMemory:
    def __init__(self, user_id: str) -> None:
        self._user_id = user_id
        self._store = VectorStore()

    def remember_interaction(self, role: str, content: str, metadata: Optional[dict] = None) -> str:
        meta = {
            "user_id": self._user_id,
            "role": role,
            "timestamp": datetime.now().isoformat(),
            **(metadata or {}),
        }
        return self._store.add_document(text=content, metadata=meta)

    def store_error_record(self, record: ErrorRecord) -> str:
        content = (
            f"错题: {record.question.content}\n"
            f"知识点: {record.knowledge_point}\n"
            f"用户答案: {record.user_answer}\n"
            f"正确答案: {record.question.answer}\n"
            f"解析: {record.question.explanation}"
        )
        return self._store.add_document(
            text=content,
            metadata={
                "user_id": self._user_id,
                "type": "error_record",
                "knowledge_point": record.knowledge_point,
                "error_count": record.error_count,
                "mastered": record.mastered,
            },
        )

    def store_learning_material(self, content: str, material_type: str, metadata: Optional[dict] = None) -> str:
        meta = {
            "user_id": self._user_id,
            "type": material_type,
            **(metadata or {}),
        }
        return self._store.add_document(text=content, metadata=meta)

    def retrieve_relevant(
        self, query: str, top_k: int = 5, filter_type: Optional[str] = None
    ) -> list[dict[str, Any]]:
        filter_meta = {"user_id": self._user_id}
        if filter_type:
            filter_meta["type"] = filter_type
        return self._store.search(query, top_k=top_k, filter_metadata=filter_meta)

    def retrieve_errors_by_knowledge_point(self, knowledge_point: str) -> list[dict[str, Any]]:
        filter_meta = {
            "user_id": self._user_id,
            "type": "error_record",
            "knowledge_point": knowledge_point,
        }
        return self._store.search(knowledge_point, top_k=20, filter_metadata=filter_meta)

    def get_user_summary(self) -> dict[str, Any]:
        all_records = self._store.search(
            "学习 记录 历史", top_k=50, filter_metadata={"user_id": self._user_id}
        )
        error_records = self.retrieve_relevant("错题", top_k=50, filter_type="error_record")
        return {
            "total_interactions": len(all_records),
            "total_errors": len(error_records),
            "knowledge_points": list({
                r.get("metadata", {}).get("knowledge_point", "")
                for r in error_records
                if r.get("metadata", {}).get("knowledge_point")
            }),
        }


def get_short_term_memory_key(user_id: str, thread_id: str) -> str:
    return f"memory:{user_id}:{thread_id}"


def get_vector_store() -> VectorStore:
    return VectorStore()