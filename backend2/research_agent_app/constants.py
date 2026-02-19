from __future__ import annotations

from langchain_core.prompts import PromptTemplate

from .types import Scale

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
