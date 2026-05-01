from __future__ import annotations

from typing import Any

from src.llm import call_json_llm
from src.utils import ANCHOR_PROJECTS, RED_FLAG_PATTERNS, TARGET_PROFILE, normalize_list


SCORE_WEIGHTS = {
    "Role Alignment": 0.25,
    "Technical Fit": 0.15,
    "Experience Fit": 0.15,
    "Career Compounding": 0.20,
    "Application Probability": 0.10,
    "Location / Visa Feasibility": 0.05,
    "Values Fit": 0.05,
    "Resume Tailoring ROI": 0.05,
}

MALCOLM_JOB_EVALUATION_CONTEXT = """
Evaluate jobs for Malcolm Palmer, an early-career AI + business profile based in Bologna, Italy.

Core positioning:
Malcolm is not a pure ML engineer, research scientist, generic business analyst, quota salesperson,
traditional CRM/admin operator, or deep backend/platform engineer. He is strongest as someone who
takes messy real-world problems and builds simple AI-enabled systems that improve how work gets done.
Prioritize roles where he translates business or operational problems into AI-enabled workflows,
prototypes, POCs, MVPs, adoption plans, and practical systems.

Strong-fit roles:
AI Enablement, AI Implementation, AI Operations, AI Workflow Automation, Deployment Strategist,
Forward Deployed AI, Digital Transformation, Business Transformation, AI Product Operations,
Internal AI Tools, Process Improvement + AI, AI Consulting, customer-facing AI implementation,
agentic AI workflow roles, and implementation-oriented AI governance.

Moderate-fit roles:
Product Operations, Technical Program Management, Strategy & Operations with AI exposure,
Innovation Operations, Solutions Consultant / Strategist, and CRM or systems roles only when they
involve AI automation, process design, or implementation.

Weak-fit roles:
Pure ML engineering, heavy data science/statistics, research, production software engineering,
backend/platform/devops, pure sales or BD, generic operations without AI/digital implementation,
marketing/content with light AI usage, admin CRM roles, dashboard-only reporting roles, and security
roles unless clearly AI governance/process-related.

Experience anchors:
1. IADLC Public Affairs & Operations: stakeholder coordination across 100+ stakeholders, CRM/data
systems, operational databases, fragmented inputs into structured outputs, lightweight AI workflows.
2. AI Email Workflow Agent: LLM context retrieval, summarization, task extraction, follow-up tracking,
and response drafting for communication workflows.
3. AI Job Search Workflow Agent: Python/Streamlit workflow agent for JD parsing, fit scoring, resume
emphasis, outreach drafts, and follow-up tracking.
4. Manufacturing Defect Model: operational and sensor data for production-line defect prediction and
decision-support signals.
5. Ohio House: regulated process environment, documentation, confidentiality, stakeholder communication.
6. Education: Master's in AI and Innovation Management at Bologna Business School, plus business and
philosophy background.

Technical fit:
Strong when the role asks for AI literacy, prompt engineering, agentic tools, basic Python/SQL, workflow
automation, analytics, process analysis, stakeholder translation, POCs/MVPs, requirements gathering,
GenAI enablement, and implementation support. Weak when it requires production engineering, advanced ML,
MLOps, backend systems, Kubernetes, cloud architecture, research publications, or advanced statistics as
the core job.

Location and timing:
Malcolm is a U.S. citizen studying in Bologna. He may need sponsorship for UK/EU roles and should not
self-reject unless a posting clearly requires existing unrestricted work authorization. U.S., London,
and Dublin are preferred. Summer/fall 2026 starts are better than immediate starts.

Values:
Flag roles negatively if they appear tied to manipulative ad-tech, predatory sales, gambling, pornography,
exploitative products, deceptive tactics, unethical surveillance, or AI that replaces judgment without
accountability. Do not automatically reject defense, energy, political, or industrial roles; evaluate the
actual work and moral tradeoffs.

Scoring:
Use 1 to 10 scores for Role Alignment, Technical Fit, Experience Fit, Career Compounding,
Application Probability, Location / Visa Feasibility, Values Fit, and Resume Tailoring ROI.
Weighted overall score uses: Role Alignment 25%, Technical Fit 15%, Experience Fit 15%,
Career Compounding 20%, Application Probability 10%, Location/Visa 5%, Values Fit 5%,
Resume Tailoring ROI 5%.

Verdicts:
8.5-10 Primary Target
7.0-8.4 Strong Secondary
5.5-6.9 Controlled Effort
Below 5.5 Skip

Style:
Be direct, practical, and willing to say skip. Do not flatter Malcolm. Do not overrate prestige.
Prioritize fit, traction probability, and career compounding. Avoid buzzwords, fake certainty, and
double dashes.
""".strip()


def classify_target_score(score: int | float | None) -> str:
    if score is None:
        return "Not Scored"
    score = float(score)
    if score >= 8.5:
        return "Primary Target"
    if score >= 7:
        return "Strong Secondary"
    if score >= 5.5:
        return "Controlled Effort"
    return "Skip"


def _weighted_score(score_breakdown: dict[str, Any]) -> float:
    total = 0.0
    for label, weight in SCORE_WEIGHTS.items():
        try:
            value = float(score_breakdown.get(label, 5))
        except (TypeError, ValueError):
            value = 5
        total += max(1, min(10, value)) * weight
    return round(total, 1)


def _score_dimensions(job_description: str) -> list[tuple[str, int]]:
    lowered = job_description.lower()
    scores = []
    for label, keywords in TARGET_PROFILE.items():
        hits = sum(1 for keyword in keywords if keyword in lowered)
        scores.append((label, hits))
    return scores


def _detect_drift(job_description: str) -> str | None:
    lowered = job_description.lower()
    if any(pattern in lowered for pattern in RED_FLAG_PATTERNS["Pure engineering drift"]):
        return "Warning: this role is drifting toward pure engineering more than applied AI workflow work."
    if any(pattern in lowered for pattern in RED_FLAG_PATTERNS["Pure sales drift"]):
        return "Warning: this role is drifting toward pure sales rather than AI implementation."
    if any(pattern in lowered for pattern in RED_FLAG_PATTERNS["Generic operations drift"]):
        return "Warning: this role may be too generic operations-focused and light on AI ownership."
    return None


def mock_score_role_fit(job_description: str) -> dict[str, Any]:
    dimension_scores = _score_dimensions(job_description)
    positive_dimensions = [(label, hits) for label, hits in dimension_scores if hits > 0]
    coverage_ratio = len(positive_dimensions) / max(len(TARGET_PROFILE), 1)

    base_score = round(3 + (coverage_ratio * 7))
    base_score = max(1, min(10, base_score))

    if any(pattern in job_description.lower() for pattern in RED_FLAG_PATTERNS["Pure engineering drift"]):
        base_score = max(1, base_score - 2)
    if any(pattern in job_description.lower() for pattern in RED_FLAG_PATTERNS["Pure sales drift"]):
        base_score = max(1, base_score - 3)
    if any(pattern in job_description.lower() for pattern in RED_FLAG_PATTERNS["Generic operations drift"]):
        base_score = max(1, base_score - 2)

    ranked = sorted(dimension_scores, key=lambda item: item[1], reverse=True)
    strongest = [f"{label}: matched {hits} related signal(s)" for label, hits in ranked if hits > 0][:4]
    weakest = [label for label, hits in ranked if hits == 0][:4]

    explanation = (
        "This role was scored against an AI workflow and implementation profile that emphasizes practical AI use, "
        "business process improvement, stakeholder work, and prototype-driven execution."
    )

    score_breakdown = {
        "Role Alignment": base_score,
        "Technical Fit": min(10, max(1, base_score)),
        "Experience Fit": min(10, max(1, base_score - 1)),
        "Career Compounding": min(10, max(1, base_score)),
        "Application Probability": 6,
        "Location / Visa Feasibility": 6,
        "Values Fit": 8,
        "Resume Tailoring ROI": min(10, max(1, base_score)),
    }
    score = _weighted_score(score_breakdown)
    verdict = classify_target_score(score)

    return {
        "fit_score": score,
        "fit_category": verdict,
        "verdict": verdict,
        "overall_fit_score": score,
        "score_breakdown": score_breakdown,
        "explanation": explanation,
        "strongest_alignment": strongest or ["Limited direct alignment detected from the available text."],
        "weakest_alignment": weakest or ["No major gap categories surfaced from the available text."],
        "why_it_fits": strongest[:5] or ["Some overlap with Malcolm's AI workflow positioning, but the posting needs review."],
        "concerns": weakest[:4] or ["No major concern surfaced from the available text."],
        "best_resume_angle": "Email Agent",
        "suggested_resume_tweaks": ["Emphasize practical AI workflow design and stakeholder-facing implementation."],
        "outreach_recommendation": {
            "recommended": verdict in {"Primary Target", "Strong Secondary"},
            "best_target_type": "Hiring manager or implementation team member",
            "suggested_short_angle": "Practical AI workflow prototypes and business-process translation.",
        },
        "application_effort": "High" if verdict == "Primary Target" else "Medium" if verdict == "Strong Secondary" else "Low" if verdict == "Controlled Effort" else "Skip",
        "final_recommendation": "Apply now" if verdict == "Primary Target" else "Apply with light tailoring" if verdict == "Strong Secondary" else "Apply only if quick" if verdict == "Controlled Effort" else "Skip",
    }


def score_role_fit(
    job_description: str,
    parsed_analysis: dict[str, Any],
    profile_context: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    system_prompt = "You are a practical job evaluation agent. Return only valid JSON."
    evaluation_context = (profile_context or MALCOLM_JOB_EVALUATION_CONTEXT).strip()
    user_prompt = f"""
Return JSON with exactly these keys:
- verdict: Primary Target, Strong Secondary, Controlled Effort, or Skip
- overall_fit_score: number from 1 to 10
- score_breakdown: object with Role Alignment, Technical Fit, Experience Fit, Career Compounding, Application Probability, Location / Visa Feasibility, Values Fit, Resume Tailoring ROI
- why_it_fits: list of 3 to 5 concise bullets
- concerns: list of 2 to 4 concise bullets
- best_resume_angle: one of Email Agent, Job Search Agent, Manufacturing Defect Model, IADLC, Education, Ohio House
- suggested_resume_tweaks: list of 1 to 3 concise tweaks
- outreach_recommendation: object with recommended boolean, best_target_type string, suggested_short_angle string
- application_effort: High, Medium, Low, or Skip
- final_recommendation: Apply now, Apply with light tailoring, Apply only if quick, Skip, or Save for later
- explanation: short plain-English decision summary
- strongest_alignment: list
- weakest_alignment: list

Use this evaluation context:
{evaluation_context}

Parsed job analysis:
{parsed_analysis}

Job description:
{job_description}
""".strip()

    result, meta = call_json_llm(system_prompt, user_prompt)
    if result is None:
        return mock_score_role_fit(job_description), meta

    fit_score = result.get("overall_fit_score", result.get("fit_score"))
    try:
        fit_score = round(float(fit_score), 1)
    except (TypeError, ValueError):
        fit_score = 5
    fit_score = max(1, min(10, fit_score))

    score_breakdown = result.get("score_breakdown") if isinstance(result.get("score_breakdown"), dict) else {}
    normalized_breakdown = {}
    for label in SCORE_WEIGHTS:
        try:
            normalized_breakdown[label] = round(float(score_breakdown.get(label, 5)), 1)
        except (TypeError, ValueError):
            normalized_breakdown[label] = 5.0
        normalized_breakdown[label] = max(1, min(10, normalized_breakdown[label]))

    if not result.get("overall_fit_score"):
        fit_score = _weighted_score(normalized_breakdown)
    verdict = str(result.get("verdict") or classify_target_score(fit_score)).strip()
    if verdict not in {"Primary Target", "Strong Secondary", "Controlled Effort", "Skip"}:
        verdict = classify_target_score(fit_score)

    normalized = {
        "fit_score": fit_score,
        "fit_category": verdict,
        "verdict": verdict,
        "overall_fit_score": fit_score,
        "score_breakdown": normalized_breakdown,
        "explanation": str(result.get("explanation") or "").strip()
        or "Fit explanation not provided by the model.",
        "strongest_alignment": normalize_list(result.get("strongest_alignment"), limit=5),
        "weakest_alignment": normalize_list(result.get("weakest_alignment"), limit=5),
        "why_it_fits": normalize_list(result.get("why_it_fits"), limit=5),
        "concerns": normalize_list(result.get("concerns"), limit=4),
        "best_resume_angle": str(result.get("best_resume_angle") or "Email Agent").strip(),
        "suggested_resume_tweaks": normalize_list(result.get("suggested_resume_tweaks"), limit=3),
        "outreach_recommendation": result.get("outreach_recommendation")
        if isinstance(result.get("outreach_recommendation"), dict)
        else {
            "recommended": verdict in {"Primary Target", "Strong Secondary"},
            "best_target_type": "Hiring manager or implementation team member",
            "suggested_short_angle": "Practical AI workflow implementation and business-process translation.",
        },
        "application_effort": str(result.get("application_effort") or "Medium").strip(),
        "final_recommendation": str(result.get("final_recommendation") or "Apply with light tailoring").strip(),
    }
    return normalized, meta


def mock_resume_emphasis(job_description: str, parsed_analysis: dict[str, Any], fit_result: dict[str, Any]) -> dict[str, Any]:
    lowered = job_description.lower()
    scored_projects = []
    for project, keywords in ANCHOR_PROJECTS.items():
        score = sum(1 for keyword in keywords if keyword in lowered)
        scored_projects.append((project, score))
    ranked_projects = [project for project, score in sorted(scored_projects, key=lambda item: item[1], reverse=True) if score > 0]

    if len(ranked_projects) < 3:
        fallbacks = [
            "Email AI Workflow Agent",
            "AI Job Search Workflow Agent",
            "IADLC Public Affairs & Operations",
            "AI + Innovation Management master’s program",
            "Manufacturing Defect Model",
            "Ohio House process/stakeholder experience",
        ]
        for project in fallbacks:
            if project not in ranked_projects:
                ranked_projects.append(project)
            if len(ranked_projects) >= 3:
                break

    suggested_keywords = normalize_list(
        parsed_analysis.get("ats_keywords", []) + parsed_analysis.get("keywords", []) + parsed_analysis.get("business_keywords", []),
        limit=6,
    )[:3]

    emphasis_lines = [
        f"Lead with {ranked_projects[0]} because it most directly matches the role's stated needs.",
        f"Use {ranked_projects[1]} to reinforce stakeholder-facing process and execution experience.",
        f"Reference {ranked_projects[2]} to show broader AI, strategy, or operational context.",
    ]

    return {
        "resume_emphasis": emphasis_lines,
        "suggested_keywords": suggested_keywords or ["AI implementation", "workflow improvement", "stakeholder communication"],
        "drift_warning": _detect_drift(job_description),
    }


def recommend_resume_emphasis(
    job_description: str,
    parsed_analysis: dict[str, Any],
    fit_result: dict[str, Any],
    profile_context: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    system_prompt = (
        "You are recommending resume emphasis angles for a practical AI workflow and implementation candidate. "
        "Return only valid JSON."
    )
    evaluation_context = (profile_context or MALCOLM_JOB_EVALUATION_CONTEXT).strip()
    user_prompt = f"""
Return JSON with exactly these keys:
- resume_emphasis: list of exactly 3 recommended resume or experience angles
- suggested_keywords: list of exactly 3 keywords to include
- drift_warning: string or null

The available experience anchors are:
1. Email AI Workflow Agent
2. Manufacturing Defect Model
3. IADLC Public Affairs & Operations
4. Ohio House process/stakeholder experience
5. AI + Innovation Management master’s program

Keep the suggestions practical and defensible.

Use this candidate context:
{evaluation_context}

Parsed job analysis:
{parsed_analysis}

Fit result:
{fit_result}

Job description:
{job_description}
""".strip()

    result, meta = call_json_llm(system_prompt, user_prompt)
    if result is None:
        return mock_resume_emphasis(job_description, parsed_analysis, fit_result), meta

    normalized = {
        "resume_emphasis": normalize_list(result.get("resume_emphasis"), limit=3),
        "suggested_keywords": normalize_list(result.get("suggested_keywords"), limit=3),
        "drift_warning": result.get("drift_warning"),
    }
    if len(normalized["resume_emphasis"]) < 3:
        fallback = mock_resume_emphasis(job_description, parsed_analysis, fit_result)
        normalized["resume_emphasis"] = fallback["resume_emphasis"]
    if len(normalized["suggested_keywords"]) < 3:
        fallback = mock_resume_emphasis(job_description, parsed_analysis, fit_result)
        normalized["suggested_keywords"] = fallback["suggested_keywords"]
    return normalized, meta
