"""Unit tests for LangGraph MultiAgentWorkflow."""

from multi_agent_research_lab.core.schemas import ResearchQuery
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.graph.workflow import MultiAgentWorkflow


def test_workflow_end_to_end_execution() -> None:
    """Test full LangGraph workflow execution from START to END."""
    workflow = MultiAgentWorkflow()
    query = ResearchQuery(query="GraphRAG architecture and benchmarks", max_sources=3)
    state = ResearchState(request=query)

    final_state = workflow.run(state)

    assert final_state.final_answer is not None
    assert len(final_state.sources) > 0
    assert final_state.research_notes is not None
    assert final_state.analysis_notes is not None
    assert "researcher" in final_state.route_history
    assert "analyst" in final_state.route_history
    assert "writer" in final_state.route_history
    assert final_state.route_history[-1] == "done"


def test_workflow_with_critic() -> None:
    """Test workflow with optional Critic agent enabled."""
    workflow = MultiAgentWorkflow(enable_critic=True)
    query = ResearchQuery(query="Compare single-agent vs multi-agent", max_sources=2)
    state = ResearchState(request=query)

    final_state = workflow.run(state)

    assert final_state.final_answer is not None
    agent_names = [res.agent for res in final_state.agent_results]
    assert "critic" in agent_names
