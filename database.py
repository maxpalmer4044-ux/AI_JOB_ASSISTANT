from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.utils import OUTREACH_STATUS_OPTIONS, STATUS_OPTIONS, to_iso_date


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
DB_PATH = DATA_DIR / "jobs.db"


def clean_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def get_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS job_applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company TEXT NOT NULL,
                job_title TEXT NOT NULL,
                location TEXT,
                job_description TEXT,
                status TEXT NOT NULL DEFAULT 'Saved',
                fit_score REAL,
                fit_category TEXT,
                priority TEXT,
                application_date TEXT,
                follow_up_date TEXT,
                contact_name TEXT,
                referral_source TEXT,
                outreach_status TEXT DEFAULT 'Not Started',
                notes TEXT,
                analysis_json TEXT,
                outreach_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )


def seed_from_csv_if_empty(csv_path: Path) -> None:
    with get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) AS count FROM job_applications").fetchone()
        if row["count"] > 0:
            return

    seed_df = pd.read_csv(csv_path)
    for _, row in seed_df.iterrows():
        add_job(
            {
                "company": row.get("company", ""),
                "job_title": row.get("job_title", ""),
                "location": row.get("location", ""),
                "job_description": row.get("job_description", ""),
                "status": row.get("status", STATUS_OPTIONS[0]),
                "fit_score": row.get("fit_score") if pd.notna(row.get("fit_score")) else None,
                "fit_category": row.get("fit_category") if pd.notna(row.get("fit_category")) else None,
                "priority": row.get("priority", "Medium"),
                "application_date": to_iso_date(row.get("application_date")),
                "follow_up_date": to_iso_date(row.get("follow_up_date")),
                "contact_name": row.get("contact_name", ""),
                "referral_source": row.get("referral_source", ""),
                "outreach_status": row.get("outreach_status", OUTREACH_STATUS_OPTIONS[0]),
                "notes": row.get("notes", ""),
            },
            allow_duplicate=True,
        )


def is_duplicate_job(company: str, job_title: str, location: str | None = None) -> bool:
    query = """
        SELECT 1
        FROM job_applications
        WHERE LOWER(company) = LOWER(?)
          AND LOWER(job_title) = LOWER(?)
          AND LOWER(COALESCE(location, '')) = LOWER(COALESCE(?, ''))
        LIMIT 1
    """
    with get_connection() as conn:
        row = conn.execute(query, (company.strip(), job_title.strip(), (location or "").strip())).fetchone()
    return row is not None


def add_job(job: dict[str, Any], allow_duplicate: bool = False) -> tuple[bool, str, int | None]:
    company = clean_text(job.get("company"))
    job_title = clean_text(job.get("job_title"))
    location = clean_text(job.get("location"))

    if not allow_duplicate and is_duplicate_job(company, job_title, location):
        return False, "A matching company + job title already exists. Tick the duplicate box if you want to save it anyway.", None

    now = datetime.utcnow().isoformat(timespec="seconds")
    payload = {
        "company": company,
        "job_title": job_title,
        "location": location,
        "job_description": clean_text(job.get("job_description")),
        "status": job.get("status") or STATUS_OPTIONS[0],
        "fit_score": job.get("fit_score"),
        "fit_category": job.get("fit_category"),
        "priority": job.get("priority") or "Medium",
        "application_date": to_iso_date(job.get("application_date")),
        "follow_up_date": to_iso_date(job.get("follow_up_date")),
        "contact_name": clean_text(job.get("contact_name")),
        "referral_source": clean_text(job.get("referral_source")),
        "outreach_status": job.get("outreach_status") or OUTREACH_STATUS_OPTIONS[0],
        "notes": clean_text(job.get("notes")),
        "analysis_json": json.dumps(job.get("analysis_json")) if job.get("analysis_json") else None,
        "outreach_json": json.dumps(job.get("outreach_json")) if job.get("outreach_json") else None,
        "created_at": now,
        "updated_at": now,
    }

    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO job_applications (
                company, job_title, location, job_description, status, fit_score, fit_category,
                priority, application_date, follow_up_date, contact_name, referral_source,
                outreach_status, notes, analysis_json, outreach_json, created_at, updated_at
            ) VALUES (
                :company, :job_title, :location, :job_description, :status, :fit_score, :fit_category,
                :priority, :application_date, :follow_up_date, :contact_name, :referral_source,
                :outreach_status, :notes, :analysis_json, :outreach_json, :created_at, :updated_at
            )
            """,
            payload,
        )
        job_id = cursor.lastrowid

    return True, "Saved.", job_id


def fetch_jobs() -> pd.DataFrame:
    with get_connection() as conn:
        df = pd.read_sql_query(
            "SELECT * FROM job_applications ORDER BY updated_at DESC, id DESC",
            conn,
        )
    return df


def delete_all_jobs() -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM job_applications")


def delete_job(job_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM job_applications WHERE id = ?", (job_id,))


def get_job_by_id(job_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM job_applications WHERE id = ?", (job_id,)).fetchone()
    return dict(row) if row else None


def update_job_fields(job_id: int, updates: dict[str, Any]) -> None:
    if not updates:
        return

    text_fields = {
        "company",
        "job_title",
        "location",
        "job_description",
        "status",
        "fit_category",
        "priority",
        "contact_name",
        "referral_source",
        "outreach_status",
        "notes",
    }

    normalized = {}
    for key, value in updates.items():
        if key in {"application_date", "follow_up_date"}:
            normalized[key] = to_iso_date(value)
        elif key in {"analysis_json", "outreach_json"} and value is not None and not isinstance(value, str):
            normalized[key] = json.dumps(value)
        elif key in text_fields:
            normalized[key] = clean_text(value)
        else:
            normalized[key] = value
    normalized["updated_at"] = datetime.utcnow().isoformat(timespec="seconds")

    set_clause = ", ".join(f"{column} = :{column}" for column in normalized)
    normalized["id"] = job_id

    with get_connection() as conn:
        conn.execute(
            f"UPDATE job_applications SET {set_clause} WHERE id = :id",
            normalized,
        )


def update_job_analysis(
    job_id: int,
    fit_score: float,
    fit_category: str,
    priority: str,
    analysis_payload: dict[str, Any],
) -> None:
    update_job_fields(
        job_id,
        {
            "fit_score": fit_score,
            "fit_category": fit_category,
            "priority": priority,
            "analysis_json": analysis_payload,
        },
    )


def update_job_outreach(
    job_id: int,
    outreach_status: str | None = None,
    outreach_payload: dict[str, Any] | None = None,
) -> None:
    updates: dict[str, Any] = {}
    if outreach_status:
        updates["outreach_status"] = outreach_status
    if outreach_payload is not None:
        updates["outreach_json"] = outreach_payload
    update_job_fields(job_id, updates)
