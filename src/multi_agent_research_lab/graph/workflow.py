"""LangGraph workflow implementation."""

from typing import Any

from langgraph.graph import END, START, StateGraph

from multi_agent_research_lab.agents.analyst import AnalystAgent
from multi_agent_research_lab.agents.critic import CriticAgent
from multi_agent_research_lab.agents.researcher import ResearcherAgent
from multi_agent_research_lab.agents.supervisor import SupervisorAgent
from multi_agent_research_lab.agents.writer import WriterAgent
from multi_agent_research_lab.core.config import get_settings
from multi_agent_research_lab.core.state import ResearchState


class MultiAgentWorkflow:
    """Builds and runs the multi-agent graph with LangGraph."""

    def __init__(
        self,
        supervisor: SupervisorAgent | None = None,
        researcher: ResearcherAgent | None = None,
        analyst: AnalystAgent | None = None,
        writer: WriterAgent | None = None,
        critic: CriticAgent | None = None,
        enable_critic: bool = False,
    ) -> None:
        self.supervisor = supervisor or SupervisorAgent()
        self.researcher = researcher or ResearcherAgent()
        self.analyst = analyst or AnalystAgent()
        self.writer = writer or WriterAgent()
        self.critic = critic or CriticAgent()
        self.enable_critic = enable_critic
        self._graph = self.build()

    def build(self) -> Any:
        """Create and compile the LangGraph workflow.

        Flow:
        START -> supervisor -> conditional routing:
            - 'researcher' -> supervisor
            - 'analyst' -> supervisor
            - 'writer' -> supervisor (or critic)
            - 'done' -> END
        """
        builder = StateGraph(ResearchState)

        # 1. Define nodes
        builder.add_node("supervisor", lambda state: self.supervisor.run(state))
        builder.add_node("researcher", lambda state: self.researcher.run(state))
        builder.add_node("analyst", lambda state: self.analyst.run(state))
        builder.add_node("writer", lambda state: self.writer.run(state))

        if self.enable_critic:
            builder.add_node("critic", lambda state: self.critic.run(state))

        # 2. Add entrypoint edge
        builder.add_edge(START, "supervisor")

        # 3. Conditional routing from supervisor
        def supervisor_router(state: ResearchState) -> str:
            if not state.route_history:
                return "done"
            latest_route = state.route_history[-1]
            return latest_route if latest_route in ["researcher", "analyst", "writer"] else "done"

        routing_map: dict[str, str] = {
            "researcher": "researcher",
            "analyst": "analyst",
            "writer": "writer",
            "done": END,
        }
        builder.add_conditional_edges("supervisor", supervisor_router, routing_map)

        # 4. Return edges from worker nodes back to supervisor
        builder.add_edge("researcher", "supervisor")
        builder.add_edge("analyst", "supervisor")

        if self.enable_critic:
            builder.add_edge("writer", "critic")
            builder.add_edge("critic", "supervisor")
        else:
            builder.add_edge("writer", "supervisor")

        return builder.compile()

    def run(self, state: ResearchState) -> ResearchState:
        """Execute the graph and return the final validated ResearchState."""
        settings = get_settings()
        recursion_limit = settings.max_iterations * 4 + 10

        raw_result = self._graph.invoke(
            state,
            config={"recursion_limit": recursion_limit},
        )

        if isinstance(raw_result, dict):
            return ResearchState.model_validate(raw_result)
        return raw_result
