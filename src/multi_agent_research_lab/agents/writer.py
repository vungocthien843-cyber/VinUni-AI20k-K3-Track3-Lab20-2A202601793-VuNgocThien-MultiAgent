"""Writer agent implementation."""

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.schemas import AgentName, AgentResult
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.services.llm_client import LLMClient


class WriterAgent(BaseAgent):
    """Produces final answer from research and analysis notes with inline citations."""

    name = "writer"

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client or LLMClient()

    def run(self, state: ResearchState) -> ResearchState:
        """Populate `state.final_answer`."""
        system_prompt = (
            "You are an expert Technical Research Writer. Synthesize complex analytical "
            "insights into a clear, cohesive report tailored for the requested audience. "
            "CRITICAL: You MUST use inline citations formatted like [1], [2] throughout, "
            "and include a complete 'References' section at the end corresponding to sources."
        )

        sources_context = ""
        if state.sources:
            sources_context = "\nAvailable Sources:\n" + "\n".join(
                f"[{idx}] {doc.title} ({doc.url or 'N/A'})\n    Summary: {doc.snippet}"
                for idx, doc in enumerate(state.sources, start=1)
            )

        analysis_context = (
            state.analysis_notes or state.research_notes or "No analysis notes available."
        )

        user_prompt = (
            f"Topic Query: {state.request.query}\n"
            f"Target Audience: {state.request.audience}\n\n"
            f"Analytical Findings:\n{analysis_context}\n"
            f"{sources_context}\n\n"
            "Please write a comprehensive, professional research synthesis with:\n"
            "- Executive Summary & Problem Framing\n"
            "- Detailed Architectural & Technical Analysis\n"
            "- Practical Guidance & Guardrail Recommendations\n"
            "- Final Takeaways\n"
            "- Complete References section with [1], [2], etc."
        )

        response = self.llm_client.complete(system_prompt, user_prompt)
        state.final_answer = response.content

        state.agent_results.append(
            AgentResult(
                agent=AgentName.WRITER,
                content=state.final_answer,
                metadata={
                    "input_tokens": response.input_tokens,
                    "output_tokens": response.output_tokens,
                    "cost_usd": response.cost_usd,
                },
            )
        )
        state.add_trace_event(
            "writer.done",
            {"cost_usd": response.cost_usd, "output_tokens": response.output_tokens},
        )
        return state
