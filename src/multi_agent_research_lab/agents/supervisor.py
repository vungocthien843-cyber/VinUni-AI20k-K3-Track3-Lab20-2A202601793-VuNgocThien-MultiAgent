"""Supervisor / router implementation."""

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.config import get_settings
from multi_agent_research_lab.core.state import ResearchState


class SupervisorAgent(BaseAgent):
    """Decides which worker should run next and when to stop."""

    name = "supervisor"

    def __init__(self, max_iterations: int | None = None) -> None:
        settings = get_settings()
        self.max_iterations = max_iterations or settings.max_iterations

    def decide_route(self, state: ResearchState) -> str:
        """Determine the next step in the research lifecycle.

        Routing logic:
        1. Guard: If iteration limit reached, stop immediately ('done').
        2. If no sources collected yet, route to 'researcher'.
        3. If sources collected but no analysis synthesized, route to 'analyst'.
        4. If analysis ready but no final response written, route to 'writer'.
        5. If final answer exists, workflow is complete ('done').
        """
        # Guardrail: stop infinite loops
        if state.iteration >= self.max_iterations:
            return "done"

        # Check missing state fields in sequence
        if not state.sources and "researcher" not in state.route_history:
            return "researcher"

        if state.sources and not state.analysis_notes and "analyst" not in state.route_history:
            return "analyst"

        if (state.analysis_notes or state.research_notes) and not state.final_answer:
            return "writer"

        return "done"

    def run(self, state: ResearchState) -> ResearchState:
        """Update `state.route_history` with the next route."""
        next_route = self.decide_route(state)
        state.record_route(next_route)
        state.add_trace_event(
            "supervisor.route",
            {"next_route": next_route, "iteration": state.iteration},
        )
        return state
