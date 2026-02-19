from __future__ import annotations

import sys

from dotenv import load_dotenv

from research_agent_app.cli import main

# Load API keys and runtime options from .env if present.
load_dotenv()
# Avoid creating/updating __pycache__ in restricted environments.
sys.dont_write_bytecode = True


if __name__ == "__main__":
    main()
