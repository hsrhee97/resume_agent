from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Literal, Optional, TypedDict

import requests
from dotenv import load_dotenv
from langchain_core.prompts import PromptTemplate
from langgraph.graph import END, START, StateGraph

# Load API keys and runtime options from .env if present.
load_dotenv()
# Avoid creating/updating __pycache__ in restricted environments.
sys.dont_write_bytecode = True

Scale = Literal["Large", "Medium", "Startup"]


class CompanyInfo(TypedDict):
    name: str
    team: str
    role: str


class RawResearchItem(TypedDict, total=False):
    stage: str
    query: str
    title: str
    url: str
    snippet: str
    content_markdown: str


class InsightHooks(TypedDict):
    business_hook: str
    tech_hook: str
    culture_hook: str


class LLMInvokeData(TypedDict, total=False):
    invoked: bool
    raw_response: str
    parsed_json: dict[str, Any]
    parse_success: bool
    used_fallback: bool
    error: str


class Diagnostics(TypedDict):
    errors: list[str]
    warnings: list[str]


class ResearchState(TypedDict):
    company_info: CompanyInfo
    scale: Optional[Scale]
    raw_research_data: list[RawResearchItem]
    insights: InsightHooks
    llm_invoke: LLMInvokeData
    diagnostics: Diagnostics


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str = ""


CLASSIFICATION_QUERY = PromptTemplate.from_template(
    "{company_name} 매출액 사원수 상장여부 투자단계"
)

SCALE_QUERY_TEMPLATES: dict[Scale, list[PromptTemplate]] = {
    "Large": [
        PromptTemplate.from_template("{company_name} {team_name} 기술 블로그"),
        PromptTemplate.from_template("{company_name} 2024 신년사 사업방향"),
    ],
    "Medium": [
        PromptTemplate.from_template("{company_name} 시장 점유율 경쟁사 비교"),
        PromptTemplate.from_template("{company_name} 최근 3년 신사업"),
    ],
    "Startup": [
        PromptTemplate.from_template("{company_name} 서비스 사용자 후기 페인포인트"),
        PromptTemplate.from_template("{ceo_name} 인터뷰 비전 {company_name}"),
    ],
}

INSIGHT_EXTRACTION_PROMPT = PromptTemplate.from_template(
    """
너는 자소서 리서치 전문가다. 아래 조사 내용을 바탕으로 지원자가 자소서에 직접 활용할 Hook을 만들어라.

[회사 정보]
- 회사명: {company_name}
- 팀명: {team_name}
- 직무: {role_name}
- 기업 규모: {scale}

[조사 본문]
{research_context}

아래 스키마의 JSON만 출력하라. 설명 문장은 절대 추가하지 마라.
{{
  "business_hook": "회사의 현재 전략과 나의 지원 동기를 연결할 포인트",
  "tech_hook": "해당 팀의 기술적 고민과 나의 기술 스택이 맞닿는 부분",
  "culture_hook": "회사가 선호하는 인재상과 나의 협업 스타일 매칭"
}}
""".strip()
)

_TOP_10_GROUP_KEYWORDS = (
    "삼성",
    "SK",
    "현대자동차",
    "LG",
    "롯데",
    "포스코",
    "한화",
    "GS",
    "신세계",
    "CJ",
    "HD현대",
    "LS",
)

_KOSPI_KEYWORDS = ("코스피", "KOSPI", "유가증권시장")
_KOSDAQ_KEYWORDS = ("코스닥", "KOSDAQ")
_MEDIUM_ASSOCIATION_KEYWORDS = ("중견기업연합회", "한국중견기업연합회")
_STARTUP_UNLISTED_KEYWORDS = ("비상장", "상장 전", "프리IPO", "pre-ipo")
_STARTUP_SERVICE_KEYWORDS = (
    "서비스",
    "플랫폼",
    "SaaS",
    "앱",
    "사용자",
    "프로덕트",
    "AI",
)


class WebSearchClient:
    def __init__(
        self,
        provider: str = "tavily",
        tavily_api_key: Optional[str] = None,
        serper_api_key: Optional[str] = None,
        timeout: int = 20,
    ) -> None:
        self.provider = provider.lower().strip()
        self.tavily_api_key = tavily_api_key or os.getenv("TAVILY_API_KEY")
        self.serper_api_key = serper_api_key or os.getenv("SERPER_API_KEY")
        self.timeout = timeout

    def search(self, query: str, k: int = 5) -> list[SearchResult]:
        if self.provider == "tavily":
            return self._search_tavily(query, k)
        if self.provider == "serper":
            return self._search_serper(query, k)
        raise ValueError("provider must be one of: tavily, serper")

    def _search_tavily(self, query: str, k: int) -> list[SearchResult]:
        if not self.tavily_api_key:
            raise RuntimeError("TAVILY_API_KEY is required when provider=tavily")

        response = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": self.tavily_api_key,
                "query": query,
                "search_depth": "advanced",
                "max_results": k,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()

        results: list[SearchResult] = []
        for item in payload.get("results", []):
            url = (item.get("url") or "").strip()
            if not url:
                continue
            results.append(
                SearchResult(
                    title=(item.get("title") or "").strip(),
                    url=url,
                    snippet=(item.get("content") or "").strip(),
                )
            )
        return results

    def _search_serper(self, query: str, k: int) -> list[SearchResult]:
        if not self.serper_api_key:
            raise RuntimeError("SERPER_API_KEY is required when provider=serper")

        response = requests.post(
            "https://google.serper.dev/search",
            headers={
                "X-API-KEY": self.serper_api_key,
                "Content-Type": "application/json",
            },
            json={"q": query, "num": k},
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()

        results: list[SearchResult] = []
        for item in payload.get("organic", []):
            url = (item.get("link") or "").strip()
            if not url:
                continue
            results.append(
                SearchResult(
                    title=(item.get("title") or "").strip(),
                    url=url,
                    snippet=(item.get("snippet") or "").strip(),
                )
            )
        return results


def fetch_markdown_via_jina(url: str, timeout: int = 20) -> str:
    normalized = url.strip()
    if not normalized:
        return ""
    if not normalized.startswith(("http://", "https://")):
        normalized = f"https://{normalized}"

    response = requests.get(
        f"https://r.jina.ai/{normalized}",
        headers={"User-Agent": "resume-research-agent/1.0"},
        timeout=timeout,
    )
    response.raise_for_status()
    return response.text


def create_initial_state(company_name: str, team_name: str, role_name: str) -> ResearchState:
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
    }


def _contains_any(text: str, keywords: Iterable[str]) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def _extract_employee_count(text: str) -> Optional[int]:
    patterns = (
        r"(?:사원수|임직원수|임직원|직원수|직원)\D{0,10}(\d{1,3}(?:,\d{3})+|\d+)\s*명",
        r"(\d{1,3}(?:,\d{3})+|\d+)\s*명\D{0,10}(?:임직원|직원)",
    )
    candidates: list[int] = []

    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            raw = match.group(1).replace(",", "")
            if not raw.isdigit():
                continue
            value = int(raw)
            if 10 <= value <= 5_000_000:
                candidates.append(value)

    if not candidates:
        return None
    return max(candidates)


def _extract_revenue_100m(text: str) -> Optional[int]:
    candidates: list[int] = []

    for match in re.finditer(
        r"(?:매출(?:액)?|연매출)\D{0,12}(\d{1,3}(?:,\d{3})+|\d+)\s*억(?:원)?",
        text,
        flags=re.IGNORECASE,
    ):
        raw = match.group(1).replace(",", "")
        if raw.isdigit():
            candidates.append(int(raw))

    for match in re.finditer(
        r"(?:매출(?:액)?|연매출)\D{0,12}(\d+(?:\.\d+)?)\s*조(?:원)?",
        text,
        flags=re.IGNORECASE,
    ):
        try:
            candidates.append(int(float(match.group(1)) * 10_000))
        except ValueError:
            continue

    if not candidates:
        return None
    return max(candidates)


def _extract_ceo_name(text: str, company_name: str) -> str:
    patterns = (
        r"(?:대표이사|대표|CEO)\s*[:：]?\s*([가-힣A-Za-z]{2,20})",
        r"([가-힣A-Za-z]{2,20})\s*(?:대표이사|대표|CEO)",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        candidate = match.group(1).strip()
        if candidate and candidate not in company_name:
            return candidate
    return f"{company_name} 대표"


def classify_scale_from_text(evidence_text: str) -> Scale:
    employee_count = _extract_employee_count(evidence_text)
    revenue_100m = _extract_revenue_100m(evidence_text)

    is_top_10_group = _contains_any(evidence_text, _TOP_10_GROUP_KEYWORDS)
    is_kospi = _contains_any(evidence_text, _KOSPI_KEYWORDS)
    is_kosdaq = _contains_any(evidence_text, _KOSDAQ_KEYWORDS)
    is_medium_association = _contains_any(evidence_text, _MEDIUM_ASSOCIATION_KEYWORDS)

    is_unlisted = _contains_any(evidence_text, _STARTUP_UNLISTED_KEYWORDS)
    has_series_funding = bool(
        re.search(r"(?:Series|시리즈)\s*[ABCabc]", evidence_text, flags=re.IGNORECASE)
    )
    service_or_innovation = _contains_any(evidence_text, _STARTUP_SERVICE_KEYWORDS)

    large_signals = 0
    if is_top_10_group:
        large_signals += 1
    if is_kospi:
        large_signals += 1
    if employee_count is not None and employee_count >= 1_000:
        large_signals += 1

    medium_signals = 0
    if revenue_100m is not None and revenue_100m >= 1_000:
        medium_signals += 1
    if is_kosdaq:
        medium_signals += 1
    if is_medium_association:
        medium_signals += 1

    startup_signals = 0
    if is_unlisted:
        startup_signals += 1
    if has_series_funding:
        startup_signals += 1
    if service_or_innovation:
        startup_signals += 1

    if large_signals >= 2:
        return "Large"
    if medium_signals >= 2 and large_signals == 0:
        return "Medium"
    if startup_signals >= 2 and large_signals == 0:
        return "Startup"

    if employee_count is not None and employee_count >= 1_000:
        return "Large"
    if is_kospi:
        return "Large"
    if revenue_100m is not None and revenue_100m >= 1_000:
        return "Medium"
    if is_kosdaq or is_medium_association:
        return "Medium"
    return "Startup"


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


def _pick_sentence(text: str, keywords: Iterable[str]) -> Optional[str]:
    sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
    for sentence in sentences:
        normalized = sentence.strip()
        if len(normalized) < 20:
            continue
        if _contains_any(normalized, keywords):
            return normalized
    return None


def _fallback_insights(
    company_name: str,
    team_name: str,
    role_name: str,
    research_context: str,
) -> InsightHooks:
    business = _pick_sentence(
        research_context,
        ("전략", "사업", "신사업", "성장", "시장", "점유율", "비전"),
    )
    tech = _pick_sentence(
        research_context,
        ("기술", "아키텍처", "개발", "데이터", "플랫폼", "AI", "엔지니어링"),
    )
    culture = _pick_sentence(
        research_context,
        ("문화", "협업", "인재", "가치", "원칙", "소통", "고객 중심"),
    )

    return {
        "business_hook": business
        or f"{company_name}의 최근 사업 방향과 {role_name} 지원 동기를 하나의 성장 스토리로 연결하세요.",
        "tech_hook": tech
        or f"{team_name} 팀의 기술 과제를 정리하고 본인의 핵심 기술 스택으로 해결 시나리오를 제시하세요.",
        "culture_hook": culture
        or f"{company_name}의 협업 방식에 맞춰 본인의 협업 습관과 커뮤니케이션 원칙을 구체 사례로 매칭하세요.",
    }


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

        seen_urls = {item.get("url", "") for item in raw_data if item.get("url")}
        for template in templates:
            query = template.format(
                company_name=company["name"],
                team_name=company["team"],
                role_name=company["role"],
                ceo_name=ceo_name,
            )
            log(f"[Research] query={query}")
            search_results, search_error = _safe_search(search_client, query, k=per_query_results)
            log(f"[Research] results={len(search_results)}")
            if search_error:
                diagnostics["errors"].append(
                    f"adaptive search failed for query='{query}': {search_error}"
                )
            if not search_results:
                diagnostics["warnings"].append(
                    f"adaptive search returned 0 results for query: {query}"
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
                        "query": query,
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
        diagnostics = dict(state.get("diagnostics", {"errors": [], "warnings": []}))
        diagnostics.setdefault("errors", [])
        diagnostics.setdefault("warnings", [])

        research_context = _build_research_context(raw_data)
        log(f"[Insight] context_chars={len(research_context)} llm={'on' if llm else 'off'}")
        if not research_context.strip():
            diagnostics["warnings"].append(
                "no research context available; using fallback insight generation."
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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Company Research Agent for resume insights (LangGraph + RAG)",
    )
    parser.add_argument("--company", required=True, help="Company name")
    parser.add_argument("--team", required=True, help="Target team name")
    parser.add_argument("--role", required=True, help="Target role name")
    parser.add_argument(
        "--provider",
        default=os.getenv("SEARCH_PROVIDER", "tavily"),
        choices=("tavily", "serper"),
        help="Search backend",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        help="OpenAI model name for insight extraction",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=os.getenv("VERBOSE", "0").strip() in ("1", "true", "TRUE", "yes", "YES"),
        help="Print intermediate progress logs to stderr",
    )
    parser.add_argument(
        "--output",
        default="run_output.json",
        help="File path to save final JSON output (default: run_output.json)",
    )

    args = parser.parse_args()

    try:
        result = run_research(
            company_name=args.company,
            team_name=args.team,
            role_name=args.role,
            provider=args.provider,
            model=args.model,
            verbose=args.verbose,
        )
    except Exception as exc:
        raise SystemExit(f"Research run failed: {exc}") from exc

    output_text = json.dumps(result, ensure_ascii=False, indent=2)
    output_hash = hashlib.sha256(output_text.encode("utf-8")).hexdigest()[:12]
    output_path = Path(args.output).expanduser().resolve()
    with output_path.open("w", encoding="utf-8") as output_file:
        output_file.write(output_text + "\n")
    print(
        f"[Output] file={output_path} sha256={output_hash}",
        file=sys.stderr,
        flush=True,
    )
    print(output_text)


if __name__ == "__main__":
    main()
