"""Unit tests for multi-agent roles and routing policy."""

from multi_agent_research_lab.agents.analyst import AnalystAgent
from multi_agent_research_lab.agents.critic import CriticAgent
from multi_agent_research_lab.agents.researcher import ResearcherAgent
from multi_agent_research_lab.agents.supervisor import SupervisorAgent
from multi_agent_research_lab.agents.writer import WriterAgent
from multi_agent_research_lab.core.schemas import ResearchQuery, SourceDocument
from multi_agent_research_lab.core.state import ResearchState


def test_supervisor_routing_sequence() -> None:
    """Test supervisor routing policy transitions correctly across states."""
    supervisor = SupervisorAgent(max_iterations=6)
    state = ResearchState(request=ResearchQuery(query="Research AI Agents"))

    # 1. Initially no sources -> route to researcher
    assert supervisor.decide_route(state) == "researcher"
    state = supervisor.run(state)
    assert state.route_history == ["researcher"]

    # 2. Simulate sources found -> route to analyst
    state.sources = [SourceDocument(title="AI Agents Survey", snippet="Overview of agents")]
    assert supervisor.decide_route(state) == "analyst"
    state = supervisor.run(state)
    assert state.route_history == ["researcher", "analyst"]

    # 3. Simulate analysis completed -> route to writer
    state.analysis_notes = "Key findings: Multi-agent systems offer better modularity."
    assert supervisor.decide_route(state) == "writer"
    state = supervisor.run(state)
    assert state.route_history == ["researcher", "analyst", "writer"]

    # 4. Simulate final answer written -> route to done
    state.final_answer = "Full synthesized report [1]."
    assert supervisor.decide_route(state) == "done"
    state = supervisor.run(state)
    assert state.route_history == ["researcher", "analyst", "writer", "done"]


def test_supervisor_max_iterations_guardrail() -> None:
    """Test supervisor stops with 'done' when max iterations reached."""
    supervisor = SupervisorAgent(max_iterations=3)
    state = ResearchState(request=ResearchQuery(query="Infinite loop test"))
    state.iteration = 3

    assert supervisor.decide_route(state) == "done"


def test_researcher_populates_sources_and_notes() -> None:
    """Test researcher agent populates sources and research_notes."""
    researcher = ResearcherAgent()
    state = ResearchState(request=ResearchQuery(query="GraphRAG overview", max_sources=3))

    result_state = researcher.run(state)
    assert len(result_state.sources) > 0
    assert result_state.research_notes is not None
    assert len(result_state.agent_results) == 1
    assert result_state.agent_results[0].agent == "researcher"


def test_analyst_and_writer_execution() -> None:
    """Test analyst and writer agent pipeline execution."""
    state = ResearchState(request=ResearchQuery(query="Explain multi-agent guardrails"))
    state.sources = [
        SourceDocument(
            title="Guardrails in AI",
            url="https://example.com/guardrails",
            snippet="Guardrails prevent infinite looping and excessive costs.",
        )
    ]
    state.research_notes = "[1] Guardrails in AI: Guardrails prevent infinite looping."

    analyst = AnalystAgent()
    state = analyst.run(state)
    assert state.analysis_notes is not None

    writer = WriterAgent()
    state = writer.run(state)
    assert state.final_answer is not None
    assert len(state.final_answer) > 20

    critic = CriticAgent()
    state = critic.run(state)
    assert len(state.agent_results) == 3
