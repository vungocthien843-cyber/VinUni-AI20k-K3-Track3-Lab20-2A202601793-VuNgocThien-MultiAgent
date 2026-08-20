"""Command-line entrypoint for the Multi-Agent Research Lab."""

import sys
from pathlib import Path
from time import perf_counter
from typing import Annotated

import typer
import yaml
from pydantic import ValidationError
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from multi_agent_research_lab.core.config import get_settings
from multi_agent_research_lab.core.schemas import (
    AgentName,
    AgentResult,
    BenchmarkMetrics,
    ResearchQuery,
)
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.evaluation.benchmark import run_benchmark
from multi_agent_research_lab.evaluation.report import render_markdown_report
from multi_agent_research_lab.graph.workflow import MultiAgentWorkflow
from multi_agent_research_lab.observability.logging import configure_logging
from multi_agent_research_lab.observability.tracing import setup_external_tracing
from multi_agent_research_lab.services.llm_client import LLMClient
from multi_agent_research_lab.services.storage import LocalArtifactStore

# Fix Windows console utf-8 encoding
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

app = typer.Typer(help="Multi-Agent Research Lab CLI")
console = Console(safe_box=True)


def _init() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    setup_external_tracing()


def _parse_query(query: str) -> ResearchQuery:
    try:
        return ResearchQuery(query=query)
    except ValidationError as exc:
        console.print(
            Panel.fit(
                f"Invalid query: {exc.errors()[0]['msg']}",
                title="Input Error",
                style="red",
            )
        )
        raise typer.Exit(code=1) from exc


def _run_single_agent_baseline(query_str: str) -> ResearchState:
    """Execute single-agent direct LLM baseline without decomposition."""
    request = _parse_query(query_str)
    state = ResearchState(request=request)
    llm = LLMClient()

    system_prompt = "You are an AI research assistant. Provide a direct, concise summary."
    user_prompt = f"Please research and answer: {query_str}"

    response = llm.complete(system_prompt, user_prompt)
    state.final_answer = response.content
    state.agent_results.append(
        AgentResult(
            agent=AgentName.WRITER,
            content=response.content,
            metadata={
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "cost_usd": response.cost_usd,
            },
        )
    )
    state.record_route("single_agent_direct")
    return state


def _run_multi_agent(query_str: str) -> ResearchState:
    """Execute full multi-agent workflow."""
    request = _parse_query(query_str)
    state = ResearchState(request=request)
    workflow = MultiAgentWorkflow()
    return workflow.run(state)


@app.command()
def baseline(
    query: Annotated[str, typer.Option("--query", "-q", help="Research query")],
) -> None:
    """Run a single-agent baseline LLM call and measure metrics."""
    _init()
    console.print(f"[bold cyan]Running Single-Agent Baseline for:[/bold cyan] {query}\n")

    started = perf_counter()
    state = _run_single_agent_baseline(query)
    latency = perf_counter() - started

    cost = state.agent_results[0].metadata.get("cost_usd", 0.0) if state.agent_results else 0.0

    console.print(
        Panel(
            state.final_answer or "",
            title="[bold green]Baseline Answer[/bold green]",
            border_style="green",
        )
    )

    table = Table(title="Execution Metrics", show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="yellow")
    table.add_row("Latency", f"{latency:.3f} s")
    table.add_row("Estimated Cost", f"${cost:.6f}")
    table.add_row("Sources Retrieved", str(len(state.sources)))
    console.print(table)


@app.command("multi-agent")
def multi_agent(
    query: Annotated[str, typer.Option("--query", "-q", help="Research query")],
    critic: Annotated[
        bool, typer.Option("--critic", "-c", help="Enable optional Critic agent")
    ] = False,
) -> None:
    """Run the multi-agent workflow (Supervisor -> Researcher -> Analyst -> Writer)."""
    _init()
    console.print(f"[bold cyan]Launching Multi-Agent Research Workflow for:[/bold cyan] {query}\n")

    request = _parse_query(query)
    state = ResearchState(request=request)
    workflow = MultiAgentWorkflow(enable_critic=critic)

    started = perf_counter()
    result = workflow.run(state)
    latency = perf_counter() - started

    # Route history panel
    route_chain = " -> ".join(f"[bold yellow]{r}[/bold yellow]" for r in result.route_history)
    console.print(Panel(route_chain, title="[bold blue]Orchestration Route History[/bold blue]"))

    # Sources retrieved
    if result.sources:
        sources_table = Table(title="Retrieved Sources", show_header=True)
        sources_table.add_column("#", width=4)
        sources_table.add_column("Title", style="cyan")
        sources_table.add_column("URL / Provenance", style="dim")
        for idx, doc in enumerate(result.sources, start=1):
            sources_table.add_row(str(idx), doc.title, doc.url or "Offline Benchmark Corpus")
        console.print(sources_table)

    # Final Answer
    console.print(
        Panel(
            result.final_answer or "",
            title="[bold green]Final Research Synthesis[/bold green]",
            border_style="green",
        )
    )

    # Summary metrics
    total_cost = sum(
        float(res.metadata.get("cost_usd", 0.0) or 0.0) for res in result.agent_results
    )
    table = Table(title="Workflow Performance", show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="yellow")
    table.add_row("Total Latency", f"{latency:.3f} s")
    table.add_row("Total Estimated Cost", f"${total_cost:.6f}")
    table.add_row("Handoff Iterations", str(result.iteration))
    table.add_row("Agents Executed", str(len(result.agent_results)))
    console.print(table)


@app.command()
def benchmark(
    config_file: Annotated[
        str, typer.Option("--config", "-c", help="Path to config yaml")
    ] = "configs/lab_default.yaml",
) -> None:
    """Run benchmark comparing single-agent vs multi-agent."""
    _init()
    config_path = Path(config_file)
    queries = ["Research GraphRAG state-of-the-art and write a 500-word summary"]
    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
            queries = cfg.get("benchmark", {}).get("queries", queries)

    console.print(
        f"[bold cyan]Running Benchmark Suite with {len(queries)} queries...[/bold cyan]\n"
    )

    all_metrics: list[BenchmarkMetrics] = []

    for i, q in enumerate(queries, start=1):
        console.print(f"[bold yellow]Evaluating Query {i}/{len(queries)}:[/bold yellow] {q}")

        # 1. Single Agent Baseline
        _, m_single = run_benchmark(f"Single-Agent (Q{i})", q, _run_single_agent_baseline)
        all_metrics.append(m_single)

        # 2. Multi Agent Workflow
        _, m_multi = run_benchmark(f"Multi-Agent (Q{i})", q, _run_multi_agent)
        all_metrics.append(m_multi)

    # Render report
    markdown_report = render_markdown_report(all_metrics)
    store = LocalArtifactStore(Path("reports"))
    out_path = store.write_text("benchmark_report.md", markdown_report)

    console.print(
        f"\n[bold green]Benchmark complete![/bold green] Report written to: "
        f"[underline]{out_path}[/underline]\n"
    )
    console.print(markdown_report)


@app.command()
def ui(
    host: Annotated[str, typer.Option("--host", "-h", help="Host address")] = "127.0.0.1",
    port: Annotated[int, typer.Option("--port", "-p", help="Port number")] = 8000,
) -> None:
    """Launch the interactive Multi-Agent Research Studio Web UI."""
    _init()
    import uvicorn

    from multi_agent_research_lab.web.app import app as web_app

    console.print(f"[bold green]Starting Web Studio UI at: http://{host}:{port}[/bold green]")
    uvicorn.run(web_app, host=host, port=port)


if __name__ == "__main__":
    app()
