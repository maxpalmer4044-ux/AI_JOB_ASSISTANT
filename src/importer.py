from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.database import add_job, delete_all_jobs, fetch_jobs
from src.utils import compute_priority, to_iso_date


DEFAULT_TRACKER_PATH = Path.home() / "OneDrive" / "Documents" / "Palmer Job application manager.xlsx"
SAMPLE_ROLE_KEYS = {
    ("OpusClip", "AI Implementation Intern"),
    ("Distyl", "Deployment Strategist"),
    ("Generic CRM Corp", "Operations Coordinator"),
}

ROW_INDEX = {
    "company": 3,
    "outreach_flag": 4,
    "outreach_score": 5,
    "website": 6,
    "location": 7,
    "job_title": 9,
    "jd_link": 10,
    "salary": 11,
    "status": 12,
    "application_date": 13,
    "cover_letter": 14,
    "giulia_flag": 15,
    "interview_date": 17,
    "interview_time": 18,
    "contact_name": 20,
    "contact_email": 21,
    "contact_phone": 22,
    "thank_you_sent": 32,
    "follow_up_date": 33,
}


def clean_excel_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    if text.lower() in {"nan", "nat", "none", "tbd"}:
        return ""
    return text


def clean_excel_date(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    return to_iso_date(value)


def normalize_status(raw_status: Any) -> str:
    status = clean_excel_text(raw_status).lower()
    if "reject" in status:
        return "Rejected"
    if "offer" in status:
        return "Offer"
    if "interview" in status:
        return "Interview"
    if "network" in status:
        return "Networking"
    if any(token in status for token in ["apply", "submitted", "submission", "sent"]):
        return "Applied"
    if status:
        return "Saved"
    return "Saved"


def normalize_outreach(flag: Any, score: Any) -> str:
    flag_text = clean_excel_text(flag).lower()
    if flag_text == "y":
        return "Sent"
    if flag_text == "?":
        return "Drafted"
    if flag_text == "n":
        return "Not Started"
    if score is not None and not pd.isna(score):
        return "Drafted"
    return "Not Started"


def compose_notes(record: dict[str, Any]) -> str:
    note_parts = []
    if record.get("jd_link"):
        note_parts.append(f"JD link: {record['jd_link']}")
    if record.get("website"):
        note_parts.append(f"Company site: {record['website']}")
    if record.get("salary"):
        note_parts.append(f"Salary/rate: {record['salary']}")
    if record.get("cover_letter"):
        note_parts.append(f"Cover letter attached: {record['cover_letter']}")
    if record.get("giulia_flag"):
        note_parts.append(f"Giulia notified: {record['giulia_flag']}")
    if record.get("contact_email"):
        note_parts.append(f"Contact email: {record['contact_email']}")
    if record.get("contact_phone"):
        note_parts.append(f"Contact phone: {record['contact_phone']}")
    if record.get("interview_date"):
        interview_line = f"Interview date: {record['interview_date']}"
        if record.get("interview_time"):
            interview_line += f" at {record['interview_time']}"
        note_parts.append(interview_line)
    if record.get("thank_you_sent"):
        note_parts.append(f"Thank-you note sent: {record['thank_you_sent']}")
    return "\n".join(note_parts)


def _row_value(df: pd.DataFrame, row_index: int, column_index: int) -> Any:
    if row_index >= len(df.index) or column_index >= len(df.columns):
        return None
    return df.iat[row_index, column_index]


def parse_tracker_workbook(path: Path) -> list[dict[str, Any]]:
    df = pd.read_excel(path, sheet_name="Job Application Tracker", header=None)
    records: list[dict[str, Any]] = []

    for col in range(2, len(df.columns)):
        company = clean_excel_text(_row_value(df, ROW_INDEX["company"], col))
        job_title = clean_excel_text(_row_value(df, ROW_INDEX["job_title"], col))
        if not company and not job_title:
            continue

        raw_status = _row_value(df, ROW_INDEX["status"], col)
        outreach_flag = _row_value(df, ROW_INDEX["outreach_flag"], col)
        outreach_score = _row_value(df, ROW_INDEX["outreach_score"], col)
        application_date = clean_excel_date(_row_value(df, ROW_INDEX["application_date"], col))
        follow_up_date = clean_excel_date(_row_value(df, ROW_INDEX["follow_up_date"], col))
        outreach_status = normalize_outreach(outreach_flag, outreach_score)
        status = normalize_status(raw_status)

        details = {
            "website": clean_excel_text(_row_value(df, ROW_INDEX["website"], col)),
            "jd_link": clean_excel_text(_row_value(df, ROW_INDEX["jd_link"], col)),
            "salary": clean_excel_text(_row_value(df, ROW_INDEX["salary"], col)),
            "cover_letter": clean_excel_text(_row_value(df, ROW_INDEX["cover_letter"], col)),
            "giulia_flag": clean_excel_text(_row_value(df, ROW_INDEX["giulia_flag"], col)),
            "contact_email": clean_excel_text(_row_value(df, ROW_INDEX["contact_email"], col)),
            "contact_phone": clean_excel_text(_row_value(df, ROW_INDEX["contact_phone"], col)),
            "interview_date": clean_excel_date(_row_value(df, ROW_INDEX["interview_date"], col)),
            "interview_time": clean_excel_text(_row_value(df, ROW_INDEX["interview_time"], col)),
            "thank_you_sent": clean_excel_text(_row_value(df, ROW_INDEX["thank_you_sent"], col)),
        }

        record = {
            "company": company,
            "job_title": job_title or "Unknown Title",
            "location": clean_excel_text(_row_value(df, ROW_INDEX["location"], col)),
            "job_description": "",
            "status": status,
            "fit_score": None,
            "fit_category": None,
            "priority": compute_priority(
                fit_score=None,
                follow_up_date=follow_up_date,
                outreach_status=outreach_status,
                status=status,
            ),
            "application_date": application_date,
            "follow_up_date": follow_up_date,
            "contact_name": clean_excel_text(_row_value(df, ROW_INDEX["contact_name"], col)),
            "referral_source": "Imported from Excel tracker",
            "outreach_status": outreach_status,
            "notes": compose_notes(details),
        }
        records.append(record)

    return records


def db_contains_only_sample_rows() -> bool:
    jobs = fetch_jobs()
    if jobs.empty:
        return False
    role_keys = {(str(row["company"]), str(row["job_title"])) for _, row in jobs.iterrows()}
    return role_keys.issubset(SAMPLE_ROLE_KEYS)


def import_tracker_into_database(
    path: Path,
    replace_sample_seed: bool = True,
) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Tracker file not found: {path}")

    if replace_sample_seed and db_contains_only_sample_rows():
        delete_all_jobs()

    records = parse_tracker_workbook(path)
    imported = 0
    skipped = 0

    for record in records:
        ok, _message, _job_id = add_job(record, allow_duplicate=False)
        if ok:
            imported += 1
        else:
            skipped += 1

    return {
        "path": str(path),
        "parsed_records": len(records),
        "imported": imported,
        "skipped": skipped,
    }
