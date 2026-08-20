"""Analyst agent implementation."""

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.schemas import AgentName, AgentResult
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.services.llm_client import LLMClient


class AnalystAgent(BaseAgent):
    """Turns research notes and sources into structured insights."""

    name = "analyst"

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client or LLMClient()

    def run(self, state: ResearchState) -> ResearchState:
        """Populate `state.analysis_notes`."""
        if not state.sources and not state.research_notes:
            state.errors.append(
                "Analyst warning: No sources or research notes provided to analyze."
            )

        system_prompt = (
            "You are a Senior AI Research Analyst. Critically evaluate raw research notes, "
            "extract key trade-offs, identify core mechanisms, compare viewpoints, "
            "and evaluate the credibility and empirical support of each source."
        )

        raw_notes = state.research_notes or "No raw notes available."
        user_prompt = (
            f"Research Question: {state.request.query}\n"
            f"Target Audience: {state.request.audience}\n\n"
            f"Raw Research Notes & Evidence:\n{raw_notes}\n\n"
            "Please provide structured analysis covering:\n"
            "1. Key Findings & Extracted Claims\n"
            "2. Trade-offs (e.g. latency, cost, reliability, complexity)\n"
            "3. Source Credibility Assessment & Evidence Quality"
        )

        response = self.llm_client.complete(system_prompt, user_prompt)
        state.analysis_notes = response.content

        state.agent_results.append(
            AgentResult(
                agent=AgentName.ANALYST,
                content=state.analysis_notes,
                metadata={
                    "input_tokens": response.input_tokens,
                    "output_tokens": response.output_tokens,
                    "cost_usd": response.cost_usd,
                },
            )
        )
        state.add_trace_event(
            "analyst.done",
            {"cost_usd": response.cost_usd, "output_tokens": response.output_tokens},
        )
        return state
