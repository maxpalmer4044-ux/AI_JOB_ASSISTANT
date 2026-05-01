from __future__ import annotations

import re
from typing import Any

from src.llm import call_json_llm
from src.utils import (
    AI_KEYWORD_BANK,
    BUSINESS_KEYWORD_BANK,
    RED_FLAG_PATTERNS,
    find_keyword_matches,
    normalize_list,
    top_terms,
)


def _extract_lines(job_description: str) -> list[str]:
    return [line.strip(" -•\t") for line in job_description.splitlines() if line.strip()]


def _extract_bullets_by_signal(lines: list[str], signals: list[str], limit: int = 8) -> list[str]:
    matches = [line for line in lines if any(signal in line.lower() for signal in signals)]
    return normalize_list(matches, limit=limit)


def mock_parse_job_description(job_description: str) -> dict[str, Any]:
    lines = _extract_lines(job_description)
    responsibilities = _extract_bullets_by_signal(
        lines,
        ["build", "lead", "support", "coordinate", "manage", "design", "partner", "drive", "turn", "deliver"],
        limit=6,
    )
    if not responsibilities:
        responsibilities = normalize_list(lines[:6], limit=6)

    required_skills = _extract_bullets_by_signal(
        lines,
        ["required", "must", "experience", "qualification", "skills", "ability"],
        limit=8,
    )
    preferred_skills = _extract_bullets_by_signal(
        lines,
        ["preferred", "nice to have", "bonus", "plus"],
        limit=6,
    )

    ai_keywords = find_keyword_matches(job_description, AI_KEYWORD_BANK)
    business_keywords = find_keyword_matches(job_description, BUSINESS_KEYWORD_BANK)

    red_flags = []
    lowered = job_description.lower()
    for label, patterns in RED_FLAG_PATTERNS.items():
        if any(pattern in lowered for pattern in patterns):
            red_flags.append(label)
    if not red_flags:
        red_flags.append("No major red flags detected from keyword scan.")

    ats_keywords = normalize_list(required_skills + ai_keywords + business_keywords + top_terms(job_description, limit=12), limit=10)

    return {
        "responsibilities": responsibilities or ["Review the full description manually."],
        "required_skills": required_skills or top_terms(job_description, limit=6),
        "preferred_skills": preferred_skills or ["No explicit preferred skills detected."],
        "keywords": ai_keywords or ["No obvious AI or automation keywords detected."],
        "business_keywords": business_keywords or ["No obvious process or business keywords detected."],
        "red_flags": red_flags,
        "ats_keywords": ats_keywords or top_terms(job_description, limit=10),
    }


def parse_job_description(job_description: str) -> tuple[dict[str, Any], dict[str, Any]]:
    if not job_description.strip():
        raise ValueError("Job description cannot be empty.")

    system_prompt = (
        "You are extracting structured job-search analysis. Return only valid JSON. "
        "Do not add commentary outside the JSON object."
    )
    user_prompt = f"""
Parse the following job description and return JSON with exactly these keys:
- responsibilities: list of short bullet-like strings
- required_skills: list
- preferred_skills: list
- keywords: list of AI/digital/automation keywords
- business_keywords: list of business/process keywords
- red_flags: list of possible red flags or drift signals
- ats_keywords: list of top 10 ATS keywords

Keep items concise and grounded in the text.

Job description:
{job_description}
""".strip()

    result, meta = call_json_llm(system_prompt, user_prompt)
    if result is None:
        return mock_parse_job_description(job_description), meta

    normalized = {
        "responsibilities": normalize_list(result.get("responsibilities"), limit=8),
        "required_skills": normalize_list(result.get("required_skills"), limit=10),
        "preferred_skills": normalize_list(result.get("preferred_skills"), limit=8),
        "keywords": normalize_list(result.get("keywords"), limit=10),
        "business_keywords": normalize_list(result.get("business_keywords"), limit=10),
        "red_flags": normalize_list(result.get("red_flags"), limit=6),
        "ats_keywords": normalize_list(result.get("ats_keywords"), limit=10),
    }
    return normalized, meta
