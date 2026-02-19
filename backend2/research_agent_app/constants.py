from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from langchain_core.prompts import PromptTemplate

from .types import Scale


def _load_backend1_schemas() -> tuple[dict[str, Any], dict[str, Any]]:
    config_path = (
        Path(__file__).resolve().parents[2] / "backend1" / "preprocess_agent_app" / "config.py"
    )
    if not config_path.exists():
        return {}, {}

    try:
        spec = importlib.util.spec_from_file_location("backend1_preprocess_config", config_path)
        if spec is None or spec.loader is None:
            return {}, {}
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except Exception:
        return {}, {}

    user_profile_schema = getattr(module, "USER_PROFILE_SCHEMA", {})
    job_posting_schema = getattr(module, "JOB_POSTING_SCHEMA", {})

    if not isinstance(user_profile_schema, dict):
        user_profile_schema = {}
    if not isinstance(job_posting_schema, dict):
        job_posting_schema = {}

    return user_profile_schema, job_posting_schema


def _schema_outline(schema: dict[str, Any], depth: int = 0, max_depth: int = 2) -> str:
    if not isinstance(schema, dict):
        return ""
    if depth >= max_depth:
        return ""

    lines: list[str] = []
    for key, value in schema.items():
        if isinstance(value, dict):
            child_keys = ", ".join(value.keys())
            lines.append(f"- {key}: {{{child_keys}}}")
            child_outline = _schema_outline(value, depth + 1, max_depth=max_depth)
            if child_outline:
                lines.append(child_outline)
        elif isinstance(value, list):
            lines.append(f"- {key}: [list]")
        else:
            lines.append(f"- {key}: value")
    return "\n".join(lines)


USER_PROFILE_SCHEMA_REF, JOB_POSTING_SCHEMA_REF = _load_backend1_schemas()
USER_PROFILE_SCHEMA_OUTLINE = _schema_outline(USER_PROFILE_SCHEMA_REF)
JOB_POSTING_SCHEMA_OUTLINE = _schema_outline(JOB_POSTING_SCHEMA_REF)


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
너는 자소서 리서치 전문가다.
아래 조사 내용과 입력 JSON을 바탕으로 자소서에 바로 쓸 수 있는 Hook을 만들어라.

[회사 정보]
- 회사명: {company_name}
- 팀명: {team_name}
- 직무: {role_name}
- 기업 규모: {scale}

[입력 스키마 기준 (backend1/preprocess_agent_app/config.py)]
[USER_PROFILE_SCHEMA 핵심 키]
{user_profile_schema_outline}

[JOB_POSTING_SCHEMA 핵심 키]
{job_posting_schema_outline}

[채용공고 JSON (JOB_POSTING_SCHEMA 기반)]
{job_posting_context}

[지원자 JSON (USER_PROFILE_SCHEMA 기반)]
{user_profile_context}

[외부 리서치 본문]
{research_context}

[작성 규칙]
1. "나의 지원 동기/기술 스택/협업 스타일" 관련 내용은 반드시 지원자 JSON의 근거만 사용한다.
2. 지원자 JSON 근거가 부족하면 추정하지 말고 "지원자 정보 부족"을 명시한다.
3. 채용공고 JSON의 requirements/talent_keywords를 우선 반영한다.
4. 반드시 아래 스키마의 JSON만 출력한다. 설명 문장은 절대 추가하지 마라.

{{
  "business_hook": "채용공고와 회사 방향, 그리고 지원자 동기(근거 기반)를 연결한 포인트",
  "tech_hook": "직무 기술요건과 지원자 기술 스택(근거 기반)의 접점",
  "culture_hook": "채용공고 인재상과 지원자 협업 스타일(근거 기반)의 접점"
}}
""".strip()
)

TOP_10_GROUP_KEYWORDS = (
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

KOSPI_KEYWORDS = ("코스피", "KOSPI", "유가증권시장")
KOSDAQ_KEYWORDS = ("코스닥", "KOSDAQ")
MEDIUM_ASSOCIATION_KEYWORDS = ("중견기업연합회", "한국중견기업연합회")
STARTUP_UNLISTED_KEYWORDS = ("비상장", "상장 전", "프리IPO", "pre-ipo")
STARTUP_SERVICE_KEYWORDS = (
    "서비스",
    "플랫폼",
    "SaaS",
    "앱",
    "사용자",
    "프로덕트",
    "AI",
)
