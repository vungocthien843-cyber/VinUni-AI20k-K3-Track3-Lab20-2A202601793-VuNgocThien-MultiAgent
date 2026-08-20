"""FastAPI web server for the Multi-Agent Research Lab UI."""

import json
from pathlib import Path
from time import perf_counter
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from multi_agent_research_lab.core.schemas import AgentName, AgentResult, ResearchQuery
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.evaluation.benchmark import (
    compute_citation_coverage,
    compute_estimated_cost,
    compute_quality_score,
    run_benchmark,
)
from multi_agent_research_lab.graph.workflow import MultiAgentWorkflow
from multi_agent_research_lab.services.llm_client import LLMClient

app = FastAPI(title="Multi-Agent Research Lab Live Studio")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).parent / "static"


class QueryRequest(BaseModel):
    query: str
    max_sources: int = 5
    audience: str = "technical learners"
    enable_critic: bool = False


@app.get("/api/topics")
def get_topics() -> list[dict[str, Any]]:
    """Return available offline topics for easy 1-click loading."""
    corpus_dir = Path(
        "ai_agent_offline_research_corpus_30_topics_v2/ai_agent_offline_research_corpus_v2/topics"
    )
    if not corpus_dir.exists():
        corpus_dir = Path(
            "../ai_agent_offline_research_corpus_30_topics_v2/"
            "ai_agent_offline_research_corpus_v2/topics"
        )

    topics: list[dict[str, Any]] = []
    if corpus_dir.exists():
        for f in sorted(corpus_dir.glob("*.json")):
            try:
                with open(f, encoding="utf-8") as jf:
                    data = json.load(jf)
                    topics.append(
                        {
                            "id": data.get("benchmark_metadata", {}).get("topic_id", f.stem),
                            "file": f.name,
                            "name": data.get("topic", {}).get("name", f.stem),
                            "question": data.get("topic", {}).get("research_question", ""),
                            "tags": data.get("topic", {}).get("tags", []),
                        }
                    )
            except Exception:
                pass
    return topics


@app.post("/api/run-baseline")
def run_baseline_endpoint(req: QueryRequest) -> dict[str, Any]:
    """Execute single-agent direct LLM baseline."""
    if len(req.query.strip()) < 3:
        raise HTTPException(status_code=400, detail="Query too short.")

    started = perf_counter()
    req_query = ResearchQuery(
        query=req.query,
        max_sources=req.max_sources,
        audience=req.audience,
    )
    state = ResearchState(request=req_query)
    llm = LLMClient()

    sys_prompt = "You are an AI research assistant. Provide a direct, concise summary."
    resp = llm.complete(sys_prompt, f"Please research and answer: {req.query}")

    state.final_answer = resp.content
    state.agent_results.append(
        AgentResult(
            agent=AgentName.WRITER,
            content=resp.content,
            metadata={
                "input_tokens": resp.input_tokens,
                "output_tokens": resp.output_tokens,
                "cost_usd": resp.cost_usd,
            },
        )
    )
    state.record_route("single_agent_direct")
    latency = perf_counter() - started

    return {
        "final_answer": state.final_answer,
        "latency_seconds": round(latency, 4),
        "cost_usd": resp.cost_usd or 0.0,
        "quality_score": compute_quality_score(state),
        "citation_coverage": 0.0,
        "route_history": state.route_history,
    }


@app.post("/api/run-multi")
def run_multi_endpoint(req: QueryRequest) -> dict[str, Any]:
    """Execute full multi-agent LangGraph workflow."""
    if len(req.query.strip()) < 3:
        raise HTTPException(status_code=400, detail="Query too short.")

    started = perf_counter()
    req_query = ResearchQuery(
        query=req.query,
        max_sources=req.max_sources,
        audience=req.audience,
    )
    state = ResearchState(request=req_query)
    workflow = MultiAgentWorkflow(enable_critic=req.enable_critic)
    final_state = workflow.run(state)
    latency = perf_counter() - started

    sources_data = [
        {"title": s.title, "url": s.url, "snippet": s.snippet, "metadata": s.metadata}
        for s in final_state.sources
    ]

    agent_results_data = [
        {
            "agent": r.agent,
            "content": r.content,
            "metadata": r.metadata,
        }
        for r in final_state.agent_results
    ]

    cost = compute_estimated_cost(final_state)
    coverage = compute_citation_coverage(final_state)
    quality = compute_quality_score(final_state)

    return {
        "final_answer": final_state.final_answer,
        "research_notes": final_state.research_notes,
        "analysis_notes": final_state.analysis_notes,
        "sources": sources_data,
        "route_history": final_state.route_history,
        "agent_results": agent_results_data,
        "trace": final_state.trace,
        "iteration": final_state.iteration,
        "latency_seconds": round(latency, 4),
        "cost_usd": cost,
        "quality_score": quality,
        "citation_coverage": coverage,
        "errors": final_state.errors,
    }


@app.post("/api/benchmark")
def run_benchmark_endpoint(req: dict[str, list[str]]) -> list[dict[str, Any]]:
    """Execute benchmark across a list of queries."""
    default_q = ["Research GraphRAG state-of-the-art and write a 500-word summary"]
    queries = req.get("queries", default_q)
    results: list[dict[str, Any]] = []

    def baseline_runner(q: str) -> ResearchState:
        st = ResearchState(request=ResearchQuery(query=q))
        resp = LLMClient().complete("You are an AI assistant.", q)
        st.final_answer = resp.content
        st.agent_results.append(
            AgentResult(
                agent=AgentName.WRITER,
                content=resp.content,
                metadata={"cost_usd": resp.cost_usd},
            )
        )
        st.record_route("single_agent")
        return st

    def multi_runner(q: str) -> ResearchState:
        st = ResearchState(request=ResearchQuery(query=q))
        return MultiAgentWorkflow().run(st)

    for i, q in enumerate(queries, start=1):
        _, m_single = run_benchmark(f"Single-Agent (Q{i})", q, baseline_runner)
        _, m_multi = run_benchmark(f"Multi-Agent (Q{i})", q, multi_runner)
        results.append(m_single.model_dump())
        results.append(m_multi.model_dump())

    return results


# Mount static assets
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def serve_index() -> FileResponse:
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Frontend assets not found.")
    return FileResponse(str(index_file))
