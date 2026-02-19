from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv

from .graph import build_research_graph, create_initial_state
from .search import WebSearchClient
from .types import ResearchState

# Load API keys and runtime options from .env if present.
load_dotenv()


def create_default_llm(model: str = "gpt-4.1-mini") -> Any:
    try:
        from langchain_openai import ChatOpenAI
    except ImportError:
        return None

    if not os.getenv("OPENAI_API_KEY"):
        return None

    return ChatOpenAI(model=model, temperature=0)


def format_output_json(state: ResearchState) -> dict[str, Any]:
    urls = sorted(
        {
            item["url"]
            for item in state.get("raw_research_data", [])
            if isinstance(item, dict) and item.get("url")
        }
    )
    diagnostics = state.get("diagnostics", {"errors": [], "warnings": []})
    errors = diagnostics.get("errors", [])
    llm_invoke = state.get("llm_invoke", {})
    result_valid = bool(urls) and not errors and not llm_invoke.get("used_fallback", False)

    return {
        "company_info": state.get("company_info", {}),
        "scale": state.get("scale"),
        "insights": state.get("insights", {}),
        "llm_invoke": llm_invoke,
        "diagnostics": diagnostics,
        "result_valid": result_valid,
        "reference_urls": urls,
    }


def run_research(
    company_name: str,
    team_name: str,
    role_name: str,
    provider: str = "tavily",
    model: str = "gpt-4.1-mini",
    verbose: bool = False,
) -> dict[str, Any]:
    initial_state = create_initial_state(company_name, team_name, role_name)
    search_client = WebSearchClient(provider=provider)
    llm = create_default_llm(model=model)
    graph = build_research_graph(search_client=search_client, llm=llm, verbose=verbose)
    final_state = graph.invoke(initial_state)
    return format_output_json(final_state)
