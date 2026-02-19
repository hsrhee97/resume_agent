# agent.py
"""
자소서 생성 에이전트 (메인 오케스트레이터)
=======================================
하나의 에이전트가 두 작업을 수행:
1. 샘플 자소서 PDF → JSON 스키마 추출
2. 채용공고 URL → 공고 정보 + 회사 리서치 JSON

Usage:
    python agent.py --pdf sample.pdf --url "https://jobkorea.co.kr/..."
    python agent.py --pdf sample.pdf  # PDF만 파싱
    python agent.py --url "https://..."  # URL만 크롤링
"""

import argparse
import json
import os
import sys
from datetime import datetime

# 현재 파일 위치 기준으로 preprocess_agent_app 모듈 경로를 sys.path에 추가
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.join(BASE_DIR, "preprocess_agent_app")
if APP_DIR not in sys.path:
    sys.path.append(APP_DIR)

from config import PROMPTS, USER_PROFILE_SCHEMA, JOB_POSTING_SCHEMA
from llm_client import HuggingFaceLLM, OllamaLLM
from pdf_parser import extract_text_from_pdf, chunk_text
from web_crawler import JobPostingCrawler, CompanyResearcher, format_research_for_llm


class FirstAgent:
    """
    자소서 생성 에이전트

    두 가지 핵심 태스크:
    - Task A: PDF → 사용자 프로필 JSON 추출
    - Task B: URL → 채용공고 + 회사 리서치 JSON 추출

    두 결과를 결합하면 최종 자소서 생성의 입력이 됨.
    """

    def __init__(self, llm_backend: str = "huggingface", hf_token: str = None):
        """
        Args:
            llm_backend: "huggingface" 또는 "ollama"
            hf_token: HuggingFace API 토큰 (huggingface 백엔드 사용 시)
        """
        if llm_backend == "ollama":
            self.llm = OllamaLLM(model="mistral")
            print("🤖 LLM 백엔드: Ollama (로컬)")
        else:
            self.llm = HuggingFaceLLM(api_token=hf_token)
            print(f"🤖 LLM 백엔드: HuggingFace ({self.llm.model_id})")

        self.job_crawler = JobPostingCrawler()
        self.researcher = CompanyResearcher()

    # ============================================================
    # Task A: PDF → 사용자 프로필 JSON
    # ============================================================
    def extract_profile_from_pdf(self, pdf_path: str) -> dict:
        """
        샘플 자소서 PDF에서 사용자 프로필을 JSON 스키마로 추출

        Args:
            pdf_path: 자소서 PDF 경로

        Returns:
            USER_PROFILE_SCHEMA에 맞는 딕셔너리
        """
        print("\n" + "=" * 60)
        print("📄 [Task A] PDF → 프로필 JSON 추출")
        print("=" * 60)

        # Step 1: PDF 텍스트 추출
        print(f"\n1️⃣ PDF 텍스트 추출 중... ({pdf_path})")
        raw_text = extract_text_from_pdf(pdf_path)

        if not raw_text:
            print("  ❌ PDF에서 텍스트를 추출할 수 없습니다.")
            return {}

        print(f"  추출된 텍스트 길이: {len(raw_text)} 글자")

        # Step 2: 텍스트가 길면 청킹
        chunks = chunk_text(raw_text, max_chars=3000)
        print(f"  청크 수: {len(chunks)}개")

        # Step 3: LLM으로 스키마 추출
        print(f"\n2️⃣ LLM으로 프로필 정보 추출 중...")

        if len(chunks) == 1:
            # 한 번에 처리
            profile = self._extract_profile_single(raw_text)
        else:
            # 청크별 추출 후 병합
            profile = self._extract_profile_chunked(chunks)

        # Step 4: 스키마 검증 및 보정
        print(f"\n3️⃣ 스키마 검증 중...")
        profile = self._validate_profile(profile)

        return profile

    def _extract_profile_single(self, text: str) -> dict:
        """단일 텍스트에서 프로필 추출"""
        schema_str = json.dumps(USER_PROFILE_SCHEMA, ensure_ascii=False, indent=2)
        prompt = PROMPTS["extract_profile_from_pdf"].format(
            schema=schema_str, text=text[:4000]
        )
        result = self.llm.generate_json(prompt)
        if result:
            print("  ✅ 프로필 추출 성공")
        else:
            print("  ⚠️ JSON 파싱 실패. raw 텍스트로 기본 구조 생성")
            result = self._build_fallback_profile(text)
        return result

    def _extract_profile_chunked(self, chunks: list[str]) -> dict:
        """여러 청크에서 프로필을 추출하여 병합"""
        merged = {}

        for i, chunk in enumerate(chunks):
            print(f"  청크 {i+1}/{len(chunks)} 처리 중...")
            schema_str = json.dumps(USER_PROFILE_SCHEMA, ensure_ascii=False, indent=2)
            prompt = PROMPTS["extract_profile_from_pdf"].format(
                schema=schema_str, text=chunk
            )
            partial = self.llm.generate_json(prompt)
            if partial:
                merged = self._deep_merge(merged, partial)

        return merged

    def _build_fallback_profile(self, text: str) -> dict:
        """LLM 파싱 실패 시 규칙 기반 기본 프로필 생성"""
        import re

        profile = {"user_profile": {}, "raw_text": text[:5000]}

        # 이메일 추출
        email_match = re.search(r"[\w.-]+@[\w.-]+\.\w+", text)
        if email_match:
            profile["user_profile"]["email"] = email_match.group()

        # 전화번호 추출
        phone_match = re.search(r"01[016789]-?\d{3,4}-?\d{4}", text)
        if phone_match:
            profile["user_profile"]["phone"] = phone_match.group()

        # GitHub 추출
        github_match = re.search(r"github\.com/[\w-]+", text)
        if github_match:
            profile["user_profile"]["github"] = f"https://{github_match.group()}"

        return profile

    def _validate_profile(self, profile: dict) -> dict:
        """추출된 프로필을 스키마에 맞게 검증/보정"""
        # 필수 키 존재 확인
        required_keys = ["user_profile", "tech_stack", "education", "experiences"]
        for key in required_keys:
            if key not in profile:
                profile[key] = {} if key in ("user_profile", "tech_stack") else []
                print(f"  ⚠️ '{key}' 누락 → 빈 값으로 채움")

        # background는 옵셔널 (PDF에 없을 수 있음)
        if "background" not in profile:
            profile["background"] = {
                "core_identity": {},
                "transformation_milestones": [],
                "conflict_resolution": [],
                "future_contribution": {},
            }

        print("  ✅ 스키마 검증 완료")
        return profile

    @staticmethod
    def _deep_merge(base: dict, update: dict) -> dict:
        """두 딕셔너리를 깊이 병합"""
        for key, value in update.items():
            if key in base:
                if isinstance(base[key], dict) and isinstance(value, dict):
                    base[key] = FirstAgent._deep_merge(base[key], value)
                elif isinstance(base[key], list) and isinstance(value, list):
                    # 리스트는 중복 제거 후 확장
                    existing = {json.dumps(item, ensure_ascii=False) if isinstance(item, dict) else str(item) for item in base[key]}
                    for item in value:
                        item_key = json.dumps(item, ensure_ascii=False) if isinstance(item, dict) else str(item)
                        if item_key not in existing:
                            base[key].append(item)
                else:
                    # 빈 값이면 덮어쓰기
                    if not base[key] or base[key] in ("", "미확인", None):
                        base[key] = value
            else:
                base[key] = value
        return base

    # ============================================================
    # Task B: URL → 채용공고 + 회사 리서치 JSON
    # ============================================================
    def extract_job_posting(self, url: str) -> dict:
        """
        채용공고 URL에서 공고 정보 + 회사 리서치를 JSON으로 추출

        Args:
            url: 잡코리아/사람인/원티드 등 채용공고 URL

        Returns:
            JOB_POSTING_SCHEMA에 맞는 딕셔너리
        """
        print("\n" + "=" * 60)
        print("🔗 [Task B] 채용공고 URL → 공고 + 리서치 JSON 추출")
        print("=" * 60)

        # Step 1: 채용공고 크롤링
        print(f"\n1️⃣ 채용공고 크롤링 중...")
        crawl_result = self.job_crawler.crawl(url)

        if not crawl_result.get("raw_text"):
            print("  ❌ 채용공고 텍스트를 가져올 수 없습니다.")
            return {"url": url, "error": "크롤링 실패"}

        # Step 2: LLM으로 공고 정보 구조화
        print(f"\n2️⃣ LLM으로 공고 정보 구조화 중...")
        schema_str = json.dumps(JOB_POSTING_SCHEMA, ensure_ascii=False, indent=2)
        prompt = PROMPTS["extract_job_posting"].format(
            schema=schema_str, text=crawl_result["raw_text"]
        )
        job_info = self.llm.generate_json(prompt)

        if not job_info:
            print("  ⚠️ LLM 파싱 실패. 크롤링 원본 데이터 사용")
            job_info = {
                "company": {"name": crawl_result["parsed"].get("company", "")},
                "position": {"title": crawl_result["parsed"].get("title", "")},
                "raw_sections": crawl_result["parsed"].get("sections", []),
            }

        # Step 3: 회사 리서치 (추가 정보 수집)
        company_name = (
            job_info.get("company", {}).get("name", "")
            or crawl_result["parsed"].get("company", "")
        )
        position = (
            job_info.get("position", {}).get("title", "")
            or crawl_result["parsed"].get("title", "")
        )

        if company_name:
            print(f"\n3️⃣ 회사 리서치 수행 중... ({company_name})")
            research = self.researcher.research(company_name, position)

            # Step 4: 리서치 결과를 LLM으로 정리
            print(f"\n4️⃣ 리서치 결과 정리 중...")
            research_text = format_research_for_llm(research)

            if research_text != "검색 결과 없음":
                research_prompt = PROMPTS["research_company"].format(
                    company_name=company_name,
                    position=position,
                    search_results=research_text[:3000],
                )
                research_json = self.llm.generate_json(research_prompt)

                if research_json:
                    job_info.setdefault("company_research", {}).update(research_json)
                else:
                    job_info["company_research"] = {"raw_data": research_text[:2000]}
        else:
            print("  ⚠️ 회사명 추출 실패. 리서치 건너뜀.")

        # 메타데이터 추가
        job_info["_meta"] = {
            "source_url": url,
            "crawled_at": datetime.now().isoformat(),
            "site": crawl_result["site"],
        }

        return job_info

    # ============================================================
    # 통합 실행
    # ============================================================
    def run(self, pdf_path: str = None, url: str = None, output_dir: str = "./output") -> dict:
        """
        에이전트 실행 (PDF, URL 중 하나 또는 둘 다)

        Args:
            pdf_path: 샘플 자소서 PDF 경로
            url: 채용공고 URL
            output_dir: 결과 JSON 저장 디렉토리

        Returns:
            { "profile": {...}, "job_posting": {...} }
        """
        os.makedirs(output_dir, exist_ok=True)
        results = {}

        # Task A: PDF 프로필 추출
        if pdf_path:
            profile = self.extract_profile_from_pdf(pdf_path)
            results["profile"] = profile

            output_path = os.path.join(output_dir, "user_profile.json")
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(profile, f, ensure_ascii=False, indent=2)
            print(f"\n💾 프로필 저장: {output_path}")

        # Task B: 채용공고 + 리서치
        if url:
            job_posting = self.extract_job_posting(url)
            results["job_posting"] = job_posting

            output_path = os.path.join(output_dir, "job_posting.json")
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(job_posting, f, ensure_ascii=False, indent=2)
            print(f"\n💾 채용공고 저장: {output_path}")

        # 요약 출력
        self._print_summary(results)

        return results

    def _print_summary(self, results: dict):
        """실행 결과 요약 출력"""
        print("\n" + "=" * 60)
        print("📊 실행 결과 요약")
        print("=" * 60)

        if "profile" in results:
            p = results["profile"]
            name = p.get("user_profile", {}).get("name", "미확인")
            exp_count = len(p.get("experiences", []))
            edu_count = len(p.get("education", []))
            print(f"\n  [프로필]")
            print(f"  - 이름: {name}")
            print(f"  - 경험: {exp_count}건")
            print(f"  - 학력: {edu_count}건")

        if "job_posting" in results:
            j = results["job_posting"]
            company = j.get("company", {}).get("name", "미확인")
            position = j.get("position", {}).get("title", "미확인")
            q_count = len(j.get("essay_questions", []))
            print(f"\n  [채용공고]")
            print(f"  - 회사: {company}")
            print(f"  - 직무: {position}")
            print(f"  - 자소서 문항: {q_count}개")

            if j.get("company_research"):
                print(f"  - 회사 리서치: ✅ 완료")

        print("\n" + "=" * 60)


# ============================================================
# 기존 JSON 스키마가 있는 경우 (PDF 파싱 스킵)
# ============================================================
def load_existing_profile(json_path: str) -> dict:
    """
    이미 작성된 user_profile.json을 로드
    (PDF 파싱 없이 기존 데이터 사용할 때)
    """
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


# ============================================================
# CLI 엔트리포인트
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description="자소서 생성 에이전트: PDF/URL → JSON 추출"
    )
    parser.add_argument("--pdf", type=str, help="샘플 자소서 PDF 경로")
    parser.add_argument("--url", type=str, help="채용공고 URL")
    parser.add_argument("--output", type=str, default="./output", help="출력 디렉토리")
    parser.add_argument(
        "--backend",
        type=str,
        choices=["huggingface", "ollama"],
        default="huggingface",
        help="LLM 백엔드 선택",
    )
    parser.add_argument("--hf-token", type=str, help="HuggingFace API 토큰")
    parser.add_argument(
        "--existing-profile",
        type=str,
        help="기존 user_profile.json 경로 (PDF 파싱 대신 사용)",
    )

    args = parser.parse_args()

    if not args.pdf and not args.url:
        parser.print_help()
        print("\n⚠️ --pdf 또는 --url 중 하나는 지정해야 합니다.")
        sys.exit(1)

    # 에이전트 초기화
    agent = FirstAgent(
        llm_backend=args.backend,
        hf_token=args.hf_token,
    )

    # 기존 프로필 사용 모드
    if args.existing_profile:
        print(f"\n📂 기존 프로필 로드: {args.existing_profile}")
        profile = load_existing_profile(args.existing_profile)
        results = {"profile": profile}

        if args.url:
            job_posting = agent.extract_job_posting(args.url)
            results["job_posting"] = job_posting

            output_path = os.path.join(args.output, "job_posting.json")
            os.makedirs(args.output, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(job_posting, f, ensure_ascii=False, indent=2)

        agent._print_summary(results)
    else:
        # 일반 실행
        agent.run(pdf_path=args.pdf, url=args.url, output_dir=args.output)


if __name__ == "__main__":
    main()