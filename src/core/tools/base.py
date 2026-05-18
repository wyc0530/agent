import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any, Callable, Optional

from src.config import logger


class ToolCategory(str, Enum):
    SEARCH = "search"
    QUIZ = "quiz"
    DOCUMENT = "document"
    TIMER = "timer"
    KNOWLEDGE = "knowledge"
    UTILITY = "utility"


class ToolPermission(str, Enum):
    READ_ONLY = "read_only"
    READ_WRITE = "read_write"
    ADMIN = "admin"


@dataclass
class ToolMetadata:
    name: str
    description: str
    category: ToolCategory = ToolCategory.UTILITY
    permission: ToolPermission = ToolPermission.READ_ONLY
    version: str = "1.0.0"
    author: str = ""
    tags: list[str] = field(default_factory=list)
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)


def tool(name: str, description: str, category: ToolCategory = ToolCategory.UTILITY):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = func(*args, **kwargs)
                elapsed = time.time() - start
                logger.debug(f"工具 [{name}] 执行成功 | 耗时 {elapsed:.3f}s")
                return result
            except Exception as e:
                elapsed = time.time() - start
                logger.warning(f"工具 [{name}] 执行失败 | 耗时 {elapsed:.3f}s | {e}")
                raise

        wrapper._tool_meta = ToolMetadata(
            name=name,
            description=description,
            category=category,
        )
        return wrapper

    return decorator


class BaseTool(ABC):
    metadata: ToolMetadata

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if not hasattr(cls, "metadata"):
            cls.metadata = ToolMetadata(
                name=cls.__name__,
                description=cls.__doc__ or "",
            )

    @abstractmethod
    def execute(self, **kwargs) -> Any:
        ...

    async def aexecute(self, **kwargs) -> Any:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: self.execute(**kwargs))

    def to_langchain_tool(self):
        from langchain_core.tools import tool as lc_tool

        metadata = self.metadata

        @lc_tool(metadata.name, description=metadata.description)
        def _tool(**kwargs) -> Any:
            return self.execute(**kwargs)

        return _tool


class ToolRegistry:
    _instance: Optional["ToolRegistry"] = None
    _tools: dict[str, BaseTool] = {}
    _function_tools: dict[str, Callable] = {}

    def __new__(cls) -> "ToolRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self._tools:
            return

    def register(self, tool_instance: BaseTool) -> None:
        name = tool_instance.metadata.name
        if name in self._tools:
            logger.warning(f"工具 [{name}] 已注册，将被覆盖")
        self._tools[name] = tool_instance
        logger.info(f"工具已注册 | name={name} category={tool_instance.metadata.category.value}")

    def register_function(self, func: Callable) -> None:
        if not hasattr(func, "_tool_meta"):
            raise ValueError(f"函数 {func.__name__} 未使用 @tool 装饰器")
        meta = func._tool_meta
        self._function_tools[meta.name] = func
        logger.info(f"函数工具已注册 | name={meta.name}")

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)
        self._function_tools.pop(name, None)

    def get(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)

    def get_function(self, name: str) -> Optional[Callable]:
        return self._function_tools.get(name)

    def execute(self, name: str, **kwargs) -> Any:
        tool_instance = self._tools.get(name)
        if tool_instance:
            return tool_instance.execute(**kwargs)
        func = self._function_tools.get(name)
        if func:
            return func(**kwargs)
        raise KeyError(f"工具 [{name}] 未注册")

    async def aexecute(self, name: str, **kwargs) -> Any:
        tool_instance = self._tools.get(name)
        if tool_instance:
            return await tool_instance.aexecute(**kwargs)
        func = self._function_tools.get(name)
        if func:
            if asyncio.iscoroutinefunction(func):
                return await func(**kwargs)
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, lambda: func(**kwargs))
        raise KeyError(f"工具 [{name}] 未注册")

    def list_by_category(self, category: ToolCategory) -> list[str]:
        names = []
        for name, t in self._tools.items():
            if t.metadata.category == category:
                names.append(name)
        return names

    def list_all(self) -> list[dict[str, Any]]:
        result = []
        for name, t in self._tools.items():
            result.append({
                "name": name,
                "description": t.metadata.description,
                "category": t.metadata.category.value,
                "permission": t.metadata.permission.value,
                "type": "class",
            })
        for name, func in self._function_tools.items():
            meta = func._tool_meta
            result.append({
                "name": name,
                "description": meta.description,
                "category": meta.category.value,
                "type": "function",
            })
        return result

    def get_tool_descriptions(self) -> str:
        lines = []
        for info in self.list_all():
            lines.append(f"- {info['name']}: {info['description']}")
        return "\n".join(lines)

    def to_langchain_tools(self) -> list:
        tools = []
        for t in self._tools.values():
            tools.append(t.to_langchain_tool())
        for func in self._function_tools.values():
            from langchain_core.tools import tool as lc_tool

            wrapped = lc_tool(func)
            tools.append(wrapped)
        return tools

    def reset(self) -> None:
        self._tools.clear()
        self._function_tools.clear()
        logger.info("工具注册表已重置")


def get_tool_registry() -> ToolRegistry:
    return ToolRegistry()


def register_all_tools() -> ToolRegistry:
    from src.core.tools.document import DocumentGenerator
    from src.core.tools.quiz import AbilityAssessor, QuizGenerator
    from src.core.tools.search import WebSearchTool
    from src.core.tools.timer import FocusTimer

    registry = ToolRegistry()

    registry.register(WebSearchTool())
    registry.register(DocumentGenerator())
    registry.register(FocusTimer())
    registry.register(QuizGenerator())
    registry.register(AbilityAssessor())

    logger.info(f"全部工具注册完成 | total={len(registry.list_all())}")
    return registry