from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable

from src.config import Settings, logger

VALID_RELATION_TYPES = frozenset({
    "PREREQUISITE",
    "DEPENDS_ON",
    "RELATED_TO",
    "PART_OF",
    "EXTENDS",
    "CONTAINS",
    "TEACHES",
    "EXERCISES",
})


@dataclass
class KnowledgeNode:
    node_id: str
    name: str
    node_type: str
    description: str = ""
    difficulty: float = 1.0
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class KnowledgeRelation:
    source_id: str
    target_id: str
    relation_type: str
    weight: float = 1.0
    properties: dict[str, Any] = field(default_factory=dict)


class GraphStore:
    _instance: Optional["GraphStore"] = None
    _driver: Any = None

    def __new__(cls) -> "GraphStore":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self._initialize()

    def _initialize(self) -> None:
        if not Settings.NEO4J_PASSWORD or Settings.NEO4J_PASSWORD == "your-neo4j-password-here":
            logger.warning(
                "Neo4j 密码未配置，图数据库功能将不可用。"
                "请设置 NEO4J_PASSWORD 环境变量。"
            )
            self._driver = None
            return

        try:
            self._driver = GraphDatabase.driver(
                Settings.NEO4J_URI,
                auth=(Settings.NEO4J_USER, Settings.NEO4J_PASSWORD),
            )
            self._driver.verify_connectivity()
            self._ensure_indexes()
            logger.info(f"Neo4j 连接成功 | uri={Settings.NEO4J_URI} db={Settings.NEO4J_DATABASE}")
        except ServiceUnavailable as e:
            logger.warning(f"Neo4j 服务不可用: {e}")
            self._driver = None
        except Exception as e:
            logger.warning(f"Neo4j 连接失败: {e}")
            self._driver = None

    def _ensure_indexes(self) -> None:
        self._write(
            "CREATE INDEX knowledge_node_id IF NOT EXISTS FOR (n:Knowledge) ON (n.node_id)"
        )
        self._write(
            "CREATE INDEX knowledge_node_name IF NOT EXISTS FOR (n:Knowledge) ON (n.name)"
        )
        self._write(
            "CREATE INDEX knowledge_node_type IF NOT EXISTS FOR (n:Knowledge) ON (n.node_type)"
        )

    def _write(self, query: str, **params: Any) -> Any:
        if self._driver is None:
            logger.warning("Neo4j 驱动未初始化，跳过写操作")
            return None
        with self._driver.session(database=Settings.NEO4J_DATABASE) as session:
            return session.run(query, **params)

    def _read(self, query: str, **params: Any) -> list[dict[str, Any]]:
        if self._driver is None:
            return []
        with self._driver.session(database=Settings.NEO4J_DATABASE) as session:
            result = session.run(query, **params)
            return [dict(record) for record in result]

    def _exists(self) -> bool:
        return self._driver is not None

    @staticmethod
    def _validate_relation_type(rel_type: str) -> str:
        upper = rel_type.upper().strip()
        if upper not in VALID_RELATION_TYPES:
            logger.warning(f"拒绝非法关系类型 | type={rel_type}")
            raise ValueError(
                f"不支持的关系类型: {rel_type}，"
                f"合法类型: {', '.join(sorted(VALID_RELATION_TYPES))}"
            )
        return upper

    def add_knowledge_node(self, node: KnowledgeNode) -> str:
        if not self._exists():
            return node.node_id

        self._write(
            """
            MERGE (n:Knowledge {node_id: $node_id})
            SET n.name = $name,
                n.node_type = $node_type,
                n.description = $description,
                n.difficulty = $difficulty,
                n.updated_at = $updated_at
            """,
            node_id=node.node_id,
            name=node.name,
            node_type=node.node_type,
            description=node.description,
            difficulty=node.difficulty,
            updated_at=datetime.now().isoformat(),
        )
        logger.debug(f"知识点节点添加 | id={node.node_id} name={node.name}")
        return node.node_id

    def add_relation(self, relation: KnowledgeRelation) -> None:
        if not self._exists():
            return

        safe_rel_type = self._validate_relation_type(relation.relation_type)
        self._write(
            f"""
            MATCH (a:Knowledge {{node_id: $source_id}})
            MATCH (b:Knowledge {{node_id: $target_id}})
            MERGE (a)-[r:{safe_rel_type}]->(b)
            SET r.weight = $weight,
                r.updated_at = $updated_at
            """,
            source_id=relation.source_id,
            target_id=relation.target_id,
            weight=relation.weight,
            updated_at=datetime.now().isoformat(),
        )
        logger.debug(
            f"知识点关系添加 | {relation.source_id} -[{safe_rel_type}]-> {relation.target_id}"
        )

    def get_node(self, node_id: str) -> Optional[dict[str, Any]]:
        results = self._read(
            "MATCH (n:Knowledge {node_id: $node_id}) RETURN n",
            node_id=node_id,
        )
        if results:
            node = results[0].get("n", {})
            return dict(node) if node else None
        return None

    def query_related(
        self, node_id: str, relation_type: Optional[str] = None, max_depth: int = 1, limit: int = 20
    ) -> list[dict[str, Any]]:
        safe_max_depth = max(1, min(int(max_depth), 5))
        if relation_type:
            safe_rel = self._validate_relation_type(relation_type)
            rel_filter = f":{safe_rel}"
        else:
            rel_filter = ""
        query = f"""
            MATCH (a:Knowledge {{node_id: $node_id}})-[r{rel_filter}*1..{safe_max_depth}]->(b:Knowledge)
            RETURN b, r
            LIMIT $limit
        """
        results = self._read(query, node_id=node_id, limit=limit)
        items = []
        for record in results:
            node_data = dict(record.get("b", {})) if record.get("b") else {}
            items.append(node_data)
        return items

    def query_by_type(self, node_type: str, limit: int = 50) -> list[dict[str, Any]]:
        results = self._read(
            "MATCH (n:Knowledge {node_type: $node_type}) RETURN n LIMIT $limit",
            node_type=node_type,
            limit=limit,
        )
        return [dict(r.get("n", {})) for r in results if r.get("n")]

    def search_nodes(self, keyword: str, limit: int = 20) -> list[dict[str, Any]]:
        results = self._read(
            """
            MATCH (n:Knowledge)
            WHERE n.name CONTAINS $keyword OR n.description CONTAINS $keyword
            RETURN n
            LIMIT $limit
            """,
            keyword=keyword,
            limit=limit,
        )
        return [dict(r.get("n", {})) for r in results if r.get("n")]

    def build_learning_path(
        self, start_node_id: str, target_node_id: str, max_depth: int = 5
    ) -> list[dict[str, Any]]:
        safe_max_depth = max(1, min(int(max_depth), 10))
        results = self._read(
            f"""
            MATCH path = shortestPath(
                (a:Knowledge {{node_id: $start_id}})-[*1..{safe_max_depth}]->(b:Knowledge {{node_id: $target_id}})
            )
            RETURN nodes(path) as nodes
            LIMIT 1
            """,
            start_id=start_node_id,
            target_id=target_node_id,
        )
        if not results:
            return []

        nodes = results[0].get("nodes", [])
        return [dict(n) for n in nodes]

    def get_knowledge_subgraph(
        self, center_node_id: str, depth: int = 2, limit: int = 50
    ) -> dict[str, Any]:
        safe_depth = max(1, min(int(depth), 5))
        safe_limit = max(1, min(int(limit), 200))
        nodes = self._read(
            f"""
            MATCH (center:Knowledge {{node_id: $node_id}})
            MATCH (center)-[*1..{safe_depth}]-(related:Knowledge)
            RETURN DISTINCT related
            LIMIT $limit
            """,
            node_id=center_node_id,
            limit=safe_limit,
        )
        relations = self._read(
            f"""
            MATCH (center:Knowledge {{node_id: $node_id}})
            MATCH (center)-[r*1..{safe_depth}]-(related:Knowledge)
            RETURN DISTINCT center, related, r
            LIMIT $limit
            """,
            node_id=center_node_id,
            limit=safe_limit,
        )

        node_list = [dict(r.get("related", {})) for r in nodes if r.get("related")]
        node_list.append({"node_id": center_node_id, "name": center_node_id})

        return {
            "center": center_node_id,
            "nodes": node_list,
            "relations_count": len(relations),
        }

    def delete_node(self, node_id: str) -> None:
        if not self._exists():
            return
        self._write(
            "MATCH (n:Knowledge {node_id: $node_id}) DETACH DELETE n",
            node_id=node_id,
        )

    def get_stats(self) -> dict[str, Any]:
        if not self._exists():
            return {"status": "disconnected"}

        node_count = self._read("MATCH (n:Knowledge) RETURN count(n) as count")
        rel_count = self._read("MATCH ()-[r]->() RETURN count(r) as count")
        types = self._read("MATCH (n:Knowledge) RETURN DISTINCT n.node_type as type")

        return {
            "status": "connected",
            "total_nodes": node_count[0]["count"] if node_count else 0,
            "total_relations": rel_count[0]["count"] if rel_count else 0,
            "node_types": [t["type"] for t in types],
            "uri": Settings.NEO4J_URI,
            "database": Settings.NEO4J_DATABASE,
        }

    def check_health(self) -> dict[str, Any]:
        if self._driver is None:
            return {"status": "disconnected", "reason": "Neo4j 未配置密码或连接失败"}

        try:
            self._driver.verify_connectivity()
            stats = self.get_stats()
            stats["status"] = "ok"
            return stats
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def close(self) -> None:
        if self._driver:
            self._driver.close()
            self._driver = None
            logger.info("Neo4j 连接已关闭")


_graph_store: Optional[GraphStore] = None


def get_graph_store() -> GraphStore:
    global _graph_store
    if _graph_store is None:
        _graph_store = GraphStore()
    return _graph_store