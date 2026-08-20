"""Critic / Verifier agent implementation for fact-checking and quality verification."""

import re

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.schemas import AgentName, AgentResult
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.services.llm_client import LLMClient


class CriticAgent(BaseAgent):
    """Fact-checking, citation audit, and hallucination verification agent."""

    name = "critic"

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client or LLMClient()

    def run(self, state: ResearchState) -> ResearchState:
        """Validate final answer and append critique findings."""
        final_answer = state.final_answer or ""
        total_sources = len(state.sources)

        # Count citation markers [1], [2], etc.
        cited_numbers = set(re.findall(r"\[(\d+)\]", final_answer))
        cited_count = len(cited_numbers)
        coverage_ratio = (cited_count / total_sources) if total_sources > 0 else 1.0

        system_prompt = (
            "You are an AI Quality Critic & Fact Verifier. Audit the research report: "
            "assess claim validity, verify whether citations correctly anchor statements, "
            "and check for hallucinations or over-generalizations."
        )

        user_prompt = (
            f"User Query: {state.request.query}\n\n"
            f"Final Report Draft:\n{final_answer}\n\n"
            f"Evidence & Sources:\n{state.research_notes or 'No raw notes'}\n\n"
            f"Citation Coverage: {coverage_ratio:.0%} ({cited_count}/{total_sources} cited).\n"
            "Please deliver a concise critique summary."
        )

        response = self.llm_client.complete(system_prompt, user_prompt)
        critique_notes = response.content

        state.agent_results.append(
            AgentResult(
                agent=AgentName.CRITIC,
                content=critique_notes,
                metadata={
                    "citation_coverage": coverage_ratio,
                    "cited_sources": list(cited_numbers),
                    "cost_usd": response.cost_usd,
                },
            )
        )
        state.add_trace_event(
            "critic.done",
            {"citation_coverage": coverage_ratio, "cost_usd": response.cost_usd},
        )
        return state
