# AI Job Search Workflow Agent

A local Streamlit app for turning job-search inputs into structured decisions and next actions.

The app is designed for people managing a high-volume search across job boards, company career pages, referrals, and outreach. It is not a general chatbot. It is a workflow tool that stores applications, parses job descriptions, scores fit against a configurable profile, recommends application emphasis, drafts outreach messages, and helps prioritize follow-up.

## Features

- Add and edit job applications with company, title, location, status, dates, notes, links, and job descriptions
- Fetch job descriptions from public job links, including LinkedIn-style pages and common job-board layouts
- Parse pasted or fetched job descriptions into responsibilities, skills, keywords, red flags, and ATS terms
- Score role fit using a weighted rubric and a customizable user profile
- Show a readable analysis brief with verdict, score breakdown, concerns, resume angle, and application effort
- Generate short outreach drafts for LinkedIn messages, follow-ups, and referral requests
- Track application status, follow-up dates, priority, and next actions in a local dashboard
- Edit fit score, fit category, priority, and follow-up status directly from the dashboard
- Customize the LLM evaluation context from the app settings page
- Run locally with SQLite storage and mock fallback when no LLM token is configured

## Tech Stack

- Python
- Streamlit
- SQLite
- pandas
- requests
- python-dotenv
- Hugging Face Router for Llama-based LLM calls

## Project Structure

```text
AI_JOB_ASSISTANT/
  app.py
  README.md
  requirements.txt
  .env.example
  .gitignore
  assets/
  data/
    sample_jobs.csv
  src/
    __init__.py
    database.py
    importer.py
    job_fetcher.py
    llm.py
    outreach.py
    parser.py
    profile_context.py
    scorer.py
    utils.py
```

## Setup

Create and activate a virtual environment, then install dependencies:

```bash
pip install -r requirements.txt
```

Create a local environment file from the example:

```bash
copy .env.example .env
```

Add a Hugging Face token if you want live LLM analysis:

```env
HF_TOKEN=your_huggingface_token_here
HF_MODEL=meta-llama/Llama-3.3-70B-Instruct:groq
```

If `HF_TOKEN` is blank, the app still runs using local mock outputs.

## Run Locally

```bash
streamlit run app.py
```

The app creates `data/jobs.db` automatically on first run. If the database is empty, it seeds sample records from `data/sample_jobs.csv`.

## Customizing The Evaluation Profile

The app includes a `Settings` tab where users can edit the LLM evaluation context. This context controls how jobs are scored, which roles are prioritized, what red flags matter, and what application angles should be recommended.

By default, the app uses the built-in profile context in `src/scorer.py`. When a user saves a custom context, it is stored locally at:

```text
data/profile_context.md
```

That file is intentionally ignored by Git so each user can keep their own private job-search rules and constraints.

## LLM Behavior

The app uses Llama through Hugging Face Router when `HF_TOKEN` is configured.

LLM-backed features include:

- job description analysis
- role-fit scoring
- resume or application emphasis recommendations
- outreach draft generation

Local app logic handles:

- SQLite storage
- dashboard metrics
- editing records
- date validation
- follow-up priority logic
- fallback mock outputs

If the LLM call fails or returns malformed JSON, the app falls back to deterministic local output instead of crashing.

## Job Link Fetching

The app can fetch public job description pages and clean the result before analysis. It includes extra cleanup for LinkedIn-style pages and common job-board layouts such as Greenhouse, Ashby, and Workday.

Some sites block unauthenticated scraping or render job text dynamically. If a page cannot expose enough useful text, paste the job description manually into the analyzer.

## Data And Privacy

This app is designed to run locally.

Do not commit these files to a public repository:

- `.env`
- `data/jobs.db`
- `data/profile_context.md`
- log files
- cache files such as `__pycache__/`

Use `.env.example` to show required environment variables without exposing credentials.

## Current Limitations

- Job-board link fetching depends on what the page exposes publicly.
- LLM output quality depends on the configured model and the profile context.
- The app is a local productivity tool, not a hosted multi-user system.
- There is no official LinkedIn API integration for personal saved/applied jobs.

## Possible Next Improvements

- Add CSV export for selected applications and analysis summaries
- Add batch import for multiple pasted job links
- Add a comparison view for multiple analyzed roles
