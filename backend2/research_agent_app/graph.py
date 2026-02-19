from __future__ import annotations

import json
import re
import sys
import time
from typing import Any, Optional

from langgraph.graph import END, START, StateGraph

from .constants import (
    CLASSIFICATION_QUERY,
    INSIGHT_EXTRACTION_PROMPT,
    JOB_POSTING_SCHEMA_OUTLINE,
    SCALE_QUERY_TEMPLATES,
    USER_PROFILE_SCHEMA_OUTLINE,
)
from .heuristics import _extract_ceo_name, _fallback_insights, classify_scale_from_text
from .search import SearchResult, WebSearchClient, fetch_markdown_via_jina
from .types import InsightHooks, LLMInvokeData, RawResearchItem, ResearchState, Scale


def create_initial_state(
    company_name: str,
    team_name: str,
    role_name: str,
    job_posting: Optional[dict[str, Any]] = None,
    user_profile: Optional[dict[str, Any]] = None,
) -> ResearchState:
    return {
        "company_info": {
            "name": company_name,
            "team": team_name,
            "role": role_name,
        },
        "scale": None,
        "raw_research_data": [],
        "insights": {
            "business_hook": "",
            "tech_hook": "",
            "culture_hook": "",
        },
        "llm_invoke": {
            "invoked": False,
            "raw_response": "",
            "parse_success": False,
            "used_fallback": False,
        },
        "diagnostics": {
            "errors": [],
            "warnings": [],
        },
        "job_posting": job_posting if isinstance(job_posting, dict) else {},
        "user_profile": user_profile if isinstance(user_profile, dict) else {},
    }


def _safe_search(
    search_client: WebSearchClient, query: str, k: int
) -> tuple[list[SearchResult], Optional[str]]:
    try:
        return search_client.search(query, k=k), None
    except Exception as exc:
        return [], f"{type(exc).__name__}: {exc}"


def _extract_json_object(text: str) -> Optional[dict[str, Any]]:
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return None

    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None

    if isinstance(parsed, dict):
        return parsed
    return None


def _build_research_context(raw_data: list[RawResearchItem], max_chars: int = 16_000) -> str:
    chunks: list[str] = []
    total = 0

    for item in raw_data:
        url = item.get("url", "")
        title = item.get("title", "")
        snippet = item.get("snippet", "")
        content = item.get("content_markdown", "")
        body = content or snippet
        if not body:
            continue

        block = f"[title] {title}\n[url] {url}\n[content]\n{body[:1600]}\n"
        if total + len(block) > max_chars:
            break
        chunks.append(block)
        total += len(block)

    return "\n".join(chunks)


def _coerce_insights(data: Optional[dict[str, Any]]) -> Optional[InsightHooks]:
    if not isinstance(data, dict):
        return None

    required_keys = ("business_hook", "tech_hook", "culture_hook")
    if not all(key in data for key in required_keys):
        return None

    return {
        "business_hook": str(data["business_hook"]).strip(),
        "tech_hook": str(data["tech_hook"]).strip(),
        "culture_hook": str(data["culture_hook"]).strip(),
    }


def _json_context(data: dict[str, Any], max_chars: int = 6_000) -> str:
    if not data:
        return "없음"
    try:
        raw = json.dumps(data, ensure_ascii=False, indent=2)
    except Exception:
        raw = str(data)
    if len(raw) <= max_chars:
        return raw
    return raw[:max_chars] + "\n...(truncated)"


def _normalize_query_term(value: Any, max_len: int = 40) -> str:
    text = str(value or "").strip()
    text = re.sub(r"\s+", " ", text)
    return text[:max_len]


def _extract_terms(value: Any, limit: int = 4) -> list[str]:
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            term = _normalize_query_term(item)
            if term:
                out.append(term)
            if len(out) >= limit:
                break
        return out
    return []


def _build_posting_queries(company_name: str, job_posting: dict[str, Any]) -> list[str]:
    if not isinstance(job_posting, dict):
        return []

    company_block = job_posting.get("company")
    position_block = job_posting.get("position")
    requirements = job_posting.get("requirements")

    if not isinstance(position_block, dict):
        position_block = {}
    if not isinstance(requirements, dict):
        requirements = {}

    position_title = _normalize_query_term(position_block.get("title"))
    department = _normalize_query_term(position_block.get("department"))
    tech_stack = _extract_terms(requirements.get("tech_stack"), limit=4)
    main_tasks = _extract_terms(requirements.get("main_tasks"), limit=2)
    talent_keywords = _extract_terms(job_posting.get("talent_keywords"), limit=4)

    queries: list[str] = []
    if position_title or department or tech_stack:
        query = " ".join(
            part
            for part in (
                company_name,
                position_title,
                department,
                "기술스택",
                " ".join(tech_stack),
            )
            if part
        )
        queries.append(query.strip())

    if position_title or main_tasks:
        query = " ".join(
            part
            for part in (
                company_name,
                position_title,
                "주요업무",
                " ".join(main_tasks),
                "실제 프로젝트",
            )
            if part
        )
        queries.append(query.strip())

    if talent_keywords:
        queries.append(f"{company_name} 인재상 조직문화 {' '.join(talent_keywords)}")

    if isinstance(company_block, dict):
        industry = _normalize_query_term(company_block.get("industry"))
        if industry:
            queries.append(f"{company_name} {industry} 최근 사업 방향")

    deduped: list[str] = []
    seen: set[str] = set()
    for query in queries:
        normalized = query.strip()
        if not normalized:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped[:3]


def _build_classifier_evidence_from_posting(job_posting: dict[str, Any]) -> str:
    if not isinstance(job_posting, dict):
        return ""

    company_block = job_posting.get("company")
    if not isinstance(company_block, dict):
        return ""

    parts: list[str] = []
    size = company_block.get("size")
    industry = company_block.get("industry")
    if isinstance(size, str) and size.strip():
        parts.append(f"회사규모: {size.strip()}")
    if isinstance(industry, str) and industry.strip():
        parts.append(f"산업: {industry.strip()}")
    return "\n".join(parts)


def build_research_graph(
    search_client: WebSearchClient,
    llm: Any = None,
    per_query_results: int = 4,
    jina_timeout: int = 20,
    verbose: bool = False,
):
    def log(message: str) -> None:
        if not verbose:
            return
        ts = time.strftime("%H:%M:%S")
        print(f"[{ts}] {message}", file=sys.stderr, flush=True)

    def company_classifier_node(state: ResearchState) -> dict[str, Any]:
        company_name = state["company_info"]["name"]
        query = CLASSIFICATION_QUERY.format(company_name=company_name)
        log(f"[Classifier] query={query}")
        search_results, search_error = _safe_search(search_client, query, k=per_query_results)
        log(f"[Classifier] results={len(search_results)}")

        raw_data = list(state.get("raw_research_data", []))
        diagnostics = dict(state.get("diagnostics", {"errors": [], "warnings": []}))
        diagnostics.setdefault("errors", [])
        diagnostics.setdefault("warnings", [])

        if search_error:
            diagnostics["errors"].append(f"classifier search failed: {search_error}")
        if not search_results:
            diagnostics["warnings"].append(
                f"classifier returned 0 results for query: {query}"
            )

        evidence_parts: list[str] = []
        for result in search_results:
            evidence_parts.append(f"{result.title} {result.snippet}")
            raw_data.append(
                {
                    "stage": "classifier",
                    "query": query,
                    "title": result.title,
                    "url": result.url,
                    "snippet": result.snippet,
                }
            )

        posting_evidence = _build_classifier_evidence_from_posting(state.get("job_posting", {}))
        if posting_evidence:
            evidence_parts.append(posting_evidence)

        evidence_text = "\n".join(evidence_parts)
        scale = classify_scale_from_text(evidence_text)
        log(f"[Classifier] scale={scale}")

        return {
            "scale": scale,
            "raw_research_data": raw_data,
            "diagnostics": diagnostics,
        }

    def adaptive_researcher_node(state: ResearchState) -> dict[str, Any]:
        company = state["company_info"]
        scale: Scale = (state.get("scale") or "Startup")  # type: ignore[assignment]
        raw_data = list(state.get("raw_research_data", []))
        diagnostics = dict(state.get("diagnostics", {"errors": [], "warnings": []}))
        diagnostics.setdefault("errors", [])
        diagnostics.setdefault("warnings", [])
        added_sources = 0

        classifier_evidence = "\n".join(
            item.get("snippet", "") for item in raw_data if item.get("stage") == "classifier"
        )
        ceo_name = _extract_ceo_name(classifier_evidence, company["name"])
        log(f"[Research] scale={scale} ceo_guess={ceo_name}")

        templates = SCALE_QUERY_TEMPLATES.get(scale, SCALE_QUERY_TEMPLATES["Startup"])
        query_candidates = [
            template.format(
                company_name=company["name"],
                team_name=company["team"],
                role_name=company["role"],
                ceo_name=ceo_name,
            )
            for template in templates
        ]
        query_candidates.extend(_build_posting_queries(company["name"], state.get("job_posting", {})))

        seen_urls = {item.get("url", "") for item in raw_data if item.get("url")}
        seen_queries: set[str] = set()
        for query in query_candidates:
            normalized_query = query.strip()
            if not normalized_query or normalized_query in seen_queries:
                continue
            seen_queries.add(normalized_query)

            log(f"[Research] query={normalized_query}")
            search_results, search_error = _safe_search(
                search_client, normalized_query, k=per_query_results
            )
            log(f"[Research] results={len(search_results)}")
            if search_error:
                diagnostics["errors"].append(
                    f"adaptive search failed for query='{normalized_query}': {search_error}"
                )
            if not search_results:
                diagnostics["warnings"].append(
                    f"adaptive search returned 0 results for query: {normalized_query}"
                )

            for result in search_results:
                if not result.url or result.url in seen_urls:
                    continue
                seen_urls.add(result.url)

                markdown = ""
                try:
                    log(f"[Jina] fetch url={result.url}")
                    markdown = fetch_markdown_via_jina(result.url, timeout=jina_timeout)
                    log(f"[Jina] ok chars={len(markdown)}")
                except Exception:
                    log("[Jina] fail")
                    markdown = ""

                raw_data.append(
                    {
                        "stage": "adaptive_research",
                        "query": normalized_query,
                        "title": result.title,
                        "url": result.url,
                        "snippet": result.snippet,
                        "content_markdown": markdown[:12_000],
                    }
                )
                added_sources += 1

        if added_sources == 0:
            diagnostics["warnings"].append(
                "adaptive research collected 0 sources; insights may be fallback-only."
            )

        return {"raw_research_data": raw_data, "diagnostics": diagnostics}

    def insight_extractor_node(state: ResearchState) -> dict[str, Any]:
        company = state["company_info"]
        scale = state.get("scale") or "Startup"
        raw_data = state.get("raw_research_data", [])
        job_posting = state.get("job_posting", {})
        user_profile = state.get("user_profile", {})
        diagnostics = dict(state.get("diagnostics", {"errors": [], "warnings": []}))
        diagnostics.setdefault("errors", [])
        diagnostics.setdefault("warnings", [])

        research_context = _build_research_context(raw_data)
        job_posting_context = _json_context(job_posting)
        user_profile_context = _json_context(user_profile)
        log(f"[Insight] context_chars={len(research_context)} llm={'on' if llm else 'off'}")

        if not research_context.strip():
            diagnostics["warnings"].append(
                "no research context available; using fallback insight generation."
            )
        if not job_posting:
            diagnostics["warnings"].append(
                "job_posting input is empty; insight quality may degrade."
            )
        if not user_profile:
            diagnostics["warnings"].append(
                "user_profile input is empty; personal-fit hooks will avoid inference."
            )

        insights: Optional[InsightHooks] = None
        llm_invoke: LLMInvokeData = {
            "invoked": False,
            "raw_response": "",
            "parse_success": False,
            "used_fallback": False,
        }
        if llm is not None and research_context:
            prompt = INSIGHT_EXTRACTION_PROMPT.format(
                company_name=company["name"],
                team_name=company["team"],
                role_name=company["role"],
                scale=scale,
                user_profile_schema_outline=USER_PROFILE_SCHEMA_OUTLINE or "스키마 정보 없음",
                job_posting_schema_outline=JOB_POSTING_SCHEMA_OUTLINE or "스키마 정보 없음",
                job_posting_context=job_posting_context,
                user_profile_context=user_profile_context,
                research_context=research_context,
            )
            try:
                llm_invoke["invoked"] = True
                log("[Insight] llm_invoke=start")
                response = llm.invoke(prompt)
                log("[Insight] llm_invoke=done")
                content = response.content if hasattr(response, "content") else str(response)
                llm_invoke["raw_response"] = str(content)
                parsed_json = _extract_json_object(str(content))
                if parsed_json is not None:
                    llm_invoke["parsed_json"] = parsed_json
                insights = _coerce_insights(parsed_json)
                llm_invoke["parse_success"] = insights is not None
            except Exception as exc:
                diagnostics["errors"].append(f"llm invoke failed: {type(exc).__name__}: {exc}")
                llm_invoke["error"] = f"{type(exc).__name__}: {exc}"
                insights = None

        if insights is None:
            llm_invoke["used_fallback"] = True
            log("[Insight] fallback=heuristic")
            if not llm_invoke.get("invoked", False):
                llm_invoke["error"] = llm_invoke.get(
                    "error", "LLM not invoked or no usable research context."
                )
            insights = _fallback_insights(
                company_name=company["name"],
                team_name=company["team"],
                role_name=company["role"],
                research_context=research_context,
                user_profile=user_profile if isinstance(user_profile, dict) else None,
            )

        return {"insights": insights, "llm_invoke": llm_invoke, "diagnostics": diagnostics}

    def route_by_scale(state: ResearchState) -> Scale:
        scale = state.get("scale")
        if scale in ("Large", "Medium", "Startup"):
            return scale
        return "Startup"

    graph_builder = StateGraph(ResearchState)
    graph_builder.add_node("company_classifier", company_classifier_node)
    graph_builder.add_node("adaptive_researcher", adaptive_researcher_node)
    graph_builder.add_node("insight_extractor", insight_extractor_node)

    graph_builder.add_edge(START, "company_classifier")
    graph_builder.add_conditional_edges(
        "company_classifier",
        route_by_scale,
        {
            "Large": "adaptive_researcher",
            "Medium": "adaptive_researcher",
            "Startup": "adaptive_researcher",
        },
    )
    graph_builder.add_edge("adaptive_researcher", "insight_extractor")
    graph_builder.add_edge("insight_extractor", END)

    return graph_builder.compile()
