# AI Job Search Workflow Agent

## What This Project Does

This project is a lightweight local workflow tool for managing a high-volume job search. Instead of acting like a general chatbot, it helps turn messy job descriptions and application notes into structured decisions and next actions.

The app lets you:

- save and track job applications
- parse job descriptions into structured requirements
- score role fit against a defined AI workflow and implementation profile
- recommend which resume angles to emphasize
- generate short outreach drafts
- flag follow-ups that are due, overdue, or missing outreach

## Why It Was Built

Job searching can quickly become fragmented. Roles live across different job boards, notes get buried, and it becomes hard to remember which positions are actually a fit, where outreach has happened, and which follow-ups matter most.

This app was built as a practical personal productivity system for turning unstructured job search inputs into a repeatable workflow.

## MVP Features

- Streamlit interface with focused workflow tabs:
  - Home
  - Add Job
  - Analyze JD
  - Dashboard
  - Outreach Generator
- Custom retro-futurist Streamlit UI inspired by 1950s diner and concept-art aesthetics
- SQLite storage for local application records
- Job description parsing for responsibilities, skills, keywords, red flags, and ATS terms
- Role-fit scoring against an AI enablement / workflow improvement target profile
- Resume emphasis recommendations tied to actual anchor projects and experiences
- Short outreach draft generation for LinkedIn, follow-ups, and referral asks
- Hugging Face Router integration for live Llama analysis
- Mock fallback so the app still runs without any API keys

## Tech Stack

- Python
- Streamlit
- SQLite
- pandas
- requests
- python-dotenv

## Project Structure

```text
job-search-agent/
  app.py
  requirements.txt
  README.md
  .env.example
  data/
    sample_jobs.csv
    jobs.db
  src/
    __init__.py
    database.py
    llm.py
    outreach.py
    parser.py
    scorer.py
    utils.py
```

## Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env`.
4. Add your Hugging Face token to `.env` if you want live Llama analysis. If you leave it empty, the app will fall back to mock mode.

## How To Run Locally

```bash
streamlit run app.py
```

The app will create `data/jobs.db` automatically on first run. If the database is empty, it will seed from `data/sample_jobs.csv`.

## LLM Behavior

The app uses one live LLM path: `Llama` via Hugging Face Router.

- If `HF_TOKEN` is configured, the app uses the selected `HF_MODEL` for live analysis.
- If the token is missing, the request fails, or the model returns malformed JSON, the app falls back to deterministic local output instead of crashing.

## Resume Framing

This is best described as an AI-enabled workflow project, not a production platform or a generic chatbot.

Strong framing:

- built a local AI workflow system for job-search decision support
- used structured extraction, fit scoring, and outreach drafting to support repeatable application prioritization
- designed the tool around practical AI implementation and workflow improvement rather than pure model development

## Defensible Talking Points

- The app stores structured application data locally in SQLite.
- The analysis layer uses Llama through Hugging Face Router when a token is available, but it still works in mock mode.
- Role-fit scoring is explicitly aligned to a defined professional profile rather than generic resume matching.
- Outreach generation is constrained to short, direct, human-sounding messages.
- Follow-up tracking is operational, not theoretical. It computes next actions and surfaces overdue items.

## Optional Stretch Features

Only add these after the MVP is stable:

1. Bulk import job applications from CSV
2. Export tailored application packets or analysis summaries
3. Add a simple interview-prep page based on saved job descriptions

## Resume Bullet Options

- Designed and built an AI-powered job search workflow agent that stores applications, parses job descriptions, scores role fit, generates outreach drafts, and tracks follow-up actions locally.
- Implemented a Python and Streamlit workflow tool with SQLite storage, structured job-description analysis, resume emphasis recommendations, and follow-up prioritization logic.
- Built a lightweight AI-enabled application management system that converts unstructured role descriptions into structured requirements, fit assessments, outreach drafts, and next-step tracking.
