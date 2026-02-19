from __future__ import annotations

import json
from typing import Any

from langchain_core.prompts import PromptTemplate


ESSAY_WRITING_PROMPT = PromptTemplate.from_template(
    """
너는 한국어 자기소개서 작성 코치다.
아래 입력 JSON 기반 컨텍스트를 근거로 4개 문항 초안을 작성하라.

[채용공고/지원 정보]
{job_posting_context}

[지원자 프로필]
{user_profile_context}

[기업 리서치]
{research_context}

[작성 규칙]
1. 사실/근거는 반드시 입력 JSON 안에서만 사용한다.
2. 근거가 부족하면 과장하지 말고 보수적으로 작성한다.
3. 문체는 일관된 1인칭 서술형으로 작성한다.
4. 각 문항은 5~8문장으로 작성한다.
5. 설명 문장 없이 JSON만 출력한다.

아래 스키마의 JSON만 출력하라.
{{
  "지원동기": "string",
  "성장과정": "string",
  "성격의 장단점": "string",
  "입사 후 포부": "string"
}}
""".strip()
)


def _safe_join(items: list[str], sep: str = ", ") -> str:
    normalized = [item.strip() for item in items if isinstance(item, str) and item.strip()]
    return sep.join(normalized)


def _flatten_strings(value: Any, max_items: int = 16) -> list[str]:
    out: list[str] = []

    def walk(node: Any) -> None:
        nonlocal out
        if len(out) >= max_items:
            return
        if isinstance(node, str):
            text = node.strip()
            if text:
                out.append(text)
            return
        if isinstance(node, list):
            for item in node:
                walk(item)
                if len(out) >= max_items:
                    return
            return
        if isinstance(node, dict):
            for item in node.values():
                walk(item)
                if len(out) >= max_items:
                    return

    walk(value)
    return out


def _compact_json(data: dict[str, Any], max_chars: int = 2_400) -> str:
    try:
        text = json.dumps(data, ensure_ascii=False, indent=2)
    except Exception:
        text = str(data)
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n...(truncated)"


def extract_company_team_role(
    job_posting: dict[str, Any],
    research_result: dict[str, Any],
    company_name: str = "",
    team_name: str = "",
    role_name: str = "",
) -> tuple[str, str, str]:
    company = (company_name or "").strip()
    team = (team_name or "").strip()
    role = (role_name or "").strip()

    company_block = job_posting.get("company")
    position_block = job_posting.get("position")
    research_company_info = research_result.get("company_info")

    if not company and isinstance(company_block, dict):
        company = str(company_block.get("name") or "").strip()
    if not team and isinstance(position_block, dict):
        team = str(position_block.get("department") or "").strip()
    if not role and isinstance(position_block, dict):
        role = str(position_block.get("title") or "").strip()

    if not company and isinstance(research_company_info, dict):
        company = str(research_company_info.get("name") or "").strip()
    if not team and isinstance(research_company_info, dict):
        team = str(research_company_info.get("team") or "").strip()
    if not role and isinstance(research_company_info, dict):
        role = str(research_company_info.get("role") or "").strip()

    return company, team, role


def format_job_posting_context(job_posting: dict[str, Any]) -> str:
    company = job_posting.get("company", {})
    position = job_posting.get("position", {})
    requirements = job_posting.get("requirements", {})
    talent_keywords = _flatten_strings(job_posting.get("talent_keywords"), max_items=10)
    company_research = job_posting.get("company_research", {})

    lines = [
        f"- 회사명: {str(company.get('name') or '').strip() or '정보 없음'}",
        f"- 산업: {str(company.get('industry') or '').strip() or '정보 없음'}",
        f"- 직무명: {str(position.get('title') or '').strip() or '정보 없음'}",
        f"- 부서: {str(position.get('department') or '').strip() or '정보 없음'}",
        f"- 주요업무: {_safe_join(_flatten_strings(requirements.get('main_tasks'), max_items=8)) or '정보 없음'}",
        f"- 자격요건: {_safe_join(_flatten_strings(requirements.get('qualifications'), max_items=8)) or '정보 없음'}",
        f"- 우대사항: {_safe_join(_flatten_strings(requirements.get('preferred'), max_items=8)) or '정보 없음'}",
        f"- 기술스택: {_safe_join(_flatten_strings(requirements.get('tech_stack'), max_items=10)) or '정보 없음'}",
        f"- 인재상 키워드: {_safe_join(talent_keywords) or '정보 없음'}",
        f"- 회사 리서치: {_compact_json(company_research, max_chars=1_800) if isinstance(company_research, dict) else '정보 없음'}",
    ]
    return "\n".join(lines)


def format_user_profile_context(user_profile: dict[str, Any]) -> str:
    profile = user_profile.get("user_profile", {})
    tech_stack = user_profile.get("tech_stack", {})
    experiences = user_profile.get("experiences", [])
    background = user_profile.get("background", {})

    summary = str(profile.get("summary") or "").strip()
    name = str(profile.get("name") or "").strip()
    location = str(profile.get("location") or "").strip()

    tech_items = _flatten_strings(tech_stack, max_items=12)
    exp_lines: list[str] = []
    if isinstance(experiences, list):
        for exp in experiences[:4]:
            if not isinstance(exp, dict):
                continue
            title = str(exp.get("title") or "").strip()
            role = str(exp.get("role") or "").strip()
            star = exp.get("star_content")
            result = str(star.get("result") or "").strip() if isinstance(star, dict) else ""
            line = " / ".join(part for part in (title, role, result) if part)
            if line:
                exp_lines.append(line)

    background_points = _flatten_strings(background, max_items=10)

    lines = [
        f"- 이름: {name or '정보 없음'}",
        f"- 거주지: {location or '정보 없음'}",
        f"- 요약: {summary or '정보 없음'}",
        f"- 기술스택: {_safe_join(tech_items) or '정보 없음'}",
        f"- 주요경험: {_safe_join(exp_lines, sep=' | ') or '정보 없음'}",
        f"- 배경 키워드: {_safe_join(background_points) or '정보 없음'}",
    ]
    return "\n".join(lines)


def format_research_context(research_result: dict[str, Any]) -> str:
    company_info = research_result.get("company_info", {})
    insights = research_result.get("insights", {})
    scale = research_result.get("scale")
    references = research_result.get("reference_urls", [])

    lines = [
        f"- 기업규모 추정: {scale or '정보 없음'}",
        f"- company_info: {_compact_json(company_info, max_chars=800) if isinstance(company_info, dict) else '정보 없음'}",
        f"- business_hook: {str(insights.get('business_hook') or '').strip() if isinstance(insights, dict) else ''}",
        f"- tech_hook: {str(insights.get('tech_hook') or '').strip() if isinstance(insights, dict) else ''}",
        f"- culture_hook: {str(insights.get('culture_hook') or '').strip() if isinstance(insights, dict) else ''}",
        f"- 참고 URL 수: {len(references) if isinstance(references, list) else 0}",
    ]
    return "\n".join(lines)
