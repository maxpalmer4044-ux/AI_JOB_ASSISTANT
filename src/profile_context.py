from __future__ import annotations

from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
PROFILE_CONTEXT_PATH = DATA_DIR / "profile_context.md"


DEFAULT_PROFILE_CONTEXT = """
Evaluate job opportunities for a candidate who wants roles at the intersection of AI, business
workflow improvement, practical implementation, and stakeholder-facing problem solving.

Prioritize roles where the candidate can translate messy business or operational problems into
AI-enabled workflows, prototypes, internal tools, process improvements, adoption plans, or
implementation support.

Strong-fit roles:
- AI enablement, AI implementation, AI operations, AI workflow automation, digital transformation,
  deployment strategy, internal AI tools, process improvement with AI, AI consulting, customer-facing
  implementation, product operations for AI tools, and practical GenAI adoption.

Moderate-fit roles:
- Product operations, strategy and operations with AI exposure, technical program management,
  innovation operations, solutions consulting, and systems roles when they involve process design,
  automation, or implementation.

Weak-fit roles:
- Pure machine learning engineering, research, backend/platform engineering, DevOps, pure sales,
  generic operations, admin-only CRM work, dashboard-only reporting, or roles where AI is only a
  buzzword with no implementation component.

Score roles from 1 to 10 across:
- Role Alignment
- Technical Fit
- Experience Fit
- Career Compounding
- Application Probability
- Location / Visa Feasibility
- Values Fit
- Resume Tailoring ROI

Use these weights:
- Role Alignment: 25%
- Technical Fit: 15%
- Experience Fit: 15%
- Career Compounding: 20%
- Application Probability: 10%
- Location / Visa Feasibility: 5%
- Values Fit: 5%
- Resume Tailoring ROI: 5%

Verdicts:
- 8.5-10: Primary Target
- 7.0-8.4: Strong Secondary
- 5.5-6.9: Controlled Effort
- Below 5.5: Skip

Be direct, practical, and willing to say skip. Prioritize actual fit, learning value, application
probability, and career compounding over prestige. Avoid buzzwords, exaggerated claims, fake
certainty, and double dashes.
""".strip()


def load_profile_context() -> str:
    if PROFILE_CONTEXT_PATH.exists():
        return PROFILE_CONTEXT_PATH.read_text(encoding="utf-8").strip()
    return DEFAULT_PROFILE_CONTEXT


def save_profile_context(context: str) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PROFILE_CONTEXT_PATH.write_text(context.strip(), encoding="utf-8")


def reset_profile_context() -> None:
    if PROFILE_CONTEXT_PATH.exists():
        PROFILE_CONTEXT_PATH.unlink()
