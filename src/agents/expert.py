import json
from typing import Any

from src.agents.base_agent import AgentResult, BaseAgent
from src.config import logger
from src.core.state import AgentRole, LearningState
from src.core.tools.search import WebSearchTool
from src.core.tools.document import DocumentGenerator


_REACT_SYSTEM_PROMPT = """你是一个专业的学习指导专家，使用ReAct（推理-行动-观察）模式来推荐学习资料。

## 可用操作
- SEARCH: 搜索互联网获取学习资料和课程信息
- ANALYZE: 分析搜索结果，评估资料质量
- FINALIZE: 生成最终推荐方案

## 输出格式
每次响应严格按以下格式输出：
```
Thought: 分析当前状态，决定下一步行动
Action: SEARCH | ANALYZE | FINALIZE
Action Input: 操作的具体输入（搜索关键词 / 分析指令 / 最终推荐内容）
```

## 规则
- 先SEARCH获取资料，再ANALYZE评估质量，最后FINALIZE生成推荐
- 如果搜索结果不理想，可以调整关键词再次SEARCH
- 最多执行3轮SEARCH操作
- FINALIZE时输出完整的推荐方案"""


class ExpertAgent(BaseAgent):
    role = AgentRole.EXPERT
    description = "学习专家Agent：ReAct模式→搜索资料→分析评估→迭代优化→推荐学习内容与课程"

    def __init__(self) -> None:
        super().__init__()
        self._searcher = WebSearchTool()
        self._doc_gen = DocumentGenerator()

    def _build_system_prompt(self, state: LearningState) -> str:
        profile = state.get("user_profile") or {}
        plan = state.get("learning_plan")

        plan_context = ""
        if plan and isinstance(plan, dict):
            plan_phases = plan.get("phases", [])
            if plan_phases:
                phases_desc = "\n".join(
                    f"- {p.get('phase_name', p.get('name', ''))}: {p.get('phase_description', p.get('description', ''))}"
                    for p in plan_phases[:3] if isinstance(p, dict)
                )
                plan_context = f"## 当前学习计划中的阶段\n{phases_desc}"

        user_context = f"""## 用户信息
- 当前水平: {profile.get('level', '未评估')}
- 学习偏好: {profile.get('preference', '综合学习')}
{plan_context}"""

        return _REACT_SYSTEM_PROMPT + "\n\n" + user_context

    def run(self, state: LearningState, message: str = "") -> AgentResult:
        return self._safe_run(state, message, self._run_impl)

    def _run_impl(self, state: LearningState, message: str) -> AgentResult:
        state_changes: dict[str, Any] = {"current_agent": self.role}
        all_web_results: list[dict[str, Any]] = []
        react_trace: list[dict[str, str]] = []

        system_prompt = self._build_system_prompt(state)
        current_input = message or "请推荐当前阶段的学习资料"
        max_iterations = 5
        search_count = 0
        max_searches = 3

        for iteration in range(max_iterations):
            react_prompt = self._build_react_prompt(system_prompt, current_input, all_web_results, react_trace, iteration)
            history = self._extract_history(state)

            try:
                response = self._chat(react_prompt, "", history=history, temperature=0.7, max_tokens=1024)
            except Exception as e:
                logger.error(f"ExpertAgent ReAct LLM 调用失败: {e}")
                break

            parsed = self._parse_react_response(response)
            react_trace.append({
                "iteration": str(iteration),
                "response": response,
                "thought": parsed.get("thought", ""),
                "action": parsed.get("action", ""),
                "action_input": parsed.get("action_input", ""),
            })

            action = parsed.get("action", "").upper()

            if action == "SEARCH":
                if search_count >= max_searches:
                    current_input = "已达到最大搜索次数，请直接ANALYZE现有结果并FINALIZE"
                    continue
                search_count += 1
                query = parsed.get("action_input", message)
                try:
                    results = self._searcher.execute(query=query, num_results=5)
                    all_web_results.extend(results)
                    observation = self._format_search_observation(results)
                    current_input = f"Observation: 搜索完成，获得 {len(results)} 条结果。\n{observation}\n\n请根据搜索结果继续下一步操作。"
                    logger.info(f"ExpertAgent ReAct SEARCH | iteration={iteration} query={query[:50]} results={len(results)}")
                except Exception as e:
                    logger.warning(f"ExpertAgent 搜索失败: {e}")
                    current_input = f"Observation: 搜索失败 ({e})。请调整策略或直接ANALYZE/FINALIZE。"

            elif action == "ANALYZE":
                analysis = parsed.get("action_input", "")
                current_input = f"Observation: 分析完成。\n{analysis}\n\n请根据分析结果决定是否需要更多搜索，或直接FINALIZE。"

            elif action == "FINALIZE":
                final_content = parsed.get("action_input", response)
                logger.info(f"ExpertAgent ReAct FINALIZE | iterations={iteration + 1}")
                break

            else:
                current_input = f"Observation: 无法识别的操作 '{action}'。请使用 SEARCH、ANALYZE 或 FINALIZE。\n\n{response}"

        else:
            final_content = current_input

        doc_content: dict[str, Any] = {"type": "learning_material", "topic": message}
        try:
            doc = self._doc_gen.execute(
                doc_type="course_recommendation",
                data={"materials": all_web_results},
                title=f"推荐学习: {message}",
            )
            doc_content["document"] = doc
        except Exception as e:
            logger.warning(f"ExpertAgent 文档生成失败: {e}")

        doc_content["ai_recommendation"] = final_content
        doc_content["web_results_count"] = len(all_web_results)
        doc_content["react_iterations"] = len(react_trace)

        logger.info(f"ExpertAgent ReAct 完成 | topic={message} iterations={len(react_trace)} web_results={len(all_web_results)}")
        return AgentResult(
            agent_role=self.role,
            output=doc_content,
            state_changes=state_changes,
        )

    def _build_react_prompt(
        self,
        system_prompt: str,
        user_input: str,
        web_results: list[dict[str, Any]],
        trace: list[dict[str, str]],
        iteration: int,
    ) -> str:
        """构建ReAct上下文提示"""
        parts = [
            system_prompt,
            f"## 用户请求\n{user_input}",
        ]

        if web_results:
            results_text = "\n".join(
                f"- [{r.get('title', '')}] {r.get('snippet', '')[:200]}"
                for r in web_results[-10:]
            )
            parts.append(f"\n## 已获取的搜索结果 ({len(web_results)}条)\n{results_text}")

        if trace:
            trace_text = "\n".join(
                f"[Iter {t['iteration']}] Thought: {t['thought']}\n  Action: {t['action']}"
                for t in trace[-3:]
            )
            parts.append(f"\n## 历史推理轨迹\n{trace_text}")

        parts.append(f"\n## 当前迭代: {iteration + 1}")
        parts.append("请按格式输出 Thought → Action → Action Input")

        return "\n\n".join(parts)

    @staticmethod
    def _parse_react_response(response: str) -> dict[str, str]:
        """解析ReAct格式的LLM响应"""
        result = {"thought": "", "action": "", "action_input": ""}

        lines = response.strip().split("\n")
        for line in lines:
            line = line.strip()
            if line.lower().startswith("thought:") or line.startswith("Thought:"):
                result["thought"] = line.split(":", 1)[1].strip() if ":" in line else ""
            elif line.lower().startswith("action:") or line.startswith("Action:"):
                action_part = line.split(":", 1)[1].strip() if ":" in line else ""
                result["action"] = action_part.split()[0] if action_part else ""
            elif line.lower().startswith("action input:") or line.startswith("Action Input:"):
                result["action_input"] = line.split(":", 1)[1].strip() if ":" in line else ""

        if not result["action"]:
            if "FINALIZE" in response.upper() or "finalize" in response.lower():
                result["action"] = "FINALIZE"
                result["action_input"] = response
            elif "SEARCH" in response.upper():
                result["action"] = "SEARCH"
                result["action_input"] = response
            elif "ANALYZE" in response.upper():
                result["action"] = "ANALYZE"
                result["action_input"] = response
            else:
                result["action"] = "FINALIZE"
                result["action_input"] = response

        return result

    @staticmethod
    def _format_search_observation(results: list[dict[str, Any]]) -> str:
        """格式化搜索结果为观察文本"""
        if not results:
            return "未找到相关结果"
        lines = []
        for i, r in enumerate(results[:5], 1):
            title = r.get("title", "无标题")
            snippet = r.get("snippet", "")[:150]
            url = r.get("url", "")
            source = r.get("source", "")
            lines.append(f"{i}. [{title}]({url}) - {source}\n   {snippet}")
        return "\n".join(lines)