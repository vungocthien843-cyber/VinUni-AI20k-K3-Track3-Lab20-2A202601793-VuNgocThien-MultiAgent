"""Benchmark runner and automated evaluation for single-agent vs multi-agent."""

import re
from collections.abc import Callable
from time import perf_counter

from multi_agent_research_lab.core.schemas import BenchmarkMetrics, ResearchQuery
from multi_agent_research_lab.core.state import ResearchState

Runner = Callable[[str], ResearchState]


def compute_citation_coverage(state: ResearchState) -> float:
    """Calculate the ratio of available sources cited in final_answer."""
    if not state.sources or not state.final_answer:
        return 0.0

    cited_indices = set()
    # Check numeric citations like [1], [2]
    num_matches = re.findall(r"\[(\d+)\]", state.final_answer)
    for m in num_matches:
        idx = int(m)
        if 1 <= idx <= len(state.sources):
            cited_indices.add(idx)

    # Also check if source title keywords appear in the answer
    for idx, source in enumerate(state.sources, start=1):
        if idx not in cited_indices:
            title_words = [w for w in re.findall(r"\w+", source.title.lower()) if len(w) > 4]
            if title_words and any(w in state.final_answer.lower() for w in title_words[:3]):
                cited_indices.add(idx)

    coverage = len(cited_indices) / len(state.sources)
    return round(min(1.0, coverage), 3)


def compute_estimated_cost(state: ResearchState) -> float:
    """Sum estimated USD cost across all agent execution steps."""
    total_cost = 0.0
    for res in state.agent_results:
        cost = res.metadata.get("cost_usd")
        if cost and isinstance(cost, (int, float)):
            total_cost += float(cost)
    return round(total_cost, 6)


def compute_quality_score(state: ResearchState) -> float:
    """Compute an objective 0-10 quality score based on structure, citations, and content."""
    if not state.final_answer:
        return 0.0

    score = 0.0
    content = state.final_answer

    # 1. Structural organization (+3 pts)
    if "##" in content or "###" in content:
        score += 1.5
    if len(content.split()) >= 150:
        score += 1.5

    # 2. Citation and grounding (+3 pts)
    cov = compute_citation_coverage(state)
    score += cov * 3.0

    # 3. Intermediate analytical depth (+2 pts)
    if state.analysis_notes and len(state.analysis_notes) > 50:
        score += 2.0
    elif state.research_notes:
        score += 1.0

    # 4. Error penalty (+2 pts base, deducted if errors present)
    if not state.errors:
        score += 2.0
    else:
        score += max(0.0, 2.0 - len(state.errors) * 0.5)

    return round(min(10.0, score), 1)


def run_benchmark(
    run_name: str, query: str, runner: Runner
) -> tuple[ResearchState, BenchmarkMetrics]:
    """Execute runner, track performance metrics, and return final state with metrics."""
    started = perf_counter()
    failure_rate = 0.0
    notes = ""

    try:
        state = runner(query)
    except Exception as exc:
        failure_rate = 1.0
        state = ResearchState(request=ResearchQuery(query=query))
        state.errors.append(f"Benchmark run failed: {exc}")
        notes = f"Execution failed with error: {exc}"

    latency = perf_counter() - started

    citation_cov = compute_citation_coverage(state)
    cost = compute_estimated_cost(state)
    quality = compute_quality_score(state)

    if not notes:
        notes = (
            f"{len(state.route_history)} hops ({' -> '.join(state.route_history)})"
            if state.route_history
            else "Single-pass execution"
        )

    metrics = BenchmarkMetrics(
        run_name=run_name,
        latency_seconds=round(latency, 3),
        estimated_cost_usd=cost if cost > 0 else None,
        quality_score=quality,
        citation_coverage=citation_cov,
        failure_rate=failure_rate,
        notes=notes,
    )
    return state, metrics
