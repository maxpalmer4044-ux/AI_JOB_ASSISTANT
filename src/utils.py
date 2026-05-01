from __future__ import annotations

import json
import re
from collections import Counter
from datetime import date, datetime
from typing import Any

import pandas as pd


STATUS_OPTIONS = [
    "Saved",
    "Applied",
    "Networking",
    "Interview",
    "Offer",
    "Rejected",
    "On Hold",
]

OUTREACH_STATUS_OPTIONS = [
    "Not Started",
    "Drafted",
    "Sent",
    "Replied",
    "Completed",
]

STOPWORDS = {
    "about",
    "across",
    "after",
    "also",
    "an",
    "and",
    "are",
    "but",
    "for",
    "from",
    "have",
    "help",
    "into",
    "that",
    "the",
    "their",
    "this",
    "with",
    "will",
    "your",
    "you",
    "role",
    "team",
    "teams",
    "work",
    "using",
    "experience",
    "years",
    "ability",
    "skills",
    "required",
    "preferred",
}

TARGET_PROFILE = {
    "AI enablement": ["ai", "enablement", "adoption", "implementation", "deployment"],
    "workflow improvement": ["workflow", "process", "automation", "efficiency", "operations"],
    "agentic AI/tools": ["agent", "llm", "copilot", "assistant", "tooling"],
    "business analysis": ["requirements", "analysis", "mapping", "discovery", "insights"],
    "stakeholder communication": ["stakeholder", "cross-functional", "communication", "present", "partner"],
    "process improvement": ["improve", "optimization", "streamline", "operational", "continuous improvement"],
    "digital transformation": ["digital", "transformation", "change", "adoption", "modernization"],
    "POCs/MVPs": ["prototype", "poc", "pilot", "mvp", "experiment"],
    "practical AI implementation": ["use case", "implementation", "internal tools", "business value", "execution"],
    "technical-business translation": ["translate", "business problems", "technical requirements", "bridge", "scoping"],
}

ANCHOR_PROJECTS = {
    "Communication Workflow Automation Project": [
        "email",
        "workflow",
        "follow-up",
        "communication",
        "automation",
        "internal tools",
        "task extraction",
        "response drafting",
    ],
    "Operational Analytics Project": [
        "manufacturing",
        "quality",
        "sensor",
        "forecasting",
        "prediction",
        "production",
        "industrial",
        "operations",
    ],
    "Personal Productivity Workflow Tool": [
        "workflow",
        "internal tools",
        "job",
        "tracking",
        "prioritization",
        "outreach",
        "automation",
        "agentic",
        "prototype",
    ],
    "Stakeholder Operations Experience": [
        "stakeholder",
        "crm",
        "operations",
        "database",
        "coordination",
        "process",
        "communications",
        "execution",
    ],
    "Regulated Process Experience": [
        "government",
        "policy",
        "public sector",
        "legislative",
        "stakeholder",
        "process",
        "constituent",
        "coordination",
    ],
    "AI And Innovation Education": [
        "innovation",
        "strategy",
        "digital transformation",
        "adoption",
        "change",
        "business",
        "ai",
        "implementation",
    ],
}

AI_KEYWORD_BANK = [
    "ai",
    "artificial intelligence",
    "llm",
    "agent",
    "automation",
    "machine learning",
    "workflow",
    "prompt",
    "copilot",
    "knowledge base",
]

BUSINESS_KEYWORD_BANK = [
    "process",
    "operations",
    "stakeholder",
    "requirements",
    "communication",
    "cross-functional",
    "business case",
    "implementation",
    "execution",
    "workflow",
]

RED_FLAG_PATTERNS = {
    "Pure engineering drift": [
        "pytorch",
        "tensorflow",
        "distributed systems",
        "compiler",
        "c++",
        "research scientist",
        "phd",
        "model training",
    ],
    "Pure sales drift": [
        "quota",
        "pipeline generation",
        "sales target",
        "account executive",
        "sdr",
        "business development representative",
    ],
    "Generic operations drift": [
        "calendar management",
        "administrative support",
        "data entry",
        "office management",
        "crm hygiene",
        "scheduling",
    ],
}


def to_iso_date(value: Any) -> str | None:
    if value in (None, "", "None"):
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        try:
            return datetime.strptime(value.strip(), "%Y-%m-%d").date().isoformat()
        except ValueError:
            return None
    return None


def format_date_or_dash(value: Any) -> str:
    iso_date = to_iso_date(value)
    return iso_date if iso_date else "-"


def safe_json_loads(raw_text: Any) -> Any:
    if raw_text in (None, ""):
        return None
    if isinstance(raw_text, (dict, list)):
        return raw_text

    text = str(raw_text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"```json\s*(\{.*?\}|\[.*?\])\s*```", text, flags=re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return None

    start = min([index for index in [text.find("{"), text.find("[")] if index != -1], default=-1)
    if start == -1:
        return None

    trimmed = text[start:]
    for end in range(len(trimmed), 0, -1):
        chunk = trimmed[:end]
        try:
            return json.loads(chunk)
        except json.JSONDecodeError:
            continue
    return None


def normalize_list(values: Any, limit: int = 10) -> list[str]:
    if not values:
        return []
    if isinstance(values, str):
        values = [values]

    cleaned: list[str] = []
    seen = set()
    for item in values:
        if item is None:
            continue
        text = str(item).strip(" -•\n\t")
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(text)
        if len(cleaned) >= limit:
            break
    return cleaned


def top_terms(text: str, limit: int = 10) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9\-/+]{2,}", text.lower())
    counts = Counter(word for word in words if word not in STOPWORDS)
    return [word for word, _count in counts.most_common(limit)]


def find_keyword_matches(text: str, bank: list[str]) -> list[str]:
    lowered = text.lower()
    matches = [term for term in bank if term.lower() in lowered]
    return normalize_list(matches)


def classify_fit_score(score: int | float | None) -> str:
    if score is None:
        return "Not Scored"
    if score >= 8:
        return "Strong Fit"
    if score >= 5:
        return "Moderate Fit"
    return "Weak Fit"


def compute_priority(
    fit_score: int | float | None,
    follow_up_date: Any,
    outreach_status: str | None,
    status: str | None,
    manual_priority: str | None = None,
) -> str:
    if status == "Rejected":
        return "Low"

    today = date.today()
    follow_up = to_iso_date(follow_up_date)
    follow_up_dt = datetime.strptime(follow_up, "%Y-%m-%d").date() if follow_up else None
    outreach_status = outreach_status or "Not Started"

    if follow_up_dt and follow_up_dt < today:
        return "High"
    if follow_up_dt and follow_up_dt == today:
        return "High"
    if manual_priority in {"High", "Medium", "Low"}:
        return manual_priority
    if fit_score is not None and float(fit_score) >= 8 and outreach_status not in {"Sent", "Replied", "Completed"}:
        return "High"
    if fit_score is not None and float(fit_score) >= 6:
        return "Medium"
    return "Low"


def compute_next_action(row: pd.Series) -> str:
    if row.get("status") == "Rejected":
        return "Close out tracking"
    if row.get("is_overdue"):
        return "Send overdue follow-up"
    if row.get("is_due_today"):
        return "Send follow-up today"
    if row.get("needs_outreach"):
        return "Start outreach"
    if row.get("status") == "Saved":
        return "Review and apply"
    if row.get("status") == "Applied":
        return "Monitor and prepare follow-up"
    if row.get("status") == "Interview":
        return "Prepare interview follow-up"
    return "Keep tracking"


def build_tracker_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    tracker = df.copy()
    today_ts = pd.Timestamp(date.today())
    tracker["follow_up_date"] = tracker["follow_up_date"].apply(to_iso_date)
    tracker["follow_up_ts"] = pd.to_datetime(tracker["follow_up_date"], errors="coerce").dt.normalize()
    tracker["outreach_status"] = tracker["outreach_status"].fillna("Not Started")
    tracker["fit_category"] = tracker["fit_category"].fillna("Not Scored")
    tracker["is_due_today"] = tracker["follow_up_ts"] == today_ts
    tracker["is_overdue"] = tracker["follow_up_ts"].notna() & (tracker["follow_up_ts"] < today_ts)
    tracker["needs_outreach"] = (
        tracker["fit_score"].fillna(0).astype(float).ge(8)
        & ~tracker["outreach_status"].isin(["Sent", "Replied", "Completed"])
    )
    tracker["computed_priority"] = tracker.apply(
        lambda row: compute_priority(
            fit_score=row.get("fit_score"),
            follow_up_date=row.get("follow_up_date"),
            outreach_status=row.get("outreach_status"),
            status=row.get("status"),
            manual_priority=row.get("priority"),
        ),
        axis=1,
    )
    tracker["next_action"] = tracker.apply(compute_next_action, axis=1)
    return tracker
