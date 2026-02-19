from __future__ import annotations

import re
from typing import Iterable, Optional

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
