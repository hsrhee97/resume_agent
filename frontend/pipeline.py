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


def run_schema_extraction(
    pdf_path: str,
    job_url: str,
    llm_backend: str = "openai",
    hf_token: str = "",
    model_name: str = "",
    temperature: float = 0.3,
    output_dir: Path = OUTPUT_DIR,
) -> tuple[dict[str, Any], dict[str, Any]]:
    from backend1.preprocess_agent import FirstAgent

    agent = FirstAgent(
        llm_backend=llm_backend,
        hf_token=hf_token or None,
        model_name=model_name,
        temperature=temperature,
    )
    result = agent.run(pdf_path=pdf_path, url=job_url, output_dir=str(output_dir))
    user_profile = result.get("profile", {}) if isinstance(result, dict) else {}
    job_posting = result.get("job_posting", {}) if isinstance(result, dict) else {}
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
