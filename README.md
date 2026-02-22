# CoverFit

CoverFit은 취업 준비의 가장 큰 병목인 **기업별 맞춤 자소서 작성**을 자동화하는  
**AI 멀티 에이전트 기반 자기소개서 생성 파이프라인**입니다.

이 프로젝트는 단순 문장 생성기가 아니라,  
사용자 경험 데이터를 구조화하고, 기업 최신 정보를 리서치한 뒤,  
둘 사이의 전략적 연결고리를 찾아 자소서 초안을 만드는 것을 목표로 합니다.

---

## 프로젝트 한 줄 요약

> "이력서 PDF 1회 등록 + 채용공고 URL 입력"만으로  
> 기업 맞춤형 자소서 초안(지원동기/성장과정/성격의 장단점/입사 후 포부)을 자동 생성

---

## 문제 정의

취업 준비생은 다음과 같은 반복 고통을 겪습니다.

- 여러 기업에 지원할수록 동일한 경험을 매번 다른 문장으로 재가공해야 함
- 기업별 최신 이슈를 조사하고, 어떤 경험을 강조할지 판단하는 데 시간이 과다 소모됨
- 한 회사 지원서 작성에 3~5시간 이상이 소요되는 비효율 발생

---

## 해결 방식

CoverFit은 아래 3가지 방식으로 문제를 해결합니다.

### 1) 데이터 기반 경험 자산화

- 이력서의 경험을 구조화(JSON)하고 STAR 기반 맥락으로 정리
- 이후 공고가 바뀌어도 재활용 가능한 개인 역량 데이터셋으로 축적

### 2) 실시간 외부 데이터 리서치

- 공고문 텍스트만 보는 것이 아니라 기업 관련 웹 정보를 추가 수집
- 최신 뉴스, 기술 맥락, 조직 방향성 등 자소서 논리 근거를 보강

### 3) 지능형 전략 매칭(Alignment)

- 사용자 경험 중 공고 요구사항과 가장 맞는 에피소드를 선별
- "내 경험"을 "기업의 언어"로 연결해 설득력 있는 초안을 생성

---

## 멀티 에이전트 아키텍처

현재 파이프라인은 `backend1 -> backend2 -> backend3` 순차 실행 구조입니다.

### Agent 1: Context Parser (`backend1`)

- 입력: 이력서 PDF, 채용공고 URL
- 역할: 프로필/공고 핵심 정보를 구조화 JSON으로 추출
- 출력:
  - `output/user_profile.json`
  - `output/job_posting.json`

### Agent 2: Insight Researcher (`backend2`)

- 입력: `user_profile.json`, `job_posting.json`
- 역할: 기업/직무 리서치 + 인사이트 생성
- 출력:
  - `output/backend2_run_output.json`

### Agent 3: Strategy Writer (`backend3`)

- 입력: `user_profile.json`, `job_posting.json`, `backend2_run_output.json`
- 역할: 전략적 자소서 4문항 초안 작성
- 출력:
  - `output/backend3_essay_output.json`

---

## 생성 결과 (기본 4문항)

`backend3`는 다음 문항을 기본 템플릿으로 생성합니다.

1. 지원동기
2. 성장과정
3. 성격의 장단점
4. 입사 후 포부

---

## 기술적 차별점

- **End-to-End 자동화**: PDF 분석 -> 공고 분석 -> 리서치 -> 문항 생성까지 단일 흐름
- **JSON 중심 설계**: 단계 간 인터페이스를 구조화 데이터로 통일
- **Agentic Workflow**: 리서치 에이전트와 작성 에이전트를 분리해 역할 전문화
- **Fallback 전략**: 외부 API 실패 시에도 최소 결과를 반환하는 안전한 실행 설계

---

## 기술 스택

- Python
- LangChain / LangGraph
- OpenAI API
- Tavily / Serper (웹 검색)
- Streamlit (UI, 선택)

---

## 실행 방법

### 1) 의존성 설치

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2) 환경변수 설정

`.env.example`을 복사해 `.env`를 만들고 API 키를 설정합니다.

```powershell
Copy-Item .env.example .env
```

### 3) 단계별 실행

```powershell
# backend1: 프로필/공고 구조화
python backend1/preprocess_agent.py --pdf "resumes/자소서1.pdf" --url "https://채용공고URL" --output "./output"

# backend2: 기업 리서치 + 인사이트 생성
python backend2/research_agent.py --output "output/backend2_run_output.json"

# backend3: 자소서 4문항 생성
python backend3/essay_agent.py --output "output/backend3_essay_output.json"
```

---

## 기대 효과

- 자소서 초안 작성 시간을 시간 단위에서 분 단위로 단축
- 기업별 맞춤 논리(요구사항-경험 연결)의 일관성 강화
- 반복적인 문서 작성 노동을 줄이고, 전략적 수정/고도화에 집중 가능

---

## 향후 고도화 아이디어

- 문항별 피드백 루프(재작성, 톤 변경, 길이 제약 반영)
- 채용공고 도메인별 프롬프트 최적화
- 정량적 매칭 점수(요구사항-경험 적합도) 시각화
- 최종 제출용 문서 포맷 내보내기
