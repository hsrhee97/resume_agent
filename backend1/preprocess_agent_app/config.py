"""
config.py
=========
프롬프트 템플릿, JSON 스키마 정의, 전역 설정
"""

# ============================================================
# 사용자 프로필 JSON 스키마 (PDF에서 추출할 구조)
# ============================================================
USER_PROFILE_SCHEMA = {
    "user_profile": {
        "name": "이름",
        "email": "이메일",
        "phone": "전화번호",
        "location": "거주지",
        "links": {
            "github": "GitHub URL",
            "portfolio": "포트폴리오 URL",
            "book": "기술 서적/블로그 URL"
        },
        "summary": "한줄 요약 (어떤 엔지니어인지)"
    },
    "tech_stack": {
        "ai_agent_ecosystem": ["LangChain", "LangGraph 등 에이전트 관련 기술"],
        "languages": ["프로그래밍 언어"],
        "llm_ops": ["LLM 관련 도구/기술"],
        "data_science_ml": ["데이터/ML 프레임워크"],
        "databases": ["데이터베이스"],
        "collaboration_tools": ["협업 도구"]
    },
    "education": [
        {
            "institution": "학교/기관명",
            "course_name": "과정명 (해당 시)",
            "degree": "학위 (해당 시)",
            "major": "전공",
            "minor": "부전공 (해당 시)",
            "period": "기간",
            "gpa": "학점",
            "honors": ["수상/우수 내역"],
            "details": ["세부 설명"]
        }
    ],
    "experiences": [
        {
            "id": "exp_고유ID",
            "category": "Work Experience / Project / Publication / Open Source 등",
            "title": "프로젝트/업무 제목",
            "organization": "소속 조직",
            "period": "기간",
            "role": "역할",
            "description": "한줄 설명",
            "star_content": {
                "situation": "상황 - 어떤 배경/문제가 있었는지",
                "task": "과제 - 내가 해결해야 할 것",
                "action": "행동 - 구체적으로 한 일",
                "result": "결과 - 정량적/정성적 성과"
            },
            "tech_keywords": ["사용 기술"],
            "meta_tags": ["역량 태그 (예: 아키텍처설계, 비용최적화)"]
        }
    ],
    "background": {
        "core_identity": {
            "vision": "AI/기술에 대한 미래 가치 정의",
            "core_values": ["핵심 가치관"],
            "identity_tags": ["#정체성_태그"],
            "one_liner": "자소서 첫 문장용 한줄 정의",
            "working_philosophy": "일에 대한 근본 신념"
        },
        "transformation_milestones": [
            {
                "id": "milestone_01",
                "title": "마일스톤 제목",
                "period": "시기",
                "type": "재수/편입/진로전환/취업실패/건강/기타",
                "context": "당시 상황",
                "challenge": "구체적 어려움",
                "action": "취한 행동",
                "result": "결과/성과",
                "engineering_mapping": "엔지니어 역량으로의 전환",
                "lesson": "핵심 교훈"
            }
        ],
        "conflict_resolution": [
            {
                "id": "conflict_01",
                "project_id": "관련 experience id",
                "team_size": 0,
                "my_role": "역할",
                "conflict_type": "의견충돌/무임승차/방향성_불일치/커뮤니케이션_부재/일정지연/기타",
                "situation": "상황 (STAR의 S+T)",
                "action": "구체적 행동",
                "result": "해결 결과",
                "communication_skill": "드러나는 소통 역량"
            }
        ],
        "future_contribution": {
            "short_term": {"period": "1yr", "goal": "", "specific_actions": []},
            "mid_term": {"period": "3yr+", "goal": "", "specific_actions": []},
            "long_term": {"period": "5yr+", "goal": "", "specific_actions": []},
            "transferable_strengths": ["이전 가능한 핵심 역량"],
            "domain_fit_keywords": ["타겟 기업/직무 매칭 키워드"]
        }
    }
}


# ============================================================
# 채용공고 JSON 스키마
# ============================================================
JOB_POSTING_SCHEMA = {
    "company": {
        "name": "회사명",
        "industry": "업종",
        "size": "기업 규모 (대기업/중견/스타트업 등)",
        "location": "소재지"
    },
    "position": {
        "title": "채용 포지션명",
        "department": "부서/팀",
        "job_type": "신입/경력/인턴",
        "employment_type": "정규직/계약직/인턴"
    },
    "requirements": {
        "main_tasks": ["주요 업무 1", "주요 업무 2"],
        "qualifications": ["자격 요건"],
        "preferred": ["우대 사항"],
        "tech_stack": ["요구 기술스택"]
    },
    "talent_keywords": ["인재상 키워드"],
    "benefits": ["복리후생"],
    "deadline": "마감일",
    "essay_questions": [
        {
            "id": 1,
            "question": "자소서 문항 내용",
            "max_chars": 500
        }
    ],
    "company_research": {
        "mission_vision": "회사 미션/비전 요약",
        "core_business": ["핵심 사업 영역"],
        "recent_news": [
            {"title": "뉴스 제목", "summary": "요약", "relevance": "high/mid/low"}
        ],
        "tech_culture": "기술 문화 요약",
        "growth_direction": "성장 방향성"
    }
}


# ============================================================
# LLM 프롬프트 템플릿
# ============================================================
PROMPTS = {
    # ---- Task A: PDF → 프로필 추출 ----
    "extract_profile_from_pdf": """당신은 한국어 자소서/이력서 데이터 추출 전문가입니다.
아래 텍스트에서 정보를 추출하여 주어진 JSON 스키마에 맞게 채워주세요.

[규칙]
1. 텍스트에서 명시적으로 확인되는 정보만 채우세요.
2. 확인할 수 없는 항목은 빈 문자열("") 또는 빈 배열([])로 두세요.
3. experiences의 각 항목은 STAR(Situation-Task-Action-Result) 형식으로 작성하세요.
4. tech_keywords와 meta_tags는 텍스트에서 추론 가능한 것만 포함하세요.
5. background 섹션은 자소서에 드러나는 가치관, 위기 극복, 갈등 해결, 미래 계획을 추출하세요.
6. 반드시 유효한 JSON만 반환하세요. 설명이나 마크다운 없이 JSON만 출력하세요.

[JSON 스키마]
{schema}

[자소서 텍스트]
{text}

JSON:""",

    # ---- Task B: 채용공고 → 구조화 ----
    "extract_job_posting": """당신은 한국 채용공고 데이터 추출 전문가입니다.
아래 채용공고 텍스트에서 정보를 추출하여 JSON 스키마에 맞게 채워주세요.

[규칙]
1. 주요업무, 자격요건, 우대사항을 명확히 구분하세요.
2. 자소서 문항이 있으면 essay_questions에 포함하세요.
3. 기술스택은 구체적 기술명으로 추출하세요 (예: Python, LangChain, AWS 등).
4. 인재상 키워드는 공고에서 강조하는 가치/역량을 추출하세요.
5. 확인 불가한 항목은 빈 값으로 두세요.
6. 반드시 유효한 JSON만 반환하세요.

[JSON 스키마]
{schema}

[채용공고 텍스트]
{text}

JSON:""",

    # ---- 회사 리서치 정리 ----
    "research_company": """당신은 기업 분석 전문가입니다.
'{company_name}'에 대한 검색 결과를 분석하여, '{position}' 지원자가 자소서 작성 시 활용할 수 있는 기업 정보를 정리하세요.

[규칙]
1. 회사의 미션/비전, 핵심 사업, 최근 동향을 정리하세요.
2. 기술 문화와 개발 환경에 대한 정보를 포함하세요.
3. 회사의 성장 방향성과 전략을 파악하세요.
4. 자소서에서 "이 회사에 왜 지원하는지"에 활용할 수 있는 팩트를 강조하세요.
5. 검색 결과에서 확인되지 않는 내용은 추측하지 마세요.
6. 반드시 유효한 JSON만 반환하세요.

[검색 결과]
{search_results}

JSON 형식:
{{
    "mission_vision": "미션/비전 요약",
    "core_business": ["핵심 사업 1", "핵심 사업 2"],
    "recent_news": [
        {{"title": "뉴스 제목", "summary": "요약", "relevance": "high/mid/low"}}
    ],
    "tech_culture": "기술 문화 요약",
    "growth_direction": "성장 방향성",
    "key_facts_for_cover_letter": ["자소서에 활용 가능한 핵심 팩트"]
}}

JSON:""",
}


# ============================================================
# 기타 설정
# ============================================================
SETTINGS = {
    "request_timeout": 15,
    "user_agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "max_retries": 3,
    "retry_delay": 2.0,
    "chunk_max_chars": 3000,
    "chunk_overlap_chars": 200,
}