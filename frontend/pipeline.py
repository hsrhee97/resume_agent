from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

OUTPUT_DIR = Path("output")


def _save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def persist_uploaded_pdf(uploaded_file: Any, output_dir: Path = OUTPUT_DIR) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / f"uploaded_{uploaded_file.name}"
    target.write_bytes(uploaded_file.getvalue())
    return target


def is_job_posting_usable(job_posting: dict[str, Any]) -> bool:
    if not isinstance(job_posting, dict) or not job_posting:
        return False
    if str(job_posting.get("error") or "").strip():
        return False

    company = job_posting.get("company", {})
    position = job_posting.get("position", {})
    requirements = job_posting.get("requirements", {})

    company_name = str(company.get("name") or "").strip() if isinstance(company, dict) else ""
    role_name = str(position.get("title") or "").strip() if isinstance(position, dict) else ""

    has_requirements = False
    has_core_detail = False
    if isinstance(requirements, dict):
        for key in ("main_tasks", "qualifications", "preferred", "tech_stack"):
            value = requirements.get(key)
            if isinstance(value, list) and any(str(item).strip() for item in value):
                has_requirements = True
                if key in ("main_tasks", "preferred", "tech_stack"):
                    has_core_detail = True
                break
            if isinstance(value, str) and value.strip():
                has_requirements = True
                if key in ("main_tasks", "preferred", "tech_stack"):
                    has_core_detail = True
                break

    essay_questions = job_posting.get("essay_questions", [])
    has_essay_questions = isinstance(essay_questions, list) and any(
        isinstance(item, dict) and str(item.get("question") or "").strip()
        for item in essay_questions
    )

    # URL 추출 "성공"의 최소 기준:
    # 1) 회사명 + 직무명
    # 2) 핵심 상세(main_tasks/preferred/tech_stack) 또는 자소서 문항
    if company_name and role_name and (has_core_detail or has_essay_questions):
        return True

    # 요건이 qualifications만 있거나, 회사/직무만 있는 상태는 실패로 간주해 fallback 유도
    if company_name and role_name and has_requirements and not (has_core_detail or has_essay_questions):
        return False
    return False


def _build_uploaded_image_payloads(job_images: list[Any]) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for idx, image in enumerate(job_images, start=1):
        try:
            content = image.getvalue() if hasattr(image, "getvalue") else b""
        except Exception:
            content = b""
        if not isinstance(content, (bytes, bytearray)) or not content:
            continue
        content_type = str(getattr(image, "type", "") or "image/jpeg").strip()
        if not content_type.startswith("image/"):
            continue
        name = str(getattr(image, "name", "") or f"uploaded_image_{idx}")
        payloads.append(
            {
                "url": name,
                "content_type": content_type,
                "content": bytes(content),
            }
        )
    return payloads


def _extract_text_from_uploaded_images(agent: Any, job_images: list[Any]) -> str:
    payloads = _build_uploaded_image_payloads(job_images)
    if not payloads:
        return ""
    try:
        return str(agent.job_crawler.extract_text_from_images(payloads) or "").strip()
    except Exception:
        return ""


def run_schema_extraction(
    pdf_path: str,
    job_url: str,
    llm_backend: str = "openai",
    hf_token: str = "",
    model_name: str = "",
    temperature: float = 0.3,
    job_text_fallback: str = "",
    job_images: list[Any] | None = None,
    output_dir: Path = OUTPUT_DIR,
) -> tuple[dict[str, Any], dict[str, Any]]:
    from backend1.preprocess_agent import FirstAgent

    agent = FirstAgent(
        llm_backend=llm_backend,
        hf_token=hf_token or None,
        model_name=model_name,
        temperature=temperature,
    )
    normalized_url = str(job_url or "").strip()
    result = agent.run(pdf_path=pdf_path, url=normalized_url or None, output_dir=str(output_dir))
    user_profile = result.get("profile", {}) if isinstance(result, dict) else {}
    job_posting = result.get("job_posting", {}) if isinstance(result, dict) else {}

    use_manual_fallback = not is_job_posting_usable(job_posting)
    if use_manual_fallback:
        fallback_chunks: list[str] = []
        manual_text = str(job_text_fallback or "").strip()
        if manual_text:
            fallback_chunks.append(f"[수동 입력 공고 텍스트]\n{manual_text}")
        image_text = _extract_text_from_uploaded_images(agent, job_images or [])
        if image_text:
            fallback_chunks.append(f"[공고 캡처 OCR 텍스트]\n{image_text}")

        if fallback_chunks:
            fallback_text = "\n\n".join(fallback_chunks).strip()
            job_posting = agent.extract_job_posting_from_text(
                raw_text=fallback_text,
                source_url=normalized_url,
                site="manual_fallback",
            )
            _save_json(output_dir / "job_posting.json", job_posting)

    if not isinstance(user_profile, dict) or not user_profile:
        raise RuntimeError("backend1 결과에서 user_profile을 생성하지 못했습니다.")
    if not isinstance(job_posting, dict) or not job_posting:
        raise RuntimeError("backend1 결과에서 job_posting을 생성하지 못했습니다.")
    return user_profile, job_posting


def run_company_research(
    user_profile: dict[str, Any],
    job_posting: dict[str, Any],
    provider: str = "tavily",
    model: str = "gpt-4.1-mini",
    output_dir: Path = OUTPUT_DIR,
) -> tuple[dict[str, Any], str, str, str]:
    from backend2.research_agent_app.service import run_research
    from backend3.essay_agent_app.prompts import extract_company_team_role

    company, team, role = extract_company_team_role(
        job_posting=job_posting,
        research_result={},
    )
    company = company or "지원 회사"
    team = team or "지원 팀"
    role = role or "지원 직무"

    try:
        research_result = run_research(
            company_name=company,
            team_name=team,
            role_name=role,
            job_posting=job_posting,
            user_profile=user_profile,
            provider=provider,
            model=model,
            verbose=False,
        )
    except Exception as exc:
        research_result = {
            "company_info": {"name": company, "team": team, "role": role},
            "scale": None,
            "insights": {},
            "llm_invoke": {
                "invoked": False,
                "raw_response": "",
                "parse_success": False,
                "used_fallback": True,
                "error": f"{type(exc).__name__}: {exc}",
            },
            "diagnostics": {
                "errors": [f"research failed: {type(exc).__name__}: {exc}"],
                "warnings": [],
            },
            "result_valid": False,
            "input_context": {
                "job_posting_attached": bool(job_posting),
                "user_profile_attached": bool(user_profile),
            },
            "reference_urls": [],
        }

    _save_json(output_dir / "backend2_run_output.json", research_result)
    return research_result, company, team, role


def run_essay_writer(
    user_profile: dict[str, Any],
    job_posting: dict[str, Any],
    research_result: dict[str, Any],
    company_name: str,
    team_name: str,
    role_name: str,
    model: str = "gpt-4.1-mini",
    temperature: float = 0.3,
    revision_instruction: str = "",
    output_dir: Path = OUTPUT_DIR,
) -> dict[str, Any]:
    from backend3.essay_agent_app.service import generate_essay_drafts

    essay_result = generate_essay_drafts(
        user_profile=user_profile,
        job_posting=job_posting,
        research_result=research_result,
        company_name=company_name,
        team_name=team_name,
        role_name=role_name,
        revision_instruction=revision_instruction,
        model=model,
        temperature=temperature,
    )
    _save_json(output_dir / "backend3_essay_output.json", essay_result)
    return essay_result


def get_hf_token() -> str:
    return os.getenv("HF_TOKEN", "").strip()
