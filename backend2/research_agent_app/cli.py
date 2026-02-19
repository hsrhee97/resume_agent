from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

from .service import run_research


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Company Research Agent for resume insights (LangGraph + RAG)",
    )
    parser.add_argument("--company", required=True, help="Company name")
    parser.add_argument("--team", required=True, help="Target team name")
    parser.add_argument("--role", required=True, help="Target role name")
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

    try:
        result = run_research(
            company_name=args.company,
            team_name=args.team,
            role_name=args.role,
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
