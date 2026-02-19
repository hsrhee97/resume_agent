from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

from .service import generate_essay_drafts

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_USER_PROFILE_JSON = str(REPO_ROOT / "output" / "user_profile.json")
DEFAULT_JOB_POSTING_JSON = str(REPO_ROOT / "output" / "job_posting.json")
DEFAULT_RESEARCH_JSON = str(REPO_ROOT / "output" / "backend2_run_output.json")
DEFAULT_OUTPUT_JSON = str(REPO_ROOT / "output" / "backend3_essay_output.json")


def _load_required_json(path_value: Optional[str], label: str) -> dict[str, Any]:
    if not path_value:
        raise SystemExit(f"{label} path is required.")

    path = Path(path_value).expanduser().resolve()
    if not path.exists():
        raise SystemExit(f"{label} file does not exist: {path}")

    try:
        raw = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raw = path.read_text(encoding="utf-8-sig")

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid {label} JSON ({path}): {exc}") from exc

    if not isinstance(parsed, dict):
        raise SystemExit(f"{label} JSON must be an object: {path}")
    return parsed


def _validate_inputs(
    user_profile: dict[str, Any],
    job_posting: dict[str, Any],
    research_result: dict[str, Any],
) -> None:
    if not isinstance(user_profile.get("user_profile"), dict):
        raise SystemExit(
            "user_profile JSON shape mismatch: expected 'user_profile' object "
            "(backend1 output/user_profile.json)."
        )
    if not isinstance(job_posting.get("company"), dict) or not isinstance(
        job_posting.get("position"), dict
    ):
        raise SystemExit(
            "job_posting JSON shape mismatch: expected 'company' and 'position' objects "
            "(backend1 output/job_posting.json)."
        )
    if not isinstance(research_result.get("insights"), dict):
        raise SystemExit(
            "research JSON shape mismatch: expected 'insights' object "
            "(backend2 output/backend2_run_output.json)."
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Essay Writer Agent (backend3) using backend1+backend2 JSON outputs",
    )
    parser.add_argument("--company", default="", help="Override company name")
    parser.add_argument("--team", default="", help="Override team name")
    parser.add_argument("--role", default="", help="Override role name")
    parser.add_argument(
        "--user-profile-json",
        default=DEFAULT_USER_PROFILE_JSON,
        help="Path to backend1 output user_profile.json",
    )
    parser.add_argument(
        "--job-posting-json",
        default=DEFAULT_JOB_POSTING_JSON,
        help="Path to backend1 output job_posting.json",
    )
    parser.add_argument(
        "--research-json",
        default=DEFAULT_RESEARCH_JSON,
        help="Path to backend2 output backend2_run_output.json",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        help="OpenAI model name for essay drafting",
    )
    parser.add_argument(
        "--temperature",
        default=0.3,
        type=float,
        help="Sampling temperature for LLM writer",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT_JSON,
        help="File path to save final JSON output",
    )
    args = parser.parse_args()

    user_profile = _load_required_json(args.user_profile_json, "user_profile")
    job_posting = _load_required_json(args.job_posting_json, "job_posting")
    research_result = _load_required_json(args.research_json, "research_result")
    _validate_inputs(user_profile, job_posting, research_result)

    try:
        result = generate_essay_drafts(
            user_profile=user_profile,
            job_posting=job_posting,
            research_result=research_result,
            company_name=args.company,
            team_name=args.team,
            role_name=args.role,
            model=args.model,
            temperature=args.temperature,
        )
    except Exception as exc:
        raise SystemExit(f"Essay generation failed: {exc}") from exc

    output_text = json.dumps(result, ensure_ascii=False, indent=2)
    output_hash = hashlib.sha256(output_text.encode("utf-8")).hexdigest()[:12]
    output_path = Path(args.output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as output_file:
        output_file.write(output_text + "\n")
    print(
        f"[Output] file={output_path} sha256={output_hash}",
        file=sys.stderr,
        flush=True,
    )
    print(output_text)
