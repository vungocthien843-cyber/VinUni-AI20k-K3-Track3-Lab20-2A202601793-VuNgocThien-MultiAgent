"""Researcher agent implementation."""

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.schemas import AgentName, AgentResult
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.services.search_client import SearchClient


class ResearcherAgent(BaseAgent):
    """Collects sources and creates concise research notes."""

    name = "researcher"

    def __init__(self, search_client: SearchClient | None = None) -> None:
        self.search_client = search_client or SearchClient()

    def run(self, state: ResearchState) -> ResearchState:
        """Populate `state.sources` and `state.research_notes`."""
        query = state.request.query
        max_sources = state.request.max_sources

        docs = self.search_client.search(query, max_results=max_sources)
        state.sources = docs

        # Synthesize clear research notes from retrieved documents
        notes_lines = [f"### Research Notes for query: '{query}'", ""]
        if docs:
            for idx, doc in enumerate(docs, start=1):
                url_str = f" ({doc.url})" if doc.url else ""
                notes_lines.append(f"[{idx}] {doc.title}{url_str}")
                notes_lines.append(f"    {doc.snippet}")
                notes_lines.append("")
        else:
            notes_lines.append(
                "No relevant external sources found. Proceeding with intrinsic knowledge."
            )

        state.research_notes = "\n".join(notes_lines).strip()

        # Record agent result and trace event
        state.agent_results.append(
            AgentResult(
                agent=AgentName.RESEARCHER,
                content=state.research_notes,
                metadata={"num_sources": len(docs)},
            )
        )
        state.add_trace_event("researcher.done", {"num_sources": len(docs)})
        return state
