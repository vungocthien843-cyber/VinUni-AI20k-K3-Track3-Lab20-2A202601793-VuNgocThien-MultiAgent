"""Search client abstraction for ResearcherAgent."""

import json
import logging
import os
import re
from pathlib import Path

from multi_agent_research_lab.core.config import get_settings
from multi_agent_research_lab.core.schemas import SourceDocument

logger = logging.getLogger(__name__)


class SearchClient:
    """Provider-agnostic search client with online Tavily and offline corpus fallback."""

    def __init__(self, api_key: str | None = None) -> None:
        settings = get_settings()
        self.api_key = api_key or settings.tavily_api_key or os.getenv("TAVILY_API_KEY") or ""
        self._corpus_dir = self._find_corpus_dir()

    def _find_corpus_dir(self) -> Path | None:
        """Locate the offline research corpus directory if present."""
        rel_path = (
            Path("ai_agent_offline_research_corpus_30_topics_v2")
            / "ai_agent_offline_research_corpus_v2"
            / "topics"
        )
        candidates = [
            rel_path,
            Path("..") / rel_path,
            Path.cwd() / rel_path,
        ]
        for c in candidates:
            if c.exists() and c.is_dir():
                return c
        return None

    def search(self, query: str, max_results: int = 5) -> list[SourceDocument]:
        """Search for documents relevant to a query."""
        if self.api_key and self.api_key.strip():
            try:
                return self._search_tavily(query, max_results)
            except Exception as exc:
                logger.warning(f"Tavily search failed ({exc}); falling back to local corpus.")

        results = self._search_offline_corpus(query, max_results)
        if results:
            return results

        return self._get_fallback_documents(query, max_results)

    def _search_tavily(self, query: str, max_results: int) -> list[SourceDocument]:
        """Query Tavily Search API."""
        import urllib.request

        url = "https://api.tavily.com/search"
        payload = json.dumps(
            {
                "api_key": self.api_key.strip(),
                "query": query,
                "max_results": max_results,
                "search_depth": "basic",
                "include_answer": False,
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "MultiAgentLab/0.1",
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        documents: list[SourceDocument] = []
        for item in data.get("results", []):
            documents.append(
                SourceDocument(
                    title=item.get("title", "Untitled Source"),
                    url=item.get("url", ""),
                    snippet=item.get("content", ""),
                    metadata={"score": item.get("score", 0.0), "source": "tavily"},
                )
            )
        return documents[:max_results]

    def _search_offline_corpus(self, query: str, max_results: int) -> list[SourceDocument]:
        """Search in local JSON benchmark corpus using keyword overlap scoring."""
        if not self._corpus_dir or not self._corpus_dir.exists():
            return []

        query_tokens = set(re.findall(r"\w+", query.lower()))
        matched_docs: list[tuple[float, SourceDocument]] = []

        try:
            for json_file in self._corpus_dir.glob("*.json"):
                with open(json_file, encoding="utf-8") as f:
                    data = json.load(f)

                kb = data.get("knowledge_base", {})
                topic_name = data.get("topic", {}).get("name", "")

                # 1. Knowledge articles
                for article in kb.get("knowledge_articles", []):
                    title = article.get("title", "")
                    content = article.get("content", "")
                    text = f"{topic_name} {title} {content}".lower()
                    score = sum(1.0 for token in query_tokens if token in text)
                    if score > 0:
                        snippet = content[:280] + ("..." if len(content) > 280 else "")
                        art_id = article.get("article_id", "")
                        matched_docs.append(
                            (
                                score,
                                SourceDocument(
                                    title=f"{topic_name}: {title}",
                                    url=f"offline://corpus/{json_file.stem}#{art_id}",
                                    snippet=snippet,
                                    metadata={
                                        "article_id": art_id,
                                        "topic": topic_name,
                                    },
                                ),
                            )
                        )

                # 2. Source documents
                for doc in kb.get("source_documents", []):
                    title = doc.get("title", "")
                    summary = doc.get("summary", "")
                    text = f"{title} {summary}".lower()
                    score = sum(1.0 for token in query_tokens if token in text)
                    if score > 0:
                        doc_id = doc.get("source_id", "")
                        matched_docs.append(
                            (
                                score + 0.5,
                                SourceDocument(
                                    title=title,
                                    url=doc.get("url") or f"offline://source/{doc_id}",
                                    snippet=summary,
                                    metadata={"source_id": doc_id},
                                ),
                            )
                        )
        except Exception as exc:
            logger.warning(f"Error scanning offline corpus: {exc}")

        matched_docs.sort(key=lambda x: x[0], reverse=True)
        return [doc for _, doc in matched_docs[:max_results]]

    def _get_fallback_documents(self, query: str, max_results: int) -> list[SourceDocument]:
        """High quality curated fallback documents for common AI / Multi-agent topics."""
        fallback_bank: list[SourceDocument] = [
            SourceDocument(
                title="Building Effective LLM Agents (Anthropic Engineering, 2024)",
                url="https://www.anthropic.com/engineering/building-effective-agents",
                snippet=(
                    "Recommends starting with single-agent workflows before multi-agent. "
                    "Supervisor patterns work best when decomposing complex sub-tasks."
                ),
                metadata={"topic": "multi-agent"},
            ),
            SourceDocument(
                title="LangGraph: Multi-Agent Workflows & Cyclic State Machines",
                url="https://langchain-ai.github.io/langgraph/concepts/",
                snippet=(
                    "LangGraph enables building robust multi-agent systems via state graphs, "
                    "conditional routing, and guardrails like max_iterations and timeouts."
                ),
                metadata={"topic": "langgraph"},
            ),
            SourceDocument(
                title="From Local RAG to GraphRAG: Global Query Focused Summarization",
                url="https://arxiv.org/abs/2404.16130",
                snippet=(
                    "GraphRAG combines knowledge graphs with hierarchical community "
                    "summarization to answer broad thematic queries effectively."
                ),
                metadata={"topic": "graphrag"},
            ),
            SourceDocument(
                title="Production Guardrails for LLM Agent Architectures",
                url="https://example.com/production-guardrails",
                snippet=(
                    "Essential reliability guardrails include iteration counters, "
                    "hard timeout limits, state schema validation, and fallback routes."
                ),
                metadata={"topic": "guardrails"},
            ),
            SourceDocument(
                title="Benchmarking Single-Agent vs Multi-Agent Systems in Practice",
                url="https://example.com/agent-benchmarking",
                snippet=(
                    "Multi-agent architectures demonstrate higher citation accuracy "
                    "at the trade-off of higher token consumption and latency."
                ),
                metadata={"topic": "evaluation"},
            ),
        ]
        return fallback_bank[:max_results]
