from __future__ import annotations

from pathlib import Path

from src.scorer import MALCOLM_JOB_EVALUATION_CONTEXT


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
PROFILE_CONTEXT_PATH = DATA_DIR / "profile_context.md"


def load_profile_context() -> str:
    if PROFILE_CONTEXT_PATH.exists():
        return PROFILE_CONTEXT_PATH.read_text(encoding="utf-8").strip()
    return MALCOLM_JOB_EVALUATION_CONTEXT


def save_profile_context(context: str) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PROFILE_CONTEXT_PATH.write_text(context.strip(), encoding="utf-8")


def reset_profile_context() -> None:
    if PROFILE_CONTEXT_PATH.exists():
        PROFILE_CONTEXT_PATH.unlink()
