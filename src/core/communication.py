import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional

from src.config import logger
from src.core.state import AgentOutput, AgentRole, LearningState


class SignalType(str, Enum):
    PLAN_UPDATED = "plan_updated"
    CONTENT_GENERATED = "content_generated"
    QUIZ_COMPLETED = "quiz_completed"
    REVIEW_COMPLETED = "review_completed"
    FEEDBACK_SIGNAL = "feedback_signal"
    ERROR_OCCURRED = "error_occurred"
    STATE_CHANGED = "state_changed"


@dataclass
class AgentSignal:
    type: SignalType
    source: AgentRole
    target: Optional[AgentRole] = None
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class AgentRouter:
    """Agent 间通信路由器，管理 Agent 间的消息传递和状态同步"""

    def __init__(self) -> None:
        self._handlers: dict[SignalType, list[Callable]] = {}
        self._state_subscribers: list[Callable] = []
        logger.info("AgentRouter 初始化完成")

    def register_handler(self, signal_type: SignalType, handler: Callable) -> None:
        if signal_type not in self._handlers:
            self._handlers[signal_type] = []
        self._handlers[signal_type].append(handler)
        logger.debug(f"注册信号处理器 | signal={signal_type.value}")

    def subscribe_state(self, callback: Callable) -> None:
        self._state_subscribers.append(callback)

    async def emit(self, signal: AgentSignal) -> None:
        logger.info(
            f"Agent信号 | type={signal.type.value} source={signal.source.value} "
            f"target={signal.target.value if signal.target else 'broadcast'}"
        )

        handlers = self._handlers.get(signal.type, [])
        tasks = []
        for handler in handlers:
            tasks.append(self._call_handler(handler, signal))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _call_handler(self, handler: Callable, signal: AgentSignal) -> None:
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(signal)
            else:
                await asyncio.get_running_loop().run_in_executor(None, handler, signal)
        except Exception as e:
            logger.error(f"信号处理器执行异常 | handler={handler.__name__} error={e}")

    async def notify_state_change(self, state: LearningState) -> None:
        for subscriber in self._state_subscribers:
            try:
                if asyncio.iscoroutinefunction(subscriber):
                    await subscriber(state)
                else:
                    await asyncio.get_running_loop().run_in_executor(None, subscriber, state)
            except Exception as e:
                logger.error(f"状态订阅者执行异常: {e}")

    def clear(self) -> None:
        self._handlers.clear()
        self._state_subscribers.clear()
        logger.info("AgentRouter 已清空")


class AgentCommunication:
    """Agent 间通信管理器"""

    def __init__(self) -> None:
        self._router = AgentRouter()
        self._agent_registry: dict[AgentRole, dict[str, Any]] = {}

    def register_agent(self, role: AgentRole, handler: Callable, metadata: Optional[dict] = None) -> None:
        self._agent_registry[role] = {
            "handler": handler,
            "metadata": metadata or {},
            "registered_at": datetime.now().isoformat(),
        }
        logger.info(f"Agent 注册 | role={role.value}")

    def get_agent_handler(self, role: AgentRole) -> Optional[Callable]:
        entry = self._agent_registry.get(role)
        return entry["handler"] if entry else None

    async def route_to_agent(
        self, source: AgentRole, target: AgentRole, payload: dict[str, Any]
    ) -> Optional[dict[str, Any]]:
        handler = self.get_agent_handler(target)
        if handler is None:
            logger.warning(f"Agent未注册 | target={target.value}")
            return None

        signal = AgentSignal(
            type=SignalType.STATE_CHANGED,
            source=source,
            target=target,
            payload=payload,
        )

        try:
            if asyncio.iscoroutinefunction(handler):
                result = await handler(signal)
            else:
                result = await asyncio.get_running_loop().run_in_executor(
                    None, handler, signal
                )
            logger.info(f"Agent路由成功 | {source.value} -> {target.value}")
            return result if isinstance(result, dict) else {"result": result}
        except Exception as e:
            logger.error(f"Agent路由失败 | {source.value} -> {target.value}: {e}")
            return {"error": str(e)}

    def create_feedback_loop(
        self,
        source_role: AgentRole,
        target_role: AgentRole,
        signal_type: SignalType,
        state_mapper: Callable[[LearningState], dict[str, Any]],
    ) -> None:
        async def feedback_handler(signal: AgentSignal) -> None:
            payload = signal.payload
            target_handler = self.get_agent_handler(target_role)
            if target_handler is not None:
                try:
                    if asyncio.iscoroutinefunction(target_handler):
                        await target_handler(payload)
                    else:
                        await asyncio.get_running_loop().run_in_executor(
                            None, target_handler, payload
                        )
                except Exception as e:
                    logger.error(f"反馈回路执行异常 | {source_role.value} -> {target_role.value}: {e}")

        self._router.register_handler(signal_type, feedback_handler)

        try:
            running_loop = asyncio.get_running_loop()

            def state_listener(state: LearningState) -> None:
                if state.get("pending_feedback"):
                    payload = state_mapper(state)
                    signal = AgentSignal(
                        type=signal_type,
                        source=source_role,
                        target=target_role,
                        payload=payload,
                    )
                    asyncio.run_coroutine_threadsafe(
                        self._router.emit(signal), running_loop
                    )

            self._router.subscribe_state(state_listener)
        except RuntimeError:
            logger.warning(f"反馈回路创建时无运行中的事件循环，状态监听器将以同步模式工作")

        logger.info(
            f"反馈回路创建 | {source_role.value} -> {target_role.value} "
            f"signal={signal_type.value}"
        )

    def update_state_from_agent(
        self, state: LearningState, role: AgentRole, output: Any, output_type: str = ""
    ) -> LearningState:
        agent_output = AgentOutput(
            agent_role=role,
            output_type=output_type,
            content=str(output) if not isinstance(output, dict) else "",
            structured_data=output if isinstance(output, dict) else None,
        )

        current_outputs = state.get("agent_outputs", {})
        current_outputs[role.value] = agent_output

        new_state: LearningState = {
            **state,
            "agent_outputs": current_outputs,
            "current_agent": role.value,
        }
        return new_state


_router: Optional[AgentRouter] = None
_communication: Optional[AgentCommunication] = None


def get_router() -> AgentRouter:
    global _router
    if _router is None:
        _router = AgentRouter()
    return _router


def get_communication() -> AgentCommunication:
    global _communication
    if _communication is None:
        _communication = AgentCommunication()
    return _communication