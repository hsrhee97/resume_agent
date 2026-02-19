from __future__ import annotations

import re
from typing import Any, Iterable, Optional

from .constants import (
    KOSDAQ_KEYWORDS,
    KOSPI_KEYWORDS,
    MEDIUM_ASSOCIATION_KEYWORDS,
    STARTUP_SERVICE_KEYWORDS,
    STARTUP_UNLISTED_KEYWORDS,
    TOP_10_GROUP_KEYWORDS,
)
from .types import InsightHooks, Scale


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

    is_top_10_group = _contains_any(evidence_text, TOP_10_GROUP_KEYWORDS)
    is_kospi = _contains_any(evidence_text, KOSPI_KEYWORDS)
    is_kosdaq = _contains_any(evidence_text, KOSDAQ_KEYWORDS)
    is_medium_association = _contains_any(evidence_text, MEDIUM_ASSOCIATION_KEYWORDS)

    is_unlisted = _contains_any(evidence_text, STARTUP_UNLISTED_KEYWORDS)
    has_series_funding = bool(
        re.search(r"(?:Series|시리즈)\s*[ABCabc]", evidence_text, flags=re.IGNORECASE)
    )
    service_or_innovation = _contains_any(evidence_text, STARTUP_SERVICE_KEYWORDS)

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


def _pick_sentence(text: str, keywords: Iterable[str]) -> Optional[str]:
    sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
    for sentence in sentences:
        normalized = sentence.strip()
        if len(normalized) < 20:
            continue
        if _contains_any(normalized, keywords):
            return normalized
    return None


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _flatten_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(_flatten_strings(item))
        return out
    if isinstance(value, dict):
        out: list[str] = []
        for item in value.values():
            out.extend(_flatten_strings(item))
        return out
    return []


def _pick_profile_tech_summary(user_profile: Optional[dict[str, Any]]) -> str:
    if not isinstance(user_profile, dict):
        return ""
    tech_stack = user_profile.get("tech_stack")
    if not isinstance(tech_stack, dict):
        return ""

    ordered_keys = (
        "ai_agent_ecosystem",
        "languages",
        "llm_ops",
        "data_science_ml",
        "databases",
        "collaboration_tools",
    )
    candidates: list[str] = []
    for key in ordered_keys:
        values = _flatten_strings(tech_stack.get(key))
        candidates.extend(values)

    deduped: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        lowered = item.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        deduped.append(item)
        if len(deduped) >= 6:
            break

    return ", ".join(deduped)


def _pick_profile_collab_style(user_profile: Optional[dict[str, Any]]) -> str:
    if not isinstance(user_profile, dict):
        return ""

    background = user_profile.get("background")
    if isinstance(background, dict):
        core_identity = background.get("core_identity")
        if isinstance(core_identity, dict):
            value = _normalize_text(core_identity.get("working_philosophy"))
            if value:
                return value

        conflict_resolution = background.get("conflict_resolution")
        if isinstance(conflict_resolution, list):
            for item in conflict_resolution:
                if not isinstance(item, dict):
                    continue
                value = _normalize_text(item.get("communication_skill"))
                if value:
                    return value

    profile_block = user_profile.get("user_profile")
    if isinstance(profile_block, dict):
        summary = _normalize_text(profile_block.get("summary"))
        if summary:
            return summary
    return ""


def _pick_profile_motivation(user_profile: Optional[dict[str, Any]]) -> str:
    if not isinstance(user_profile, dict):
        return ""

    background = user_profile.get("background")
    if isinstance(background, dict):
        future_contribution = background.get("future_contribution")
        if isinstance(future_contribution, dict):
            short_term = future_contribution.get("short_term")
            if isinstance(short_term, dict):
                goal = _normalize_text(short_term.get("goal"))
                if goal:
                    return goal

            transferable = _flatten_strings(future_contribution.get("transferable_strengths"))
            if transferable:
                return ", ".join(transferable[:3])

            domain_fit = _flatten_strings(future_contribution.get("domain_fit_keywords"))
            if domain_fit:
                return ", ".join(domain_fit[:3])

    profile_block = user_profile.get("user_profile")
    if isinstance(profile_block, dict):
        summary = _normalize_text(profile_block.get("summary"))
        if summary:
            return summary
    return ""


def _fallback_insights(
    company_name: str,
    team_name: str,
    role_name: str,
    research_context: str,
    user_profile: Optional[dict[str, Any]] = None,
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

    motivation = _pick_profile_motivation(user_profile)
    tech_summary = _pick_profile_tech_summary(user_profile)
    collab_style = _pick_profile_collab_style(user_profile)

    if motivation:
        business_default = (
            f"{company_name}의 최근 사업 방향과 '{motivation}'를 연결해 {role_name} 지원 동기를 구성하세요."
        )
    else:
        business_default = (
            f"{company_name}의 최근 사업 방향을 정리하고, 지원 동기는 제공된 사용자 정보 범위 내에서만 작성하세요."
        )

    if tech_summary:
        tech_default = (
            f"{team_name} 팀의 기술 과제에 대해 지원자 기술 스택({tech_summary})을 중심으로 해결 시나리오를 연결하세요."
        )
    else:
        tech_default = (
            f"{team_name} 팀의 기술 과제를 정리하고, 지원자 기술 스택 정보가 부족함을 명시한 뒤 추가 정보가 필요하다고 작성하세요."
        )

    if collab_style:
        culture_default = (
            f"{company_name}의 협업 방식과 지원자 협업 스타일('{collab_style}')의 접점을 구체 사례 중심으로 작성하세요."
        )
    else:
        culture_default = (
            f"{company_name}의 협업 방식은 요약하되, 지원자 협업 스타일 정보가 부족함을 명시하고 보완 포인트를 제안하세요."
        )

    return {
        "business_hook": business or business_default,
        "tech_hook": tech or tech_default,
        "culture_hook": culture or culture_default,
    }
