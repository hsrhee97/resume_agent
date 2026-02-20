from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import Any, Optional

from dotenv import load_dotenv

from .prompts import (
    ESSAY_WRITING_PROMPT,
    extract_company_team_role,
    format_job_posting_context,
    format_research_context,
    format_user_profile_context,
)

# Load API keys and runtime options from .env if present.
load_dotenv()

SECTION_KEYS = ("지원동기", "성장과정", "성격의 장단점", "입사 후 포부")


def _flatten_strings(value: Any, max_items: int = 8) -> list[str]:
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


def _coerce_essay_sections(data: Optional[dict[str, Any]]) -> Optional[dict[str, str]]:
    if not isinstance(data, dict):
        return None

    if not all(key in data for key in SECTION_KEYS):
        return None

    out: dict[str, str] = {}
    for key in SECTION_KEYS:
        out[key] = str(data.get(key) or "").strip()
    if not all(out.values()):
        return None
    return out


def _sanitize_hook_text(text: str) -> str:
    cleaned = str(text or "").strip()
    if not cleaned:
        return ""
    cleaned = re.sub(r"\s+", " ", cleaned)
    for token in ("작성하세요", "구성하세요", "연결하세요", "제시하세요"):
        cleaned = cleaned.replace(token, "")
    cleaned = cleaned.strip(" .")
    return cleaned


def _normalize_revision_instruction(text: str) -> str:
    cleaned = str(text or "").strip()
    if not cleaned:
        return "없음"
    return re.sub(r"\s+", " ", cleaned)


def create_default_llm(model: str = "gpt-4.1-mini", temperature: float = 0.3) -> Any:
    try:
        from langchain_openai import ChatOpenAI
    except ImportError:
        return None

    if not os.getenv("OPENAI_API_KEY"):
        return None

    return ChatOpenAI(model=model, temperature=temperature)


def _fallback_essays(
    user_profile: dict[str, Any],
    job_posting: dict[str, Any],
    research_result: dict[str, Any],
    company_name: str,
    team_name: str,
    role_name: str,
) -> dict[str, str]:
    profile = user_profile.get("user_profile", {})
    requirements = job_posting.get("requirements", {})
    research_insights = research_result.get("insights", {})

    summary = str(profile.get("summary") or "").strip()
    main_tasks = _flatten_strings(requirements.get("main_tasks"), max_items=3)
    qualifications = _flatten_strings(requirements.get("qualifications"), max_items=3)
    tech_stack = _flatten_strings(user_profile.get("tech_stack"), max_items=8)
    experiences = user_profile.get("experiences", [])
    future = user_profile.get("background", {})

    top_exp = ""
    if isinstance(experiences, list) and experiences:
        first_exp = experiences[0]
        if isinstance(first_exp, dict):
            title = str(first_exp.get("title") or "").strip()
            role = str(first_exp.get("role") or "").strip()
            result = ""
            star = first_exp.get("star_content")
            if isinstance(star, dict):
                result = str(star.get("result") or "").strip()
            top_exp = " / ".join(part for part in (title, role, result) if part)

    future_items = _flatten_strings(future, max_items=6)

    business_hook = ""
    tech_hook = ""
    culture_hook = ""
    if isinstance(research_insights, dict):
        business_hook = _sanitize_hook_text(research_insights.get("business_hook"))
        tech_hook = _sanitize_hook_text(research_insights.get("tech_hook"))
        culture_hook = _sanitize_hook_text(research_insights.get("culture_hook"))

    motivation = (
        f"{company_name} {role_name} 직무에 지원한 이유는, "
        f"{business_hook or '채용공고에서 제시한 핵심 과제를 실무 경험으로 연결할 수 있다고 판단했기 때문'}입니다. "
        f"{summary or '지원자의 경험 요약 정보를 바탕으로'} "
        f"{' / '.join(main_tasks) if main_tasks else '주요업무'}를 수행하며 팀 성과에 기여하고자 합니다. "
        f"특히 {' / '.join(qualifications) if qualifications else '직무 요건'}을 중심으로 빠르게 온보딩하여 "
        f"{team_name or '해당 팀'}의 실행력을 높이겠습니다."
    )

    growth = (
        f"저는 {top_exp or '여러 프로젝트 경험'}을 통해 문제를 구조화하고 끝까지 해결하는 습관을 길렀습니다. "
        "초기에는 범위를 넓게 보기보다 눈앞의 과제 해결에 집중하는 경향이 있었지만, "
        "반복적으로 회고하면서 목표-지표-실행 순서로 일하는 방식을 체화했습니다. "
        "이 과정에서 협업과 커뮤니케이션의 중요성을 배웠고, 이후에는 이해관계자와 기준을 먼저 맞춘 뒤 실행하는 방식으로 성장했습니다."
    )

    strengths_weaknesses = (
        "저의 강점은 기술 과제를 실행 가능한 단위로 분해해 빠르게 결과를 내는 점입니다. "
        f"{', '.join(tech_stack[:6]) if tech_stack else '기술 스택'}을 기반으로 요구사항을 구현하고, "
        f"{tech_hook or '팀의 기술 과제'}와 연결해 개선 포인트를 제시할 수 있습니다. "
        "단점은 완성도를 높이려다 초기에 속도를 늦출 때가 있다는 점인데, "
        "이를 보완하기 위해 우선순위와 마감 시점을 선명하게 두고 중간 공유 주기를 짧게 가져가고 있습니다."
    )

    future_plan = (
        f"입사 후에는 먼저 {team_name or '해당 팀'}의 업무 흐름과 도메인을 빠르게 학습해 "
        f"{role_name or '직무'}로서 즉시 기여 가능한 과제를 책임지겠습니다. "
        "중기적으로는 자동화와 품질 개선이 가능한 반복 업무를 발굴해 생산성을 높이고, "
        f"장기적으로는 {company_name or '회사'}의 핵심 서비스 경쟁력에 기여하는 기능을 주도하겠습니다. "
        f"{culture_hook or ''} "
        f"{' '.join(future_items[:2]) if future_items else ''}".strip()
    )

    return {
        "지원동기": motivation,
        "성장과정": growth,
        "성격의 장단점": strengths_weaknesses,
        "입사 후 포부": future_plan,
    }


def generate_essay_drafts(
    user_profile: dict[str, Any],
    job_posting: dict[str, Any],
    research_result: dict[str, Any],
    company_name: str = "",
    team_name: str = "",
    role_name: str = "",
    revision_instruction: str = "",
    model: str = "gpt-4.1-mini",
    temperature: float = 0.3,
) -> dict[str, Any]:
    diagnostics = {"errors": [], "warnings": []}
    llm_invoke: dict[str, Any] = {
        "invoked": False,
        "raw_response": "",
        "parse_success": False,
        "used_fallback": False,
    }

    company, team, role = extract_company_team_role(
        job_posting=job_posting,
        research_result=research_result,
        company_name=company_name,
        team_name=team_name,
        role_name=role_name,
    )

    if not company:
        diagnostics["warnings"].append("company name is empty; using placeholder text.")
        company = "지원 회사"
    if not team:
        diagnostics["warnings"].append("team name is empty; using placeholder text.")
        team = "지원 팀"
    if not role:
        diagnostics["warnings"].append("role name is empty; using placeholder text.")
        role = "지원 직무"

    user_profile_context = format_user_profile_context(user_profile)
    job_posting_context = format_job_posting_context(job_posting)
    research_context = format_research_context(research_result)
    revision_instruction_text = _normalize_revision_instruction(revision_instruction)

    essays: Optional[dict[str, str]] = None
    llm = create_default_llm(model=model, temperature=temperature)
    if llm is None:
        diagnostics["warnings"].append("LLM unavailable; using fallback writer.")
    else:
        prompt = ESSAY_WRITING_PROMPT.format(
            user_profile_context=user_profile_context,
            job_posting_context=job_posting_context,
            research_context=research_context,
            revision_instruction=revision_instruction_text,
        )
        try:
            llm_invoke["invoked"] = True
            response = llm.invoke(prompt)
            content = response.content if hasattr(response, "content") else str(response)
            llm_invoke["raw_response"] = str(content)
            parsed_json = _extract_json_object(str(content))
            if parsed_json is not None:
                llm_invoke["parsed_json"] = parsed_json
            essays = _coerce_essay_sections(parsed_json)
            llm_invoke["parse_success"] = essays is not None
        except Exception as exc:
            diagnostics["errors"].append(f"llm invoke failed: {type(exc).__name__}: {exc}")
            llm_invoke["error"] = f"{type(exc).__name__}: {exc}"

    if essays is None:
        llm_invoke["used_fallback"] = True
        essays = _fallback_essays(
            user_profile=user_profile,
            job_posting=job_posting,
            research_result=research_result,
            company_name=company,
            team_name=team,
            role_name=role,
        )

    return {
        "company_info": {"name": company, "team": team, "role": role},
        "essay_templates": essays,
        "llm_invoke": llm_invoke,
        "diagnostics": diagnostics,
        "input_context": {
            "user_profile_attached": bool(user_profile),
            "job_posting_attached": bool(job_posting),
            "research_result_attached": bool(research_result),
            "revision_instruction_attached": revision_instruction_text != "없음",
        },
        "generated_at": datetime.now().isoformat(),
    }
