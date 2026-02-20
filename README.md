# CoverFit

CoverFit is an AI resume-to-essay pipeline.
You upload one resume PDF and a job posting URL, then the system generates company-specific self-introduction essays through three backend stages.

## What It Does

- `backend1`: Extracts structured JSON from resume PDF and job posting URL.
- `backend2`: Runs company/role research and builds evidence-based insights.
- `backend3`: Writes final essay sections from backend1 + backend2 JSON outputs.
- `frontend`: Streamlit UI to run the full flow in one form.

## Project Structure

```text
resume_agent/
|-- backend1/
|   |-- preprocess_agent.py
|   `-- preprocess_agent_app/
|-- backend2/
|   |-- research_agent.py
|   `-- research_agent_app/
|-- backend3/
|   |-- essay_agent.py
|   `-- essay_agent_app/
|-- frontend/
|   |-- app.py
|   `-- pipeline.py
|-- output/
|-- resumes/
|-- .env.example
`-- requirements.txt
```

## Local Setup

1. Create and activate a virtual environment.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install dependencies.

```powershell
pip install -r requirements.txt
```

3. Create `.env` from `.env.example` and set keys.

```powershell
Copy-Item .env.example .env
```

## Environment Variables

Minimum variables used by this project:

```env
SEARCH_PROVIDER=tavily
VERBOSE=1
TAVILY_API_KEY=...
SERPER_API_KEY=...
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4.1-mini
BACKEND1_LLM_BACKEND=openai
BACKEND1_MODEL=gpt-4.1-mini
BACKEND1_TEMPERATURE=0.3
BACKEND1_VISION_MODEL=gpt-4.1-mini
OCR_LANG=kor+eng
```

Notes:

- `OPENAI_API_KEY` is required when using OpenAI-based flow.
- `TAVILY_API_KEY` or `SERPER_API_KEY` is needed for backend2 search.
- Do not commit `.env` to git.

## How to Run

### Full App (recommended)

```powershell
streamlit run frontend/app.py
```

### Backend 1 only (schema extraction)

```powershell
python backend1/preprocess_agent.py --pdf "resumes/your_resume.pdf" --url "https://example.com/job" --output "./output"
```

### Backend 2 only (company research)

```powershell
python backend2/research_agent.py --job-posting-json "output/job_posting.json" --user-profile-json "output/user_profile.json" --output "output/backend2_run_output.json"
```

### Backend 3 only (essay generation)

```powershell
python backend3/essay_agent.py --user-profile-json "output/user_profile.json" --job-posting-json "output/job_posting.json" --research-json "output/backend2_run_output.json" --output "output/backend3_essay_output.json"
```

## Output Files

- `output/user_profile.json`
- `output/job_posting.json`
- `output/backend2_run_output.json`
- `output/backend3_essay_output.json`

## Deployment (Streamlit Community Cloud)

Use the following settings:

- Main file path: `frontend/app.py`
- Python: 3.11 recommended
- Set secrets in Streamlit Cloud (do not upload `.env`)

Suggested secrets:

- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `TAVILY_API_KEY` and/or `SERPER_API_KEY`
- `SEARCH_PROVIDER`
- `VERBOSE`

## Deployment Checklist

- `.env` is not committed.
- API keys are set in deployment secrets.
- `requirements.txt` installs without errors.
- `output/` is writable at runtime.
- External API quota is sufficient for backend2/backend3 calls.
