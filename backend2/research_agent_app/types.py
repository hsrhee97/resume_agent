from __future__ import annotations

from typing import Any, Literal, Optional, TypedDict

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
