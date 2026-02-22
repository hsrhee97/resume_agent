# CoverFit

CoverFit은 취업 준비의 병목인 **기업별 맞춤 자소서 작성**을 자동화하는  
**AI 멀티 에이전트 기반 서비스**입니다.

사용자는 이력서와 채용공고만 제공하면,  
AI가 경험을 구조화하고 기업 정보를 리서치한 뒤  
자소서 4개 문항 초안을 생성합니다.

---

## 데모 / 링크

- 서비스 링크: `https://coverfit.streamlit.app/`

---

## 해결하는 문제

- 여러 회사 지원 시 같은 경험을 매번 공고별로 재작성해야 하는 반복 노동
- 회사 최신 이슈/기술 맥락 파악에 드는 과도한 리서치 시간
- 경험은 많지만 어떤 에피소드를 강조해야 하는지 판단하기 어려운 매칭 문제

---

## 핵심 가치

### 1) 경험 자산화
- 이력서 경험을 구조화(JSON)하고 STAR 맥락으로 정리
- 공고가 바뀌어도 재활용 가능한 역량 데이터셋 구축

### 2) 외부 데이터 리서치
- 공고문 텍스트에만 의존하지 않고 기업 관련 정보를 추가 수집
- 최신 비즈니스/기술 맥락을 자소서 근거로 반영

### 3) 전략적 매칭
- 사용자 경험 중 공고 요구와 가장 맞는 에피소드를 선별
- “내 경험”을 “기업의 언어”로 연결해 설득력 강화

---

## 멀티 에이전트 구조

### Agent 1: Context Parser (`backend1`)
- 입력: 이력서 PDF, 채용공고 URL
- 출력: `output/user_profile.json`, `output/job_posting.json`

### Agent 2: Insight Researcher (`backend2`)
- 입력: `user_profile.json`, `job_posting.json`
- 출력: `output/backend2_run_output.json`

### Agent 3: Strategy Writer (`backend3`)
- 입력: `user_profile.json`, `job_posting.json`, `backend2_run_output.json`
- 출력: `output/backend3_essay_output.json`

---

## 생성 문항

- 지원동기
- 성장과정
- 성격의 장단점
- 입사 후 포부

---

## 기술 스택

- Python
- LangChain / LangGraph
- OpenAI API
- Tavily / Serper
- Streamlit
