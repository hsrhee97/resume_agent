from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

from .service import run_research

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_JOB_POSTING_JSON = str(REPO_ROOT / "output" / "job_posting.json")
DEFAULT_USER_PROFILE_JSON = str(REPO_ROOT / "output" / "user_profile.json")


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


def _extract_company_team_role(
    company_arg: Optional[str],
    team_arg: Optional[str],
    role_arg: Optional[str],
    job_posting: dict[str, Any],
) -> tuple[str, str, str]:
    company = (company_arg or "").strip()
    team = (team_arg or "").strip()
    role = (role_arg or "").strip()

    if isinstance(job_posting, dict):
        company_block = job_posting.get("company")
        position_block = job_posting.get("position")
        if not company and isinstance(company_block, dict):
            company = str(company_block.get("name") or "").strip()
        if not team and isinstance(position_block, dict):
            team = str(position_block.get("department") or "").strip()
        if not role and isinstance(position_block, dict):
            role = str(position_block.get("title") or "").strip()

    if not company:
        raise SystemExit("Missing company. Use --company or provide company.name in --job-posting-json.")
    if not team:
        raise SystemExit("Missing team. Use --team or provide position.department in --job-posting-json.")
    if not role:
        raise SystemExit("Missing role. Use --role or provide position.title in --job-posting-json.")
    return company, team, role


def _validate_backend1_outputs(job_posting: dict[str, Any], user_profile: dict[str, Any]) -> None:
    company_ok = isinstance(job_posting.get("company"), dict)
    position_ok = isinstance(job_posting.get("position"), dict)
    profile_ok = isinstance(user_profile.get("user_profile"), dict)
    if not company_ok or not position_ok:
        raise SystemExit(
            "job_posting JSON does not match expected backend1 structure "
            "(requires 'company' and 'position' objects)."
        )
    if not profile_ok:
        raise SystemExit(
            "user_profile JSON does not match expected backend1 structure "
            "(requires 'user_profile' object)."
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Company Research Agent for resume insights (LangGraph + RAG)",
    )
    parser.add_argument("--company", default="", help="Company name")
    parser.add_argument("--team", default="", help="Target team name")
    parser.add_argument("--role", default="", help="Target role name")
    parser.add_argument(
        "--job-posting-json",
        default=DEFAULT_JOB_POSTING_JSON,
        help="Path to JOB_POSTING_SCHEMA-based JSON",
    )
    parser.add_argument(
        "--user-profile-json",
        default=DEFAULT_USER_PROFILE_JSON,
        help="Path to USER_PROFILE_SCHEMA-based JSON",
    )
    parser.add_argument(
        "--provider",
        default=os.getenv("SEARCH_PROVIDER", "tavily"),
        choices=("tavily", "serper"),
        help="Search backend",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        help="OpenAI model name for insight extraction",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=os.getenv("VERBOSE", "0").strip() in ("1", "true", "TRUE", "yes", "YES"),
        help="Print intermediate progress logs to stderr",
    )
    parser.add_argument(
        "--output",
        default="run_output.json",
        help="File path to save final JSON output (default: run_output.json)",
    )

    args = parser.parse_args()
    job_posting = _load_required_json(args.job_posting_json, "job_posting")
    user_profile = _load_required_json(args.user_profile_json, "user_profile")
    _validate_backend1_outputs(job_posting, user_profile)
    company, team, role = _extract_company_team_role(
        company_arg=args.company,
        team_arg=args.team,
        role_arg=args.role,
        job_posting=job_posting,
    )

    try:
        result = run_research(
            company_name=company,
            team_name=team,
            role_name=role,
            job_posting=job_posting,
            user_profile=user_profile,
            provider=args.provider,
            model=args.model,
            verbose=args.verbose,
        )
    except Exception as exc:
        raise SystemExit(f"Research run failed: {exc}") from exc

    output_text = json.dumps(result, ensure_ascii=False, indent=2)
    output_hash = hashlib.sha256(output_text.encode("utf-8")).hexdigest()[:12]
    output_path = Path(args.output).expanduser().resolve()
    with output_path.open("w", encoding="utf-8") as output_file:
        output_file.write(output_text + "\n")
    print(
        f"[Output] file={output_path} sha256={output_hash}",
        file=sys.stderr,
        flush=True,
    )
    print(output_text)
