from __future__ import annotations

from typing import Any

from src.llm import call_json_llm
from src.utils import normalize_list


def _pick_angle(analysis_payload: dict[str, Any] | None) -> str:
    if not analysis_payload:
        return "AI workflow and implementation work"
    resume_section = analysis_payload.get("resume", {})
    if isinstance(resume_section, dict):
        emphasis = resume_section.get("resume_emphasis") or []
        if emphasis:
            return str(emphasis[0]).rstrip(".")
    fit_section = analysis_payload.get("fit", {})
    if isinstance(fit_section, dict):
        strongest = fit_section.get("strongest_alignment") or []
        if strongest:
            return str(strongest[0]).rstrip(".")
    return "AI workflow and implementation work"


def mock_outreach_drafts(
    job_record: dict[str, Any],
    analysis_payload: dict[str, Any] | None = None,
    custom_context: str = "",
) -> dict[str, str]:
    company = job_record.get("company") or "your team"
    title = job_record.get("job_title") or "the role"
    contact_name = (job_record.get("contact_name") or "").strip()
    first_name = contact_name.split()[0] if contact_name else ""
    intro_name = first_name if first_name else "there"
    angle = _pick_angle(analysis_payload)
    extra = f" {custom_context.strip()}" if custom_context.strip() else ""

    linkedin_note = (
        f"Hi {intro_name}, I came across the {title} role at {company} and it lines up with the kind of {angle} I enjoy. "
        f"I'd be glad to connect and learn more.{extra}"
    ).strip()

    follow_up_message = (
        f"Hi {intro_name}, I applied for the {title} role at {company} and wanted to follow up. "
        f"The role stood out because of its mix of practical AI, process improvement, and stakeholder-facing work. "
        f"If helpful, I'm happy to share a bit more context on relevant projects."
    ).strip()

    referral_request_message = (
        f"Hi {intro_name}, I’m exploring the {title} role at {company} and thought to reach out. "
        f"It looks closely aligned with my background in AI-enabled workflows and implementation-focused projects. "
        f"If you think it makes sense, I’d appreciate any advice or a referral."
    ).strip()

    return {
        "linkedin_note": linkedin_note,
        "follow_up_message": follow_up_message,
        "referral_request_message": referral_request_message,
    }


def generate_outreach_drafts(
    job_record: dict[str, Any],
    analysis_payload: dict[str, Any] | None,
    custom_context: str,
) -> tuple[dict[str, str], dict[str, Any]]:
    system_prompt = (
        "You write short, human-sounding outreach for a job search. Return only valid JSON. "
        "Do not use buzzwords, exaggerated claims, or double dashes."
    )
    user_prompt = f"""
Return JSON with exactly these keys:
- linkedin_note
- follow_up_message
- referral_request_message

Constraints:
- human-sounding
- not overly formal
- no buzzwords
- no exaggerated claims
- no double dashes
- each message should be 1 to 4 sentences

Job record:
{job_record}

Saved analysis:
{analysis_payload}

Optional context:
{custom_context}
""".strip()

    result, meta = call_json_llm(system_prompt, user_prompt)
    if result is None:
        return mock_outreach_drafts(job_record, analysis_payload, custom_context), meta

    normalized = {
        "linkedin_note": str(result.get("linkedin_note") or "").strip(),
        "follow_up_message": str(result.get("follow_up_message") or "").strip(),
        "referral_request_message": str(result.get("referral_request_message") or "").strip(),
    }
    if not all(normalized.values()):
        return mock_outreach_drafts(job_record, analysis_payload, custom_context), meta
    return normalized, meta
