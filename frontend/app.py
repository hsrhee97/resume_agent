from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

# Streamlit Cloud can execute this file with cwd set to `frontend/`.
# Ensure repository root is always importable for `frontend.*` and `backend*` modules.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from frontend.pipeline import (
    get_hf_token,
    is_job_posting_usable,
    persist_uploaded_pdf,
    run_company_research,
    run_essay_writer,
    run_schema_extraction,
)

load_dotenv()

SECTION_LABELS = ("지원동기", "성장과정", "성격의 장단점", "입사 후 포부")
SECTION_ALIASES: dict[str, tuple[str, ...]] = {
    "지원동기": ("지원동기", "지원 동기", "동기", "motivation"),
    "성장과정": ("성장과정", "성장 과정", "growth"),
    "성격의 장단점": ("성격의 장단점", "장단점", "personality"),
    "입사 후 포부": ("입사 후 포부", "포부", "after joining"),
}


def _inject_styles() -> None:
    st.markdown(
        """
<style>
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=Noto+Sans+KR:wght@400;500;700;900&display=swap');

:root {
  --cf-bg: #0f172a;
  --cf-surface: #1e293b;
  --cf-surface-2: #27364b;
  --cf-upload-bg: #152237;
  --cf-border: #334155;
  --cf-border-soft: #3d4f67;
  --cf-text: #ffffff;
  --cf-muted: #94a3b8;
  --cf-accent: #38bdf8;
  --cf-accent-2: #0ea5e9;
  --cf-accent-soft: rgba(56, 189, 248, 0.16);
  --cf-radius-xl: 22px;
  --cf-radius-lg: 16px;
  --cf-radius-md: 12px;
  --cf-space-1: 0.5rem;
  --cf-space-2: 0.9rem;
  --cf-space-3: 1.2rem;
  --cf-space-4: 1.8rem;
}

.stApp {
  background:
    radial-gradient(circle at 12% 8%, rgba(56, 189, 248, 0.12) 0, rgba(56, 189, 248, 0) 30%),
    radial-gradient(circle at 90% 10%, rgba(14, 165, 233, 0.12) 0, rgba(14, 165, 233, 0) 28%),
    var(--cf-bg);
  color: var(--cf-text);
}

[data-testid="stAppViewContainer"] > .main .block-container,
section.main > div.block-container,
div[data-testid="stMainBlockContainer"] {
  width: 60% !important;
  max-width: 60% !important;
  margin-left: auto !important;
  margin-right: auto !important;
  padding-top: 1.4rem !important;
  padding-bottom: 2.6rem !important;
}

html, body, [class*="css"] {
  font-family: "Manrope", "Noto Sans KR", sans-serif;
}

h1, h2, h3, h4, p, span, label {
  color: var(--cf-text);
}

[data-testid="stCaptionContainer"] p {
  color: var(--cf-muted) !important;
}

header[data-testid="stHeader"] {
  border-bottom: 1px solid var(--cf-border);
  backdrop-filter: blur(8px);
  background: rgba(15, 23, 42, 0.88);
}

div[data-testid="stToolbar"] {
  min-height: 3.7rem;
}

div[data-testid="stToolbar"] > div {
  width: 100%;
}

div[data-testid="stToolbar"] > div > div:first-child {
  flex: 1 1 auto;
  display: flex;
  align-items: center;
  justify-content: center;
}

div[data-testid="stToolbar"] > div > div:nth-child(2) {
  display: none !important;
}

div[data-testid="stToolbarActions"] {
  display: none !important;
}

div[data-testid="stAppDeployButton"] {
  display: none !important;
}

span[data-testid="stMainMenu"] {
  display: none !important;
}

.cf-toolbar-brand {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto;
}

.cf-toolbar-logo {
  text-decoration: none;
  color: var(--cf-text);
  font-weight: 800;
  letter-spacing: 0.02em;
  font-size: 1rem;
}

.cf-toolbar-logo:hover {
  color: var(--cf-accent);
}

.cf-card {
  border-radius: var(--cf-radius-lg);
  border: 1px solid var(--cf-border);
  background: var(--cf-surface);
  padding: var(--cf-space-4);
}

.cf-hero {
  margin-top: var(--cf-space-3);
  border-radius: var(--cf-radius-xl);
  background: linear-gradient(132deg, #172236 0%, #1f2f46 55%, #243a55 100%);
  box-shadow: 0 24px 44px rgba(2, 8, 20, 0.35);
}

.cf-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.28rem 0.72rem;
  border-radius: 999px;
  border: 1px solid rgba(56, 189, 248, 0.45);
  background: rgba(56, 189, 248, 0.14);
  color: #cceeff;
  font-size: 0.74rem;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.cf-hero h1 {
  margin: 0.95rem 0 0;
  font-size: 2.1rem;
  line-height: 1.15;
}

.cf-hero p {
  margin: 0.9rem 0 0;
  color: #d6e4f3;
  line-height: 1.75;
}

.cf-flow-card {
  margin-top: var(--cf-space-4);
}

.cf-flow-card h3 {
  margin: 0 0 var(--cf-space-3);
  font-size: 1.05rem;
}

.cf-step-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--cf-space-2);
}

.cf-step {
  border-radius: var(--cf-radius-md);
  border: 1px solid var(--cf-border);
  background: var(--cf-surface-2);
  padding: var(--cf-space-3);
  min-height: 128px;
}

.cf-step strong {
  color: #d5f1ff;
  font-size: 0.95rem;
}

.cf-step p {
  margin: 0.45rem 0 0;
  color: var(--cf-muted);
  line-height: 1.56;
  font-size: 0.9rem;
}

.cf-note {
  margin-top: var(--cf-space-3);
  border-radius: var(--cf-radius-md);
  border: 1px solid rgba(56, 189, 248, 0.32);
  background: rgba(56, 189, 248, 0.1);
  color: #d9f4ff;
  padding: 0.8rem 0.92rem;
  font-size: 0.91rem;
}

.cf-landing-cta {
  height: var(--cf-space-4);
}

div[data-testid="stButton"] > button {
  border-radius: 999px;
  min-height: 2.9rem;
  border: 1px solid transparent;
  background: linear-gradient(135deg, var(--cf-accent) 0%, var(--cf-accent-2) 100%);
  color: #002335;
  font-weight: 800;
  box-shadow: 0 12px 24px rgba(14, 165, 233, 0.28);
}

div[data-testid="stButton"] > button:hover {
  filter: brightness(1.04);
}

.cf-form-header {
  margin-top: 0.45rem;
  margin-bottom: var(--cf-space-3);
}

.cf-form-header h2 {
  margin: 0;
  font-size: 1.5rem;
}

.cf-form-header p {
  margin: 0.65rem 0 0;
  color: var(--cf-muted);
  line-height: 1.62;
}

.cf-back-link {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  margin-bottom: 0.85rem;
  text-decoration: none;
  color: var(--cf-muted);
  font-size: 0.92rem;
  font-weight: 700;
}

.cf-back-link:hover {
  color: var(--cf-accent);
}

div[data-testid="stForm"] {
  border-radius: var(--cf-radius-lg);
  border: 1px solid var(--cf-border);
  background: var(--cf-surface);
  padding: var(--cf-space-3) var(--cf-space-3) var(--cf-space-1);
  box-shadow: 0 20px 34px rgba(2, 8, 20, 0.34);
}

div[data-testid="stForm"] label p {
  color: #f0f6ff !important;
  font-weight: 700 !important;
}

div[data-testid="stForm"] [data-testid="stTextInput"] input,
div[data-testid="stForm"] [data-testid="stTextArea"] textarea {
  border-radius: 14px !important;
  border: 1px solid var(--cf-border) !important;
  background: #162235 !important;
  color: #ffffff !important;
}

div[data-testid="stForm"] [data-testid="stTextInput"] input::placeholder,
div[data-testid="stForm"] [data-testid="stTextArea"] textarea::placeholder {
  color: var(--cf-muted) !important;
}

div[data-testid="stForm"] [data-testid="stTextInput"] input:focus,
div[data-testid="stForm"] [data-testid="stTextArea"] textarea:focus {
  border-color: var(--cf-accent) !important;
  box-shadow: 0 0 0 1px var(--cf-accent);
}

div[data-testid="stForm"] [data-testid="stFileUploader"] section,
div[data-testid="stForm"] [data-testid="stFileUploaderDropzone"] {
  border-radius: 14px !important;
  border: 1px dashed var(--cf-border-soft) !important;
  background: var(--cf-upload-bg) !important;
  padding: 1rem 1rem !important;
  display: flex !important;
  align-items: center !important;
  gap: 0.85rem !important;
}

div[data-testid="stForm"] [data-testid="stFileUploaderDropzoneInstructions"] {
  flex: 1 1 auto !important;
}

div[data-testid="stForm"] [data-testid="stFileUploaderDropzoneInstructions"] div:first-child {
  visibility: hidden;
  position: relative;
  min-height: 1.35rem;
}

div[data-testid="stForm"] [data-testid="stFileUploaderDropzoneInstructions"] div:first-child::after {
  content: "파일을 드래그하거나 여기에 놓아 주세요";
  visibility: visible;
  position: absolute;
  inset: 0;
  color: #d8eaff;
  font-weight: 600;
  text-align: left;
  padding-left: 1.72rem;
}

div[data-testid="stForm"] [data-testid="stFileUploaderDropzoneInstructions"] div:first-child::before {
  content: "";
  position: absolute;
  left: 0.2rem;
  top: 0.1rem;
  width: 0.9rem;
  height: 1.05rem;
  border: 1.5px solid var(--cf-accent);
  border-radius: 2px;
  visibility: visible;
}

div[data-testid="stForm"] [data-testid="stFileUploaderDropzoneInstructions"] div:nth-child(2) {
  visibility: hidden;
  position: relative;
}

div[data-testid="stForm"] [data-testid="stFileUploaderDropzoneInstructions"] div:nth-child(2)::after {
  content: "최대 200MB • PDF";
  visibility: visible;
  position: absolute;
  inset: 0;
  color: var(--cf-muted);
  text-align: left;
}

div[data-testid="stForm"] [data-testid="stFileUploader"] button {
  margin-left: auto !important;
  border-radius: 999px !important;
  border: 1px solid rgba(56, 189, 248, 0.5) !important;
  background: #1d3044 !important;
  color: #ffffff !important;
  font-weight: 700 !important;
}

div[data-testid="stFormSubmitButton"] > button {
  width: 100%;
  min-height: 3.15rem;
  border-radius: 999px;
  border: 1px solid transparent !important;
  background: linear-gradient(135deg, var(--cf-accent) 0%, var(--cf-accent-2) 100%) !important;
  color: #002335 !important;
  font-size: 1rem !important;
  font-weight: 900 !important;
  box-shadow: 0 14px 28px rgba(14, 165, 233, 0.32);
}

div[data-testid="stFormSubmitButton"] > button:hover {
  transform: translateY(-1px);
  filter: brightness(1.05);
}

div[data-testid="stAlert"] {
  border-radius: var(--cf-radius-md);
  border: 1px solid rgba(56, 189, 248, 0.4);
  background: rgba(56, 189, 248, 0.1);
}

.cf-results-title {
  margin-top: var(--cf-space-4);
  margin-bottom: 0.7rem;
}

.cf-results-divider {
  height: 1px;
  margin: 0 0 var(--cf-space-3);
  background: linear-gradient(
    90deg,
    rgba(56, 189, 248, 0.08) 0%,
    rgba(148, 163, 184, 0.45) 22%,
    rgba(148, 163, 184, 0.45) 78%,
    rgba(56, 189, 248, 0.08) 100%
  );
}

div[data-testid="stDownloadButton"] > button {
  border-radius: 12px;
  border: 1px solid var(--cf-border) !important;
  background: #1a2a3d !important;
  color: #ffffff !important;
  font-weight: 700 !important;
}

div[data-testid="stDownloadButton"] > button:hover {
  border-color: var(--cf-accent) !important;
}

@media (max-width: 1100px) {
  [data-testid="stAppViewContainer"] > .main .block-container,
  section.main > div.block-container,
  div[data-testid="stMainBlockContainer"] {
    width: 80% !important;
    max-width: 80% !important;
  }
}

@media (max-width: 900px) {
  [data-testid="stAppViewContainer"] > .main .block-container,
  section.main > div.block-container,
  div[data-testid="stMainBlockContainer"] {
    width: 94% !important;
    max-width: 94% !important;
  }
  .cf-step-grid {
    grid-template-columns: 1fr;
  }
  .cf-hero h1 {
    font-size: 1.76rem;
  }
}
</style>
""",
        unsafe_allow_html=True,
    )


def _init_state() -> None:
    backend_default = os.getenv("BACKEND1_LLM_BACKEND", "openai").strip().lower()
    if backend_default not in ("openai", "ollama", "huggingface"):
        backend_default = "openai"

    defaults: dict[str, object] = {
        "pipeline_ready": False,
        "need_job_fallback": False,
        "pending_job_url": "",
        "user_profile": {},
        "job_posting": {},
        "research_result": {},
        "essay_result": {},
        "company_info": {"name": "", "team": "", "role": ""},
        "llm_backend": backend_default,
        "research_provider": os.getenv("SEARCH_PROVIDER", "tavily"),
        "backend1_model": os.getenv("BACKEND1_MODEL", os.getenv("OPENAI_MODEL", "gpt-4.1-mini")),
        "writer_model": os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        "temperature": float(os.getenv("BACKEND1_TEMPERATURE", "0.3")),
        "job_url_input": "",
        "fallback_job_text": "",
        "current_view": "landing",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _set_query_view(view: str) -> None:
    try:
        st.query_params["view"] = view
    except Exception:
        pass


def _sync_view_from_query() -> None:
    try:
        raw = st.query_params.get("view", "")
    except Exception:
        raw = ""

    if isinstance(raw, list):
        raw = raw[0] if raw else ""

    view = str(raw).strip().lower()
    if view in ("landing", "form"):
        st.session_state.current_view = view


def _switch_view(view: str) -> None:
    st.session_state.current_view = view
    _set_query_view(view)
    st.rerun()


def _inject_toolbar_nav() -> None:
    components.html(
        """
<script>
(function () {
  const attachToolbarBrand = () => {
    const doc = window.parent.document;
    const toolbar = doc.querySelector('div[data-testid="stToolbar"]');
    if (!toolbar) return false;

    const wrapper = toolbar.querySelector(":scope > div");
    const leftSlot = wrapper && wrapper.firstElementChild ? wrapper.firstElementChild : toolbar;
    if (!leftSlot) return false;

    if (doc.getElementById("cf-toolbar-brand")) return true;

    const brandBox = doc.createElement("div");
    brandBox.id = "cf-toolbar-brand";
    brandBox.className = "cf-toolbar-brand";

    const path = window.parent.location.pathname || "/";
    const landingHref = path + "?view=landing";

    const logo = doc.createElement("a");
    logo.className = "cf-toolbar-logo";
    logo.href = landingHref;
    logo.textContent = "CoverFit";

    brandBox.appendChild(logo);
    leftSlot.appendChild(brandBox);
    return true;
  };

  if (!attachToolbarBrand()) {
    let tries = 0;
    const timer = setInterval(() => {
      tries += 1;
      if (attachToolbarBrand() || tries > 40) {
        clearInterval(timer);
      }
    }, 100);
  }
})();
</script>
""",
        height=0,
        width=0,
    )


def _render_landing() -> None:
    st.markdown(
        """
<section class="cf-card cf-hero">
  <span class="cf-badge">CoverFit Pipeline</span>
  <h1>이력서는 한 번, 자소서는 무한히</h1>
  <p>
    이력서 PDF와 채용공고 URL을 기반으로 기업 맞춤형 자기소개서를 생성합니다.
    공고 분석부터 기업 리서치, 문항별 작성까지 한 번에 연결해 반복 작업을 줄여줍니다.
  </p>
</section>
""",
        unsafe_allow_html=True,
    )

    st.markdown(
        """
<section class="cf-card cf-flow-card">
  <h3>생성 프로세스</h3>
  <div class="cf-step-grid">
    <div class="cf-step">
      <strong>Step 1. 이력서 스키마 정리</strong>
      <p>PDF에서 경험과 성과를 추출해 자소서 생성에 맞는 구조화 데이터로 변환합니다.</p>
    </div>
    <div class="cf-step">
      <strong>Step 2. 공고 요구사항 추출</strong>
      <p>채용공고 URL에서 핵심 요구역량을 추출하고, 부족하면 보조 입력으로 보완합니다.</p>
    </div>
    <div class="cf-step">
      <strong>Step 3. 맞춤 자소서 생성</strong>
      <p>기업 리서치 결과를 결합해 문항별 완성형 자소서를 생성합니다.</p>
    </div>
  </div>
  <div class="cf-note">URL만 바꿔 여러 회사에 맞춘 자소서를 빠르게 만들 수 있습니다.</div>
</section>
""",
        unsafe_allow_html=True,
    )

    st.markdown("<div class='cf-landing-cta'></div>", unsafe_allow_html=True)
    left, center, right = st.columns([1, 2, 1])
    with center:
        if st.button("자소서 작성하기", use_container_width=True, type="primary"):
            _switch_view("form")


def _submit_pipeline(
    uploaded_pdf: Any,
    job_url: str,
    fallback_text: str,
    fallback_images: list[Any],
) -> None:
    if uploaded_pdf is None:
        st.error("이력서 PDF를 먼저 업로드해 주세요.")
        return

    effective_job_url = (job_url or "").strip() or st.session_state.pending_job_url
    if not effective_job_url:
        st.error("채용공고 URL을 입력해 주세요.")
        return

    if st.session_state.need_job_fallback and not (fallback_text.strip() or fallback_images):
        st.error("URL 추출이 실패했습니다. 공고 텍스트 또는 공고 캡처 이미지를 입력해 주세요.")
        return

    with st.status("파이프라인 실행 중", expanded=True) as status:
        progress = st.progress(0)
        current_task = st.empty()

        def update_task(percent: int, title: str, detail: str = "") -> None:
            progress.progress(max(0, min(100, percent)))
            current_task.markdown(f"**{title}**" + (f"\n\n{detail}" if detail else ""))
            status.write(f"{percent}% · {title}" + (f" - {detail}" if detail else ""))

        try:
            update_task(10, "입력값 확인", "이력서 파일과 채용공고 URL을 검증합니다.")

            update_task(30, "1단계: 이력서/공고 스키마 추출", "PDF와 공고를 분석해 표준 JSON으로 변환합니다.")
            pdf_path = persist_uploaded_pdf(uploaded_pdf, output_dir=Path("output"))
            user_profile, job_posting = run_schema_extraction(
                pdf_path=str(pdf_path),
                job_url=effective_job_url,
                llm_backend=st.session_state.llm_backend,
                hf_token=get_hf_token(),
                model_name=st.session_state.backend1_model,
                temperature=float(st.session_state.temperature),
                job_text_fallback=fallback_text if st.session_state.need_job_fallback else "",
                job_images=fallback_images if st.session_state.need_job_fallback else [],
                output_dir=Path("output"),
            )

            if not is_job_posting_usable(job_posting):
                st.session_state.user_profile = user_profile
                st.session_state.need_job_fallback = True
                st.session_state.pending_job_url = effective_job_url
                update_task(45, "추가 입력 필요", "URL에서 요구사항 추출이 부족해 보완 정보가 필요합니다.")
                status.update(label="추가 공고 정보가 필요합니다", state="error")
                st.warning(
                    "채용공고 본문에서 요구사항 추출이 충분하지 않았습니다. "
                    "아래에 공고 텍스트를 붙여 넣거나 공고 캡처 이미지를 올린 뒤 다시 제출해 주세요."
                )
                return

            meta = job_posting.get("_meta", {}) if isinstance(job_posting, dict) else {}
            if isinstance(meta, dict) and meta.get("manual_fallback_used"):
                status.write("URL 추출이 부족해 수동 입력 텍스트/이미지 fallback을 사용했습니다.")

            update_task(65, "2단계: 기업 리서치", "회사/직무 관련 최신 정보와 맥락을 수집합니다.")
            research_result, company, team, role = run_company_research(
                user_profile=user_profile,
                job_posting=job_posting,
                provider=st.session_state.research_provider,
                model=st.session_state.writer_model,
                output_dir=Path("output"),
            )

            update_task(85, "3단계: 자소서 생성", "리서치 결과를 반영해 문항별 완성본을 작성합니다.")
            essay_result = run_essay_writer(
                user_profile=user_profile,
                job_posting=job_posting,
                research_result=research_result,
                company_name=company,
                team_name=team,
                role_name=role,
                model=st.session_state.writer_model,
                temperature=float(st.session_state.temperature),
                output_dir=Path("output"),
            )

            st.session_state.user_profile = user_profile
            st.session_state.job_posting = job_posting
            st.session_state.research_result = research_result
            st.session_state.essay_result = essay_result
            st.session_state.company_info = {"name": company, "team": team, "role": role}
            st.session_state.pipeline_ready = True
            st.session_state.need_job_fallback = False
            st.session_state.pending_job_url = ""
            st.session_state.fallback_job_text = ""

            update_task(100, "완료", "생성 결과를 화면에 표시합니다.")
            status.update(label="완료", state="complete")
            st.success("맞춤 자소서 생성이 완료되었습니다.")
        except Exception as exc:
            status.update(label="실패", state="error")
            st.error(f"실행 중 오류가 발생했습니다: {type(exc).__name__}: {exc}")


def _render_form() -> None:
    if st.session_state.need_job_fallback:
        st.warning(
            "URL에서 채용공고 핵심 요구사항 추출이 충분하지 않았습니다. "
            "이번에는 공고 텍스트 또는 공고 캡처 이미지를 함께 입력해 주세요."
        )
        if st.session_state.pending_job_url:
            st.caption(f"재시도 URL: {st.session_state.pending_job_url}")

    with st.form("coverfit_submit_form"):
        uploaded_pdf = st.file_uploader("이력서 PDF 업로드", type=["pdf"], key="resume_pdf_uploader")
        job_url = st.text_input(
            "채용공고 URL 입력",
            key="job_url_input",
            placeholder="https://www.wanted.co.kr/wd/123456",
        )

        fallback_text = ""
        fallback_images: list[Any] = []
        if st.session_state.need_job_fallback:
            fallback_text = st.text_area(
                "URL 추출 실패 시 사용할 채용공고 텍스트 (선택)",
                height=180,
                key="fallback_job_text",
                placeholder="공고 본문을 붙여 넣으면 URL 추출 실패 시 fallback으로 사용됩니다.",
            )
            fallback_images = st.file_uploader(
                "URL 추출 실패 시 사용할 채용공고 캡처 이미지 (선택, 여러 장 가능)",
                type=["png", "jpg", "jpeg", "webp", "bmp"],
                accept_multiple_files=True,
                key="fallback_job_images",
            )

        submit_label = "맞춤 자소서 생성하기"
        if st.session_state.need_job_fallback:
            submit_label = "추가 자료로 다시 생성하기"
        submitted = st.form_submit_button(submit_label, use_container_width=True)

    if submitted:
        _submit_pipeline(
            uploaded_pdf=uploaded_pdf,
            job_url=job_url,
            fallback_text=fallback_text,
            fallback_images=fallback_images or [],
        )


def _pick_section_text(essay_templates: dict[str, Any], label: str, index: int) -> str:
    if not isinstance(essay_templates, dict):
        return ""

    direct = essay_templates.get(label, "")
    if isinstance(direct, str) and direct.strip():
        return direct

    aliases = SECTION_ALIASES.get(label, ())
    items = list(essay_templates.items())
    for key, value in items:
        key_text = str(key)
        value_text = str(value) if value is not None else ""
        for alias in aliases:
            if alias and alias in key_text and value_text.strip():
                return value_text

    if 0 <= index < len(items):
        fallback_value = items[index][1]
        return str(fallback_value) if fallback_value is not None else ""
    return ""


def _normalize_reference_urls(raw_urls: Any) -> list[str]:
    if not isinstance(raw_urls, list):
        return []

    cleaned: list[str] = []
    seen: set[str] = set()
    for item in raw_urls:
        url = str(item or "").strip()
        if not url or not url.startswith(("http://", "https://")):
            continue
        if url in seen:
            continue
        seen.add(url)
        cleaned.append(url)
    return cleaned


def _load_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    try:
        raw = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raw = path.read_text(encoding="utf-8-sig")
    except Exception:
        return {}

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}

    return parsed if isinstance(parsed, dict) else {}


def _load_sample_outputs() -> tuple[bool, str]:
    output_dir = Path("output")
    user_profile = _load_json_object(output_dir / "user_profile.json")
    job_posting = _load_json_object(output_dir / "job_posting.json")
    research_result = _load_json_object(output_dir / "backend2_run_output.json")
    essay_result = _load_json_object(output_dir / "backend3_essay_output.json")

    if not essay_result:
        return False, "output/backend3_essay_output.json file is missing or invalid."

    essay_templates = essay_result.get("essay_templates", {})
    if not isinstance(essay_templates, dict) or not essay_templates:
        return False, "Sample file exists, but 'essay_templates' is empty."

    company_name = ""
    team_name = ""
    role_name = ""

    company_info = research_result.get("company_info", {}) if isinstance(research_result, dict) else {}
    if isinstance(company_info, dict):
        company_name = str(company_info.get("name") or "").strip()
        team_name = str(company_info.get("team") or "").strip()
        role_name = str(company_info.get("role") or "").strip()

    if not company_name and isinstance(job_posting.get("company"), dict):
        company_name = str(job_posting["company"].get("name") or "").strip()
    if not team_name and isinstance(job_posting.get("position"), dict):
        team_name = str(job_posting["position"].get("department") or "").strip()
    if not role_name and isinstance(job_posting.get("position"), dict):
        role_name = str(job_posting["position"].get("title") or "").strip()

    st.session_state.user_profile = user_profile
    st.session_state.job_posting = job_posting
    st.session_state.research_result = research_result
    st.session_state.essay_result = essay_result
    st.session_state.company_info = {"name": company_name, "team": team_name, "role": role_name}
    st.session_state.pipeline_ready = True
    st.session_state.need_job_fallback = False
    st.session_state.pending_job_url = ""
    st.session_state.fallback_job_text = ""

    return True, "Sample outputs loaded from output/*.json."


def _render_results() -> None:
    if not st.session_state.pipeline_ready:
        return

    essay_result = st.session_state.essay_result if isinstance(st.session_state.essay_result, dict) else {}
    essay_templates = essay_result.get("essay_templates", {}) if isinstance(essay_result, dict) else {}
    if not isinstance(essay_templates, dict) or not essay_templates:
        return

    st.markdown("<h3 class='cf-results-title'>생성 결과</h3>", unsafe_allow_html=True)
    st.markdown("<div class='cf-results-divider'></div>", unsafe_allow_html=True)

    section_outputs: dict[str, str] = {}
    for idx, section in enumerate(SECTION_LABELS):
        text = _pick_section_text(essay_templates, section, idx)
        section_outputs[section] = text
        st.markdown(f"### {section}")
        st.write(text if text.strip() else f"{section} 결과를 찾지 못했습니다.")
        if idx < len(SECTION_LABELS) - 1:
            st.markdown("---")

    research_result = st.session_state.research_result if isinstance(st.session_state.research_result, dict) else {}
    reference_urls = _normalize_reference_urls(research_result.get("reference_urls", []))
    diagnostics = research_result.get("diagnostics", {}) if isinstance(research_result, dict) else {}
    warnings = diagnostics.get("warnings", []) if isinstance(diagnostics, dict) else []
    errors = diagnostics.get("errors", []) if isinstance(diagnostics, dict) else []

    if reference_urls:
        st.markdown("### 근거 자료")
        st.caption("아래 링크는 기업/직무 리서치에 실제로 사용된 출처입니다.")
        max_links = 12
        for idx, url in enumerate(reference_urls[:max_links], start=1):
            st.markdown(f"{idx}. [{url}]({url})")
        if len(reference_urls) > max_links:
            st.caption(f"...외 {len(reference_urls) - max_links}개 출처가 추가로 사용되었습니다.")

    if isinstance(warnings, list) and any(str(w).strip() for w in warnings):
        st.markdown("### 리서치 경고")
        for warning in warnings[:5]:
            message = str(warning).strip()
            if message:
                st.warning(message)

    if isinstance(errors, list) and any(str(e).strip() for e in errors):
        st.markdown("### 리서치 오류")
        for error in errors[:5]:
            message = str(error).strip()
            if message:
                st.error(message)

    plain_text = "\n\n".join(f"[{section}]\n{section_outputs.get(section, '')}" for section in SECTION_LABELS)
    json_text = json.dumps(essay_result, ensure_ascii=False, indent=2)
    d1, d2 = st.columns(2)
    with d1:
        st.download_button(
            label="자소서 텍스트 다운로드",
            data=plain_text,
            file_name="coverfit_essay.txt",
            mime="text/plain",
            use_container_width=True,
        )
    with d2:
        st.download_button(
            label="전체 JSON 다운로드",
            data=json_text,
            file_name="coverfit_output.json",
            mime="application/json",
            use_container_width=True,
        )

def _render_form_page() -> None:
    st.markdown(
        """
<section class="cf-card cf-form-header">
  <a class="cf-back-link" href="?view=landing">← 홈으로</a>
  <h2>AI 맞춤 자소서 생성</h2>
  <p>이력서 분석 → 공고 추출 → 기업 리서치 → 자소서 생성 순으로 진행됩니다. 아래 자료를 제출해 주세요.</p>
</section>
""",
        unsafe_allow_html=True,
    )

    sample_col_text, sample_col_btn = st.columns([2.4, 1.0])
    with sample_col_text:
        st.caption("UI preview mode: load existing output JSON without uploading PDF/URL.")
    with sample_col_btn:
        if st.button("샘플 결과 보기", use_container_width=True, key="load_sample_outputs_btn"):
            ok, message = _load_sample_outputs()
            if ok:
                st.success(message)
            else:
                st.warning(message)

    _render_form()
    _render_results()


def main() -> None:
    st.set_page_config(page_title="CoverFit", layout="wide")
    _init_state()
    _sync_view_from_query()
    _inject_styles()
    _inject_toolbar_nav()

    if st.session_state.current_view == "form":
        _render_form_page()
        return
    _render_landing()


if __name__ == "__main__":
    main()
