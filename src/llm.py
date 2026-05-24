import asyncio
import time
from typing import Any, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from src.config import Settings, logger


class LLMProvider:
    _instance: Optional["LLMProvider"] = None
    _model: Optional[BaseChatModel] = None
    _local_model: Optional[BaseChatModel] = None

    def __new__(cls) -> "LLMProvider":
        if cls._instance is None:
            try:
                cls._instance = super().__new__(cls)
            except (TypeError, RuntimeError, AttributeError) as e:
                cls._instance = None
                logger.error(f"LLMProvider 单例创建失败: {e}")
                raise
        return cls._instance

    def __init__(self) -> None:
        if self._model is not None:
            return
        try:
            self._initialize()
        except Exception:
            self._model = None
            self._local_model = None
            raise

    def _initialize(self) -> None:
        logger.info(f"初始化 LLM 接入层 | provider={Settings.LLM_PROVIDER} model={Settings.LLM_MODEL}")

        provider = Settings.LLM_PROVIDER.lower()
        openai_compatible = ("openai", "modelscope", "zhipu", "deepseek", "custom")

        if provider in openai_compatible:
            self._model = ChatOpenAI(
                model=Settings.LLM_MODEL,
                api_key=Settings.LLM_API_KEY,
                base_url=Settings.LLM_BASE_URL,
                temperature=Settings.LLM_TEMPERATURE,
                max_tokens=Settings.LLM_MAX_TOKENS,
            )
            logger.info(f"LLM 接入层初始化完成 | provider={provider} compatible=true")
        else:
            raise ValueError(f"不支持的LLM提供商: {Settings.LLM_PROVIDER}，当前支持: {', '.join(openai_compatible)}")

        if Settings.LOCAL_LLM_ENABLED:
            self._init_local_model()

    def _init_local_model(self) -> None:
        try:
            logger.info(f"加载本地 LLM 模型 | model={Settings.LOCAL_LLM_MODEL} device={Settings.LOCAL_LLM_DEVICE}")
            self._local_model = ChatOpenAI(
                model=Settings.LOCAL_LLM_MODEL,
                api_key="not-needed",
                base_url=Settings.LOCAL_LLM_BASE_URL,
                temperature=Settings.LLM_TEMPERATURE,
                max_tokens=Settings.LLM_MAX_TOKENS,
            )
            logger.info("本地 LLM 模型加载成功")
        except Exception as e:
            logger.warning(f"本地 LLM 模型加载失败，将使用远程API作为备选: {e}")
            self._local_model = None

    @property
    def model(self) -> BaseChatModel:
        if self._model is None:
            raise RuntimeError("LLM模型未初始化")
        return self._model

    def invoke(
        self,
        messages: list[BaseMessage],
        use_local: bool = False,
        **kwargs: Any,
    ) -> AIMessage:
        model = self._local_model if use_local and self._local_model else self._model
        if model is None:
            raise RuntimeError("没有可用的LLM模型")

        try:
            result = model.invoke(messages, **kwargs)
            if isinstance(result, BaseMessage):
                return result
            return AIMessage(content=str(result))
        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            if use_local or self._local_model is None:
                raise
            logger.info("API调用失败，尝试使用本地模型")
            return self.invoke(messages, use_local=True)

    async def ainvoke(
        self,
        messages: list[BaseMessage],
        use_local: bool = False,
        **kwargs: Any,
    ) -> AIMessage:
        model = self._local_model if use_local and self._local_model else self._model
        if model is None:
            raise RuntimeError("没有可用的LLM模型")

        try:
            result = await model.ainvoke(messages, **kwargs)
            if isinstance(result, BaseMessage):
                return result
            return AIMessage(content=str(result))
        except Exception as e:
            logger.warning(f"LLM异步调用失败: {e}")
            if use_local or self._local_model is None:
                raise
            logger.info("API调用失败，尝试使用本地模型")
            return await self.ainvoke(messages, use_local=True)

    def invoke_with_retry(
        self,
        messages: list[BaseMessage],
        max_retries: int = 3,
        base_delay: float = 1.0,
    ) -> AIMessage:
        last_error = None
        for attempt in range(max_retries):
            try:
                return self.invoke(messages)
            except Exception as e:
                last_error = e
                logger.warning(f"LLM调用失败 (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    time.sleep(delay)
        raise RuntimeError(f"LLM调用在 {max_retries} 次重试后仍然失败: {last_error}")

    def chat(
        self,
        user_message: str,
        system_prompt: str = "",
        use_local: bool = False,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        messages: list[BaseMessage] = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=user_message))
        response = self.invoke(messages, use_local=use_local, temperature=temperature, max_tokens=max_tokens)
        return response.content

    async def achat(
        self,
        user_message: str,
        system_prompt: str = "",
        use_local: bool = False,
    ) -> str:
        messages: list[BaseMessage] = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=user_message))
        response = await self.ainvoke(messages, use_local=use_local)
        return response.content

    def chat_with_history(
        self,
        user_message: str,
        history: list[BaseMessage],
        system_prompt: str = "",
    ) -> str:
        messages: list[BaseMessage] = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        for msg in history:
            content = msg.get("content", "") if isinstance(msg, dict) else (getattr(msg, "content", ""))
            role = msg.get("role", "user") if isinstance(msg, dict) else getattr(msg, "type", "human")
            if role not in ("system", "ai", "assistant", "human", "user"):
                role = "user"
            if role in ("assistant", "ai"):
                messages.append(AIMessage(content=content))
            elif role == "system":
                continue
            else:
                messages.append(HumanMessage(content=content))
        messages.append(HumanMessage(content=user_message))
        response = self.invoke(messages)
        return response.content

    def check_health(self) -> dict[str, Any]:
        health = {
            "provider": Settings.LLM_PROVIDER,
            "model": Settings.LLM_MODEL,
            "api_available": self._model is not None,
            "local_available": self._local_model is not None,
        }
        return health


_llm_provider: Optional[LLMProvider] = None


def get_llm() -> LLMProvider:
    global _llm_provider
    if _llm_provider is None:
        _llm_provider = LLMProvider()
    return _llm_provider


async def get_llm_async() -> LLMProvider:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, get_llm)