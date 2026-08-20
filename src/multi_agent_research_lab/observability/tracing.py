"""Tracing hooks supporting local JSON spans and optional LangSmith / Langfuse."""

import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager
from time import perf_counter
from typing import Any

from multi_agent_research_lab.core.config import get_settings

logger = logging.getLogger(__name__)


def setup_external_tracing() -> None:
    """Configure external tracing providers (LangSmith/Langfuse) if keys are provided."""
    settings = get_settings()
    if settings.langsmith_api_key or os.getenv("LANGSMITH_API_KEY"):
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key or os.getenv(
            "LANGSMITH_API_KEY", ""
        )
        os.environ["LANGCHAIN_PROJECT"] = settings.langsmith_project
        logger.info(f"LangSmith tracing enabled for project '{settings.langsmith_project}'")

    if settings.langfuse_public_key and settings.langfuse_secret_key:
        os.environ["LANGFUSE_PUBLIC_KEY"] = settings.langfuse_public_key
        os.environ["LANGFUSE_SECRET_KEY"] = settings.langfuse_secret_key
        os.environ["LANGFUSE_HOST"] = settings.langfuse_host
        logger.info("Langfuse tracing credentials initialized.")


@contextmanager
def trace_span(name: str, attributes: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]:
    """Context manager to measure and log an execution span."""
    started = perf_counter()
    span: dict[str, Any] = {
        "name": name,
        "attributes": attributes or {},
        "duration_seconds": None,
        "status": "in_progress",
    }
    try:
        yield span
        span["status"] = "success"
    except Exception as exc:
        span["status"] = "error"
        span["error"] = str(exc)
        raise
    finally:
        span["duration_seconds"] = round(perf_counter() - started, 4)
