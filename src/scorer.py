from __future__ import annotations

from typing import Any

from src.llm import call_json_llm
from src.profile_context import DEFAULT_PROFILE_CONTEXT
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
        "why_it_fits": strongest[:5] or ["Some overlap with the target AI workflow positioning, but the posting needs review."],
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
    evaluation_context = (profile_context or DEFAULT_PROFILE_CONTEXT).strip()
    user_prompt = f"""
Return JSON with exactly these keys:
- verdict: Primary Target, Strong Secondary, Controlled Effort, or Skip
- overall_fit_score: number from 1 to 10
- score_breakdown: object with Role Alignment, Technical Fit, Experience Fit, Career Compounding, Application Probability, Location / Visa Feasibility, Values Fit, Resume Tailoring ROI
- why_it_fits: list of 3 to 5 concise bullets
- concerns: list of 2 to 4 concise bullets
- best_resume_angle: concise label for the strongest resume, project, education, or experience angle from the candidate context
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
        "best_resume_angle": str(result.get("best_resume_angle") or "Workflow Automation Project").strip(),
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
            "Communication Workflow Automation Project",
            "Personal Productivity Workflow Tool",
            "Stakeholder Operations Experience",
            "AI And Innovation Education",
            "Operational Analytics Project",
            "Regulated Process Experience",
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
    evaluation_context = (profile_context or DEFAULT_PROFILE_CONTEXT).strip()
    user_prompt = f"""
Return JSON with exactly these keys:
- resume_emphasis: list of exactly 3 recommended resume or experience angles
- suggested_keywords: list of exactly 3 keywords to include
- drift_warning: string or null

Use the candidate context to infer the most relevant experience anchors. If the context does not
name specific projects or jobs, use generic labels such as Communication Workflow Automation Project,
Operational Analytics Project, Stakeholder Operations Experience, AI And Innovation Education, or
Personal Productivity Workflow Tool.
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
