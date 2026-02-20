from __future__ import annotations

import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from frontend.pipeline import (
    get_hf_token,
    persist_uploaded_pdf,
    run_company_research,
    run_essay_writer,
    run_schema_extraction,
)

load_dotenv()

SECTION_KEYS = ("지원동기", "성장과정", "성격의 장단점", "입사 후 포부")


def _format_essay_markdown(essay_templates: dict[str, str]) -> str:
    blocks: list[str] = []
    for section in SECTION_KEYS:
        blocks.append(f"### {section}\n{essay_templates.get(section, '')}")
    return "\n\n".join(blocks)


def _build_revision_instruction(user_request: str) -> str:
    cleaned = (user_request or "").strip()
    if not cleaned:
        return ""
    targets = [section for section in SECTION_KEYS if section in cleaned]
    if not targets:
        return cleaned
    joined = ", ".join(targets)
    return (
        f"사용자 후속 요청: {cleaned}. "
        f"특히 {joined} 문항을 우선 강화하고, 나머지 문항은 톤과 사실 근거를 유지하라."
    )


def _append_message(role: str, content: str) -> None:
    st.session_state.messages.append({"role": role, "content": content})


def _render_messages() -> None:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])


def _init_session_state() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": (
                    "기존 자소서 PDF와 채용공고 URL을 입력해 주세요. "
                    "입력이 끝나면 채팅창에 `시작` 또는 원하는 요청을 입력하면 진행합니다."
                ),
            }
        ]
    if "pipeline_ready" not in st.session_state:
        st.session_state.pipeline_ready = False
    if "user_profile" not in st.session_state:
        st.session_state.user_profile = {}
    if "job_posting" not in st.session_state:
        st.session_state.job_posting = {}
    if "research_result" not in st.session_state:
        st.session_state.research_result = {}
    if "essay_result" not in st.session_state:
        st.session_state.essay_result = {}
    if "company_info" not in st.session_state:
        st.session_state.company_info = {"name": "", "team": "", "role": ""}


def main() -> None:
    st.set_page_config(page_title="자소서 멀티에이전트 챗봇", layout="wide")
    st.title("자소서 멀티에이전트 챗봇")
    st.caption("PDF/채용공고 입력 -> 스키마 정리 -> 기업 조사 -> 자소서 완성본 생성")

    _init_session_state()

    with st.sidebar:
        st.subheader("실행 옵션")
        llm_backend = st.selectbox("기존 자소서/공고 정리 모델", ("openai", "ollama", "huggingface"))
        research_provider = st.selectbox("회사 조사 검색 공급자", ("tavily", "serper"))
        if llm_backend == "ollama":
            backend1_default_model = os.getenv("BACKEND1_MODEL", os.getenv("OLLAMA_MODEL", "qwen2.5"))
        elif llm_backend == "openai":
            backend1_default_model = os.getenv("BACKEND1_MODEL", os.getenv("OPENAI_MODEL", "gpt-4.1-mini"))
        else:
            backend1_default_model = os.getenv("BACKEND1_MODEL", os.getenv("HF_MODEL", ""))
        backend1_model_name = st.text_input("기존 자소서/공고 정리 모델명", value=backend1_default_model)
        writer_model_name = st.text_input("회사 조사/자소서 작성 모델", value=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"))
        temperature = st.slider("작성 온도", min_value=0.0, max_value=1.0, value=0.3, step=0.1)

    uploaded_pdf = st.file_uploader("기존 자소서 PDF 업로드", type=["pdf"])
    job_url = st.text_input("채용공고 URL")

    _render_messages()

    user_prompt = st.chat_input("요청을 입력하세요.")
    if not user_prompt:
        return

    _append_message("user", user_prompt)
    with st.chat_message("user"):
        st.markdown(user_prompt)

    if not st.session_state.pipeline_ready:
        if uploaded_pdf is None or not job_url.strip():
            warning_msg = "PDF 업로드와 채용공고 URL 입력이 필요합니다. 두 항목을 채운 뒤 다시 요청해 주세요."
            _append_message("assistant", warning_msg)
            with st.chat_message("assistant"):
                st.markdown(warning_msg)
            return

        with st.chat_message("assistant"):
            with st.status("자소서 생성 파이프라인 실행 중", expanded=True) as status:
                try:
                    status.write("1/3 기존 자소서와 채용 공고를 우리 스키마에 맞게 정리하는 중")
                    pdf_path = persist_uploaded_pdf(uploaded_pdf, output_dir=Path("output"))
                    user_profile, job_posting = run_schema_extraction(
                        pdf_path=str(pdf_path),
                        job_url=job_url.strip(),
                        llm_backend=llm_backend,
                        hf_token=get_hf_token(),
                        model_name=backend1_model_name,
                        temperature=temperature,
                        output_dir=Path("output"),
                    )

                    status.write("2/3 회사 정보를 조사하고 직무 인사이트를 모으는 중")
                    research_result, company, team, role = run_company_research(
                        user_profile=user_profile,
                        job_posting=job_posting,
                        provider=research_provider,
                        model=writer_model_name,
                        output_dir=Path("output"),
                    )

                    status.write("3/3 수집된 정보를 바탕으로 자기소개서 완성본을 작성하는 중")
                    essay_result = run_essay_writer(
                        user_profile=user_profile,
                        job_posting=job_posting,
                        research_result=research_result,
                        company_name=company,
                        team_name=team,
                        role_name=role,
                        model=writer_model_name,
                        temperature=temperature,
                        output_dir=Path("output"),
                    )

                    essay_templates = essay_result.get("essay_templates", {})
                    st.session_state.user_profile = user_profile
                    st.session_state.job_posting = job_posting
                    st.session_state.research_result = research_result
                    st.session_state.essay_result = essay_result
                    st.session_state.company_info = {"name": company, "team": team, "role": role}
                    st.session_state.pipeline_ready = True

                    status.update(label="완료", state="complete")
                    assistant_msg = _format_essay_markdown(essay_templates)
                    _append_message("assistant", assistant_msg)
                    st.markdown(assistant_msg)
                except Exception as exc:
                    status.update(label="실패", state="error")
                    error_msg = f"실행 중 오류가 발생했습니다: {type(exc).__name__}: {exc}"
                    _append_message("assistant", error_msg)
                    st.error(error_msg)
        return

    with st.chat_message("assistant"):
        with st.status("후속 요청을 반영해 자기소개서를 다시 작성하는 중", expanded=True) as status:
            try:
                revision_instruction = _build_revision_instruction(user_prompt)
                status.write("수집된 정보와 기존 결과를 유지한 채 요청 사항을 반영합니다.")
                company_info = st.session_state.company_info
                essay_result = run_essay_writer(
                    user_profile=st.session_state.user_profile,
                    job_posting=st.session_state.job_posting,
                    research_result=st.session_state.research_result,
                    company_name=company_info.get("name", ""),
                    team_name=company_info.get("team", ""),
                    role_name=company_info.get("role", ""),
                    model=writer_model_name,
                    temperature=temperature,
                    revision_instruction=revision_instruction,
                    output_dir=Path("output"),
                )
                st.session_state.essay_result = essay_result
                status.update(label="완료", state="complete")
                refreshed_templates = essay_result.get("essay_templates", {})
                assistant_msg = _format_essay_markdown(refreshed_templates)
                _append_message("assistant", assistant_msg)
                st.markdown(assistant_msg)
            except Exception as exc:
                status.update(label="실패", state="error")
                error_msg = f"재작성 중 오류가 발생했습니다: {type(exc).__name__}: {exc}"
                _append_message("assistant", error_msg)
                st.error(error_msg)


if __name__ == "__main__":
    main()
