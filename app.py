from __future__ import annotations

import base64
import os
import re
from functools import lru_cache
from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st

from src.database import (
    add_job,
    delete_job,
    fetch_jobs,
    init_db,
    seed_from_csv_if_empty,
    update_job_analysis,
    update_job_fields,
    update_job_outreach,
)
from src.importer import DEFAULT_TRACKER_PATH, import_tracker_into_database
from src.job_fetcher import fetch_job_posting
from src.llm import describe_llm_status
from src.outreach import generate_outreach_drafts
from src.parser import parse_job_description
from src.scorer import recommend_resume_emphasis, score_role_fit
from src.utils import (
    OUTREACH_STATUS_OPTIONS,
    STATUS_OPTIONS,
    build_tracker_dataframe,
    compute_priority,
    format_date_or_dash,
    safe_json_loads,
    to_iso_date,
)


ROOT_DIR = Path(__file__).resolve().parent
SAMPLE_CSV = ROOT_DIR / "data" / "sample_jobs.csv"
HOME_BG_IMAGE = ROOT_DIR / "assets" / "city_of_tomorrow_hero.png"
HOME_FEATURE_IMAGES = {
    "add_job": ROOT_DIR / "assets" / "add_job_feature.png",
    "analyze_jd": ROOT_DIR / "assets" / "analyze_jd_feature.png",
    "dashboard": ROOT_DIR / "assets" / "dashboard_feature.png",
    "outreach": ROOT_DIR / "assets" / "outreach_feature.png",
}


st.set_page_config(
    page_title="AI Job Search Workflow Agent",
    page_icon=":briefcase:",
    layout="wide",
)


def apply_retro_theme() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Fjalla+One&family=Manrope:wght@400;500;700;800&family=Monoton&display=swap');

        :root {
            --retro-cream: #fff7ea;
            --retro-vanilla: #f7ead2;
            --retro-teal: #6cc6c1;
            --retro-teal-deep: #1d5863;
            --retro-ink: #17343d;
            --retro-coral: #ef7d62;
            --retro-sun: #f2bf65;
            --retro-chrome: #cad8d9;
            --retro-rose: #d85f77;
            --retro-night: #18353f;
            --retro-shadow: rgba(25, 54, 64, 0.18);
            --retro-glow: rgba(255, 255, 255, 0.7);
        }

        html, body, [class*="css"] {
            font-family: "Manrope", "Trebuchet MS", sans-serif;
            color: var(--retro-ink);
        }

        div[data-testid="stAppViewContainer"] {
            background:
                radial-gradient(circle at 8% 4%, rgba(242, 191, 101, 0.48), transparent 18%),
                radial-gradient(circle at 92% 8%, rgba(108, 198, 193, 0.42), transparent 20%),
                linear-gradient(180deg, rgba(255, 249, 239, 0.98), rgba(220, 242, 240, 0.9)),
                repeating-linear-gradient(
                    120deg,
                    rgba(255, 255, 255, 0.08) 0,
                    rgba(255, 255, 255, 0.08) 2px,
                    transparent 1px,
                    transparent 74px
                ),
                repeating-linear-gradient(
                    0deg,
                    rgba(255, 255, 255, 0.08) 0,
                    rgba(255, 255, 255, 0.08) 1px,
                    transparent 1px,
                    transparent 94px
                );
        }

        div[data-testid="stHeader"] {
            background: rgba(255, 255, 255, 0);
        }

        section[data-testid="stSidebar"] {
            background:
                linear-gradient(180deg, rgba(25, 79, 90, 0.97), rgba(16, 53, 61, 0.98)),
                linear-gradient(135deg, rgba(255, 255, 255, 0.05), rgba(255, 255, 255, 0));
            border-right: 2px solid rgba(255, 255, 255, 0.15);
        }

        section[data-testid="stSidebar"] * {
            color: #f7f1e4;
        }

        section[data-testid="stSidebar"] .stSelectbox label,
        section[data-testid="stSidebar"] .stMarkdown,
        section[data-testid="stSidebar"] .stCaption {
            color: #f7f1e4;
        }

        .block-container {
            padding-top: 2.35rem;
            padding-bottom: 3rem;
        }

        .retro-hero {
            position: relative;
            overflow: hidden;
            margin: 0 0 1.4rem 0;
            min-height: 30rem;
            padding: 2.35rem 2.25rem 2.45rem;
            border-radius: 34px;
            border: 3px solid rgba(255, 255, 255, 0.58);
            background:
                linear-gradient(90deg, rgba(10, 27, 33, 0.95) 0%, rgba(14, 34, 41, 0.88) 38%, rgba(17, 52, 61, 0.34) 62%, rgba(17, 52, 61, 0.08) 100%);
            box-shadow:
                0 26px 54px var(--retro-shadow),
                inset 0 1px 0 rgba(255, 255, 255, 0.7),
                inset 0 -18px 32px rgba(255, 255, 255, 0.12),
                inset 0 0 0 8px rgba(255, 255, 255, 0.12);
        }

        .retro-hero::before {
            content: "";
            position: absolute;
            inset: 0;
            background:
                linear-gradient(90deg, rgba(9, 24, 29, 0.72) 0%, rgba(9, 24, 29, 0.28) 42%, rgba(9, 24, 29, 0.02) 72%, rgba(9, 24, 29, 0) 100%),
                radial-gradient(circle at 74% 22%, rgba(249, 181, 76, 0.16), transparent 18%),
                radial-gradient(circle at 18% 14%, rgba(255, 255, 255, 0.12), transparent 16%);
        }

        .retro-hero::after {
            content: "";
            position: absolute;
            inset: 0;
            background:
                linear-gradient(180deg, rgba(248, 187, 87, 0.08), transparent 26%),
                linear-gradient(0deg, rgba(12, 22, 26, 0.16), transparent 24%);
        }

        .retro-hero-grid {
            position: absolute;
            inset: 0;
            background:
                linear-gradient(transparent 0 78%, rgba(255,255,255,0.08) 78% 80%, transparent 80%),
                repeating-linear-gradient(
                    90deg,
                    rgba(255,255,255,0.04) 0,
                    rgba(255,255,255,0.04) 2px,
                    transparent 2px,
                    transparent 90px
                );
            opacity: 0.32;
            pointer-events: none;
        }

        .retro-hero-content {
            position: relative;
            z-index: 2;
            max-width: 35rem;
        }

        .retro-hero-content,
        .retro-hero-content *,
        .home-feature-chip,
        .home-feature-chip * {
            color: #fff8ee !important;
            -webkit-text-fill-color: #fff8ee !important;
        }

        div[data-testid="stAppViewContainer"] .retro-hero .retro-hero-content h1,
        div[data-testid="stAppViewContainer"] .retro-hero .retro-hero-content p,
        div[data-testid="stAppViewContainer"] .retro-hero .retro-badges span,
        div[data-testid="stAppViewContainer"] .retro-hero .retro-kicker,
        div[data-testid="stAppViewContainer"] .retro-hero .retro-hero-content,
        div[data-testid="stAppViewContainer"] .retro-hero .retro-hero-content * {
            color: #fff8ee !important;
            -webkit-text-fill-color: #fff8ee !important;
        }

        .retro-orbit {
            position: absolute;
            right: 8%;
            top: 18%;
            width: 210px;
            height: 110px;
            border: 2px solid rgba(255, 255, 255, 0.38);
            border-radius: 50%;
            transform: rotate(-22deg);
            pointer-events: none;
        }

        .retro-orbit::before,
        .retro-orbit::after {
            content: "";
            position: absolute;
            inset: 0;
            border: 2px solid rgba(255, 255, 255, 0.28);
            border-radius: 50%;
        }

        .retro-orbit::before {
            transform: rotate(58deg);
        }

        .retro-orbit::after {
            transform: rotate(-58deg);
        }

        .retro-kicker,
        .section-kicker {
            display: inline-block;
            margin-bottom: 0.45rem;
            font-size: 0.8rem;
            font-weight: 800;
            letter-spacing: 0.22rem;
            text-transform: uppercase;
        }

        .retro-kicker {
            color: #fff4d2;
            padding: 0.4rem 0.8rem 0.32rem;
            border-radius: 999px;
            border: 1px solid rgba(255,255,255,0.36);
            background: rgba(255, 255, 255, 0.08);
        }

        .retro-hero h1 {
            margin: 0;
            max-width: 13ch;
            font-family: "Fjalla One", Impact, sans-serif;
            font-size: clamp(3rem, 5.6vw, 5.1rem);
            line-height: 0.96;
            letter-spacing: 0.06rem;
            text-transform: uppercase;
            color: #fff8ee;
            text-shadow:
                0 2px 0 rgba(10, 27, 33, 0.34),
                0 16px 32px rgba(0, 0, 0, 0.22);
        }

        .retro-hero p {
            max-width: 42rem;
            margin: 0.95rem 0 0;
            font-size: 1.08rem;
            line-height: 1.65;
            color: rgba(255, 248, 235, 0.98);
        }

        .retro-badges {
            display: flex;
            gap: 0.7rem;
            flex-wrap: wrap;
            margin-top: 1.2rem;
        }

        .retro-badges span {
            padding: 0.55rem 0.9rem;
            border-radius: 999px;
            border: 1px solid rgba(255, 255, 255, 0.42);
            background: linear-gradient(180deg, rgba(255, 255, 255, 0.18), rgba(255,255,255,0.08));
            color: #fff8ea;
            font-size: 0.85rem;
            font-weight: 700;
            backdrop-filter: blur(6px);
            box-shadow: inset 0 1px 0 rgba(255,255,255,0.4);
        }

        .section-shell {
            position: relative;
            margin: 0.45rem 0 1rem;
            padding: 1.15rem 1.2rem 0.95rem;
            border-radius: 24px;
            background:
                linear-gradient(180deg, rgba(255, 252, 245, 0.88), rgba(246, 236, 214, 0.82)),
                repeating-linear-gradient(
                    90deg,
                    rgba(255,255,255,0.12) 0,
                    rgba(255,255,255,0.12) 1px,
                    transparent 1px,
                    transparent 70px
                );
            border: 1px solid rgba(29, 88, 99, 0.14);
            box-shadow:
                0 16px 36px rgba(28, 65, 72, 0.08),
                inset 0 4px 0 rgba(255,255,255,0.52);
        }

        .section-shell::before {
            content: "";
            position: absolute;
            left: 1rem;
            right: 1rem;
            top: 0.72rem;
            height: 6px;
            border-radius: 999px;
            background: linear-gradient(90deg, rgba(239, 125, 98, 0.86), rgba(108, 198, 193, 0.86));
        }

        .section-kicker {
            color: var(--retro-coral);
        }

        .section-shell h2 {
            margin: 0;
            font-family: "Fjalla One", Impact, sans-serif;
            font-size: 1.95rem;
            letter-spacing: 0.04rem;
            text-transform: uppercase;
            color: var(--retro-teal-deep);
        }

        .section-shell p {
            margin: 0.45rem 0 0;
            color: rgba(23, 52, 61, 0.82);
            line-height: 1.55;
        }

        .section-copy {
            min-width: 0;
            max-width: 56rem;
        }

        .retro-panorama {
            position: relative;
            overflow: hidden;
            margin: 0.2rem 0 1rem;
            min-height: 235px;
            border-radius: 30px;
            border: 1px solid rgba(29, 88, 99, 0.16);
            background:
                linear-gradient(180deg, rgba(255, 251, 244, 0.94), rgba(232, 245, 243, 0.88));
            box-shadow:
                0 18px 38px rgba(28, 65, 72, 0.08),
                inset 0 1px 0 rgba(255,255,255,0.74);
        }

        .retro-panorama svg {
            width: 100%;
            height: 100%;
            min-height: 235px;
            display: block;
            filter: saturate(0.9) contrast(0.96);
        }

        .retro-panorama-copy {
            position: absolute;
            left: 1.25rem;
            bottom: 1.15rem;
            z-index: 2;
            max-width: 24rem;
            padding: 0.9rem 1rem;
            border-radius: 20px;
            background: rgba(255, 249, 239, 0.84);
            border: 1px solid rgba(29, 88, 99, 0.12);
            backdrop-filter: blur(8px);
            box-shadow: 0 10px 22px rgba(28, 65, 72, 0.08);
        }

        .retro-panorama-copy strong {
            display: block;
            margin-bottom: 0.18rem;
            font-family: "Fjalla One", Impact, sans-serif;
            font-size: 1rem;
            letter-spacing: 0.05rem;
            text-transform: uppercase;
            color: var(--retro-teal-deep);
        }

        .retro-panorama-copy span {
            color: rgba(23, 52, 61, 0.82);
            line-height: 1.45;
        }

        .retro-mural {
            margin: 0.3rem 0 1.2rem;
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 1rem;
        }

        .retro-mural-card {
            position: relative;
            overflow: hidden;
            min-height: 178px;
            padding: 0.8rem;
            border-radius: 28px;
            border: 1px solid rgba(29, 88, 99, 0.16);
            background:
                linear-gradient(180deg, rgba(255, 251, 244, 0.94), rgba(235, 245, 244, 0.92));
            box-shadow:
                0 16px 34px rgba(28, 65, 72, 0.08),
                inset 0 1px 0 rgba(255,255,255,0.7);
        }

        .retro-mural-card strong {
            position: absolute;
            left: 1rem;
            bottom: 1rem;
            z-index: 2;
            padding: 0.34rem 0.64rem;
            border-radius: 10px;
            background: rgba(255, 248, 235, 0.8);
            border: 1px solid rgba(29, 88, 99, 0.1);
            font-family: "Fjalla One", Impact, sans-serif;
            font-size: 0.8rem;
            letter-spacing: 0.06rem;
            text-transform: uppercase;
            color: var(--retro-teal-deep);
        }

        .retro-mural-card svg {
            width: 100%;
            height: 100%;
            display: block;
            filter: saturate(0.9) contrast(0.97);
        }

        div[data-testid="stForm"],
        div[data-testid="stDataFrame"],
        div[data-testid="stExpander"],
        div[data-testid="metric-container"],
        .stAlert,
        .stTextArea textarea,
        .stTextInput input,
        .stSelectbox [data-baseweb="select"],
        .stDateInput input {
            border-radius: 22px;
        }

        div[data-testid="stForm"] {
            background:
                linear-gradient(180deg, rgba(255, 250, 241, 0.88), rgba(247, 239, 221, 0.82));
            border: 1px solid rgba(29, 88, 99, 0.16);
            box-shadow: 0 14px 30px rgba(28, 65, 72, 0.08);
            padding: 1rem 1rem 0.2rem;
        }

        div[data-testid="metric-container"] {
            background:
                linear-gradient(180deg, rgba(196, 228, 229, 0.96), rgba(255, 245, 225, 0.96));
            border: 1px solid rgba(29, 88, 99, 0.16);
            box-shadow:
                0 14px 26px rgba(28, 65, 72, 0.08),
                inset 0 1px 0 rgba(255, 255, 255, 0.85),
                inset 0 -6px 0 rgba(216, 95, 119, 0.08);
            padding: 0.9rem 1rem;
        }

        div[data-testid="stMetric"],
        div[data-testid="metric-container"] label,
        div[data-testid="metric-container"] [data-testid="stMetricLabel"],
        div[data-testid="metric-container"] [data-testid="stMetricLabel"] *,
        div[data-testid="metric-container"] [data-testid="stMetricValue"],
        div[data-testid="metric-container"] [data-testid="stMetricValue"] * {
            color: var(--retro-teal-deep) !important;
            -webkit-text-fill-color: var(--retro-teal-deep) !important;
            font-weight: 800;
            letter-spacing: 0.04rem;
            text-transform: uppercase;
        }

        div[data-testid="stMetric"] *,
        div[data-testid="metric-container"] [data-testid="stMetricValue"] {
            color: var(--retro-ink) !important;
            font-family: "Fjalla One", Impact, sans-serif;
            letter-spacing: 0.03rem;
        }

        div[data-testid="stAppViewContainer"] label,
        div[data-testid="stAppViewContainer"] label p,
        div[data-testid="stAppViewContainer"] label span,
        div[data-testid="stAppViewContainer"] [data-testid="stWidgetLabel"] *,
        div[data-testid="stAppViewContainer"] [data-testid="stWidgetLabel"],
        div[data-testid="stAppViewContainer"] [data-testid="stWidgetLabel"] p,
        div[data-testid="stAppViewContainer"] [data-testid="stWidgetLabel"] span,
        div[data-testid="stAppViewContainer"] [data-testid="stMarkdownContainer"] p,
        div[data-testid="stAppViewContainer"] [data-testid="stMarkdownContainer"] span,
        div[data-testid="stAppViewContainer"] [data-testid="stMarkdownContainer"] li,
        div[data-testid="stAppViewContainer"] [data-testid="stCaptionContainer"] p,
        div[data-testid="stAppViewContainer"] [data-testid="stCaptionContainer"] span,
        div[data-testid="stAppViewContainer"] [role="radiogroup"] label,
        div[data-testid="stAppViewContainer"] [role="radiogroup"] label p,
        div[data-testid="stAppViewContainer"] [role="radiogroup"] label span,
        div[data-testid="stAppViewContainer"] .stRadio *,
        div[data-testid="stAppViewContainer"] .stCheckbox *,
        div[data-testid="stAppViewContainer"] .stCaption,
        div[data-testid="stAppViewContainer"] .stSelectbox label,
        div[data-testid="stAppViewContainer"] .stTextInput label,
        div[data-testid="stAppViewContainer"] .stTextArea label,
        div[data-testid="stAppViewContainer"] .stDateInput label,
        div[data-testid="stAppViewContainer"] .stMarkdown,
        div[data-testid="stAppViewContainer"] .stMarkdown p,
        div[data-testid="stAppViewContainer"] .stMarkdown span {
            color: var(--retro-ink) !important;
            -webkit-text-fill-color: var(--retro-ink) !important;
            text-shadow: none !important;
        }

        [data-baseweb="tab-list"] {
            gap: 0.6rem;
            margin-top: 0.45rem;
            margin-bottom: 1.2rem;
            padding: 0.65rem 0.7rem;
            border-radius: 28px;
            background:
                linear-gradient(180deg, rgba(23, 52, 61, 0.98), rgba(15, 35, 41, 0.98));
            box-shadow:
                0 18px 30px rgba(16, 34, 40, 0.18),
                inset 0 1px 0 rgba(255,255,255,0.1);
        }

        [data-baseweb="tab"] {
            height: 3rem;
            padding: 0 1.15rem;
            border-radius: 999px;
            border: 1px solid rgba(29, 88, 99, 0.16);
            background: linear-gradient(180deg, rgba(255, 250, 241, 0.82), rgba(243, 232, 210, 0.92));
            color: var(--retro-teal-deep);
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.04rem;
            box-shadow:
                0 10px 24px rgba(28, 65, 72, 0.06),
                inset 0 1px 0 rgba(255,255,255,0.76);
        }

        [data-baseweb="tab"][aria-selected="true"] {
            background: linear-gradient(180deg, rgba(236, 106, 98, 0.98), rgba(210, 92, 79, 0.98));
            color: #fff9ef;
            border-color: rgba(184, 79, 68, 0.6);
            box-shadow:
                0 12px 22px rgba(182, 86, 64, 0.22),
                inset 0 1px 0 rgba(255,255,255,0.4);
        }

        .stButton > button,
        .stFormSubmitButton > button {
            border: 0;
            border-radius: 999px;
            padding: 0.7rem 1.25rem;
            font-weight: 800;
            letter-spacing: 0.04rem;
            text-transform: uppercase;
            color: #fff9ef;
            background: linear-gradient(180deg, #f58d72, #d85f77 52%, #db684d);
            box-shadow:
                0 12px 20px rgba(182, 86, 64, 0.24),
                inset 0 1px 0 rgba(255, 255, 255, 0.4);
        }

        .stButton > button:hover,
        .stFormSubmitButton > button:hover {
            transform: translateY(-1px);
            background: linear-gradient(180deg, #f9a083, #dd7387 52%, #dd6e52);
        }

        .stButton > button[kind="secondary"],
        .stButton > button[kind="tertiary"] {
            padding: 0.5rem 0.95rem;
            color: var(--retro-teal-deep);
            background: linear-gradient(180deg, rgba(255, 250, 241, 0.94), rgba(240, 232, 214, 0.94));
            border: 1px solid rgba(29, 88, 99, 0.18);
            box-shadow:
                0 8px 16px rgba(28, 65, 72, 0.08),
                inset 0 1px 0 rgba(255,255,255,0.75);
        }

        .stButton > button[kind="secondary"]:hover,
        .stButton > button[kind="tertiary"]:hover {
            background: linear-gradient(180deg, rgba(255, 252, 246, 0.98), rgba(242, 236, 221, 0.98));
        }

        .stTextInput input,
        .stTextArea textarea,
        .stDateInput input,
        .stSelectbox [data-baseweb="select"] > div,
        .stMultiSelect [data-baseweb="select"] > div {
            background: rgba(255, 251, 244, 0.92);
            border: 1px solid rgba(29, 88, 99, 0.14);
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.78);
            color: var(--retro-ink) !important;
            -webkit-text-fill-color: var(--retro-ink) !important;
            caret-color: var(--retro-ink);
        }

        input,
        textarea,
        select,
        option,
        button,
        [contenteditable="true"] {
            color: var(--retro-ink) !important;
            -webkit-text-fill-color: inherit !important;
        }

        [data-testid="stTextInput"] input,
        [data-testid="stTextArea"] textarea,
        [data-testid="stDateInputField"] input,
        [data-baseweb="base-input"] input,
        [data-baseweb="textarea"] textarea,
        [data-testid="stTextArea"] textarea *,
        [data-testid="stTextInput"] input *,
        .stTextArea textarea,
        .stTextInput input {
            color: var(--retro-ink) !important;
            -webkit-text-fill-color: var(--retro-ink) !important;
            opacity: 1 !important;
            caret-color: var(--retro-ink) !important;
            text-shadow: none !important;
        }

        [data-testid="stTextInput"] input:disabled,
        [data-testid="stTextArea"] textarea:disabled,
        [data-baseweb="base-input"] input:disabled,
        [data-baseweb="textarea"] textarea:disabled,
        [data-testid="stTextInput"] input[readonly],
        [data-testid="stTextArea"] textarea[readonly],
        [data-baseweb="base-input"] input[readonly],
        [data-baseweb="textarea"] textarea[readonly] {
            color: var(--retro-ink) !important;
            -webkit-text-fill-color: var(--retro-ink) !important;
            opacity: 1 !important;
        }

        input:-webkit-autofill,
        input:-webkit-autofill:hover,
        input:-webkit-autofill:focus,
        textarea:-webkit-autofill,
        textarea:-webkit-autofill:hover,
        textarea:-webkit-autofill:focus {
            -webkit-text-fill-color: var(--retro-ink) !important;
            box-shadow: 0 0 0px 1000px rgba(255, 251, 244, 0.96) inset !important;
            transition: background-color 9999s ease-in-out 0s;
        }

        .stTextInput input::placeholder,
        .stTextArea textarea::placeholder,
        .stDateInput input::placeholder {
            color: rgba(23, 52, 61, 0.62) !important;
            -webkit-text-fill-color: rgba(23, 52, 61, 0.62) !important;
        }

        .stSelectbox [data-baseweb="select"] span,
        .stMultiSelect [data-baseweb="select"] span,
        .stSelectbox [data-baseweb="select"] input,
        .stMultiSelect [data-baseweb="select"] input,
        .stSelectbox div[data-baseweb="select"] div,
        .stMultiSelect div[data-baseweb="select"] div {
            color: var(--retro-ink) !important;
            -webkit-text-fill-color: var(--retro-ink) !important;
        }

        .retro-table-shell {
            margin: 0.65rem 0 1rem;
            border-radius: 24px;
            overflow: hidden;
            border: 1px solid rgba(29, 88, 99, 0.16);
            background: linear-gradient(180deg, rgba(255, 250, 241, 0.92), rgba(244, 235, 214, 0.92));
            box-shadow:
                0 18px 34px rgba(28, 65, 72, 0.08),
                inset 0 1px 0 rgba(255,255,255,0.7);
        }

        .retro-table-shell table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.95rem;
        }

        .retro-table-scroll {
            overflow: auto;
        }

        .retro-table-shell thead th {
            padding: 0.95rem 0.9rem;
            text-align: left;
            font-family: "Fjalla One", Impact, sans-serif;
            letter-spacing: 0.05rem;
            text-transform: uppercase;
            color: #fff8ef;
            background: linear-gradient(180deg, #235962, #2b6870);
            border-bottom: 2px solid rgba(255,255,255,0.18);
            font-weight: 700;
            position: sticky;
            top: 0;
            z-index: 1;
        }

        .retro-table-shell tbody tr:nth-child(odd) {
            background: rgba(255, 249, 238, 0.92);
        }

        .retro-table-shell tbody tr:nth-child(even) {
            background: rgba(238, 248, 247, 0.76);
        }

        .retro-table-shell tbody tr:hover {
            background: rgba(242, 191, 101, 0.16);
        }

        .retro-table-shell td {
            padding: 0.82rem 0.9rem;
            border-bottom: 1px solid rgba(29, 88, 99, 0.1);
            color: var(--retro-ink);
            vertical-align: top;
            line-height: 1.4;
        }

        .retro-table-shell a,
        .retro-table-shell a:visited {
            color: var(--retro-teal-deep);
            font-weight: 800;
            text-decoration: none;
            border-bottom: 1px solid rgba(29, 88, 99, 0.28);
        }

        .retro-table-shell a:hover {
            color: var(--retro-coral);
            border-bottom-color: rgba(239, 125, 98, 0.36);
        }

        .retro-table-shell tbody tr:last-child td {
            border-bottom: none;
        }

        .retro-table-title {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            padding: 0.95rem 1rem 0.75rem;
            background: linear-gradient(180deg, rgba(255,255,255,0.46), rgba(255,255,255,0.16));
            border-bottom: 1px solid rgba(29, 88, 99, 0.12);
        }

        .retro-table-title strong {
            font-family: "Fjalla One", Impact, sans-serif;
            letter-spacing: 0.04rem;
            text-transform: uppercase;
            color: var(--retro-teal-deep);
            font-size: 1.02rem;
        }

        .retro-table-subtle {
            color: rgba(23, 52, 61, 0.7);
            font-size: 0.88rem;
            font-weight: 700;
        }

        .retro-badge {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            white-space: nowrap;
            padding: 0.38rem 0.72rem;
            border-radius: 999px;
            font-size: 0.78rem;
            font-weight: 800;
            letter-spacing: 0.03rem;
            text-transform: uppercase;
            border: 1px solid rgba(23,52,61,0.12);
            box-shadow: inset 0 1px 0 rgba(255,255,255,0.56);
        }

        .retro-badge.status-applied,
        .retro-badge.status-strong-fit,
        .retro-badge.status-primary-target,
        .retro-badge.status-strong-secondary,
        .retro-badge.status-high {
            background: linear-gradient(180deg, rgba(106, 202, 188, 0.95), rgba(72, 159, 145, 0.95));
            color: #103f46 !important;
        }

        .retro-badge.status-rejected,
        .retro-badge.status-weak-fit,
        .retro-badge.status-skip,
        .retro-badge.status-low {
            background: linear-gradient(180deg, rgba(242, 159, 140, 0.96), rgba(219, 104, 77, 0.95));
            color: #fff9ef !important;
        }

        .retro-badge.status-saved,
        .retro-badge.status-not-started,
        .retro-badge.status-moderate-fit,
        .retro-badge.status-controlled-effort,
        .retro-badge.status-medium {
            background: linear-gradient(180deg, rgba(255, 233, 176, 0.95), rgba(242, 191, 101, 0.96));
            color: #6f4d12 !important;
        }

        .retro-badge.status-drafted,
        .retro-badge.status-networking,
        .retro-badge.status-interview,
        .retro-badge.status-sent,
        .retro-badge.status-replied,
        .retro-badge.status-completed {
            background: linear-gradient(180deg, rgba(212, 218, 237, 0.95), rgba(173, 186, 218, 0.95));
            color: #274268 !important;
        }

        .retro-table-empty {
            padding: 1rem;
            color: rgba(23, 52, 61, 0.74);
        }

        .analysis-brief {
            margin: 1rem 0;
        }

        .analysis-hero {
            border-radius: 20px;
            padding: 0.9rem 1rem;
            margin: 0.55rem 0 0.75rem;
            background: linear-gradient(135deg, rgba(28, 84, 94, 0.96), rgba(13, 45, 53, 0.96));
            border: 1px solid rgba(255, 250, 241, 0.28);
            box-shadow: 0 18px 34px rgba(28, 65, 72, 0.13);
            color: #fffaf1;
        }

        .analysis-hero h3 {
            margin: 0.1rem 0 0.35rem;
            font-family: "Fjalla One", Impact, sans-serif;
            letter-spacing: 0.04rem;
            text-transform: uppercase;
            color: #fffaf1 !important;
            font-size: 1.38rem;
        }

        .analysis-hero p,
        .analysis-hero strong,
        .analysis-hero span,
        .analysis-hero div,
        .analysis-hero * {
            color: #fffaf1 !important;
            -webkit-text-fill-color: #fffaf1 !important;
        }

        div[data-testid="stAppViewContainer"] .analysis-hero,
        div[data-testid="stAppViewContainer"] .analysis-hero *,
        div[data-testid="stAppViewContainer"] .analysis-hero p,
        div[data-testid="stAppViewContainer"] .analysis-hero h1,
        div[data-testid="stAppViewContainer"] .analysis-hero h2,
        div[data-testid="stAppViewContainer"] .analysis-hero h3,
        div[data-testid="stAppViewContainer"] .analysis-hero h4,
        div[data-testid="stAppViewContainer"] .analysis-hero span,
        div[data-testid="stAppViewContainer"] .analysis-hero strong,
        div[data-testid="stAppViewContainer"] .analysis-hero div,
        div[data-testid="stAppViewContainer"] .retro-table-shell thead,
        div[data-testid="stAppViewContainer"] .retro-table-shell thead *,
        div[data-testid="stAppViewContainer"] .retro-table-shell thead th {
            color: #fffaf1 !important;
            -webkit-text-fill-color: #fffaf1 !important;
        }

        .analysis-pill-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.42rem;
            margin-top: 0.65rem;
        }

        .analysis-pill {
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            padding: 0.34rem 0.62rem;
            background: rgba(255, 250, 241, 0.16);
            border: 1px solid rgba(255, 250, 241, 0.42);
            color: #fffaf1 !important;
            font-weight: 800;
        }

        .analysis-card {
            height: 100%;
            border-radius: 18px;
            padding: 0.78rem 0.85rem;
            margin: 0.32rem 0 0.72rem;
            background: rgba(255, 250, 241, 0.88);
            border: 1px solid rgba(29, 88, 99, 0.16);
            box-shadow: inset 0 1px 0 rgba(255,255,255,0.7), 0 12px 24px rgba(28, 65, 72, 0.07);
        }

        .analysis-card h4 {
            margin: 0 0 0.45rem;
            font-family: "Fjalla One", Impact, sans-serif;
            letter-spacing: 0.04rem;
            text-transform: uppercase;
            color: var(--retro-teal-deep) !important;
            font-size: 1rem;
        }

        .analysis-card ul {
            margin: 0;
            padding-left: 1.15rem;
        }

        .analysis-card li {
            margin: 0.24rem 0;
            color: var(--retro-ink);
            line-height: 1.45;
        }

        .analysis-mini-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
            gap: 0.5rem;
            margin: 0.55rem 0 0.75rem;
        }

        .analysis-mini {
            border-radius: 16px;
            padding: 0.62rem 0.72rem;
            background: rgba(238, 248, 247, 0.78);
            border: 1px solid rgba(29, 88, 99, 0.13);
        }

        .analysis-mini span {
            display: block;
            font-size: 0.75rem;
            font-weight: 900;
            text-transform: uppercase;
            color: rgba(23, 52, 61, 0.68) !important;
        }

        .analysis-mini strong {
            color: var(--retro-ink);
            font-size: 1.15rem;
        }

        .stRadio > div {
            background: rgba(255, 250, 241, 0.72);
            border-radius: 18px;
            padding: 0.35rem 0.65rem;
            border: 1px solid rgba(29, 88, 99, 0.12);
        }

        .stAlert {
            border: 1px solid rgba(29, 88, 99, 0.1);
            box-shadow: 0 12px 20px rgba(28, 65, 72, 0.05);
        }

        .stMarkdown h3,
        .stMarkdown h4 {
            font-family: "Fjalla One", Impact, sans-serif;
            text-transform: uppercase;
            letter-spacing: 0.04rem;
            color: var(--retro-teal-deep);
        }

        .home-feature-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 1rem;
            margin-top: 1.1rem;
        }

        .home-feature-card {
            position: relative;
            overflow: hidden;
            min-height: 17rem;
            border-radius: 28px;
            border: 1px solid rgba(29, 88, 99, 0.16);
            background:
                linear-gradient(180deg, rgba(255, 251, 244, 0.94), rgba(235, 245, 244, 0.92));
            box-shadow:
                0 16px 34px rgba(28, 65, 72, 0.08),
                inset 0 1px 0 rgba(255,255,255,0.7);
        }

        .home-feature-art {
            height: 9.25rem;
            border-bottom: 1px solid rgba(29, 88, 99, 0.08);
            background: rgba(255,255,255,0.34);
            position: relative;
            overflow: hidden;
        }

        .home-feature-photo {
            width: 100%;
            height: 100%;
            background-size: cover;
            background-repeat: no-repeat;
            position: relative;
        }

        .home-feature-photo::before {
            content: "";
            position: absolute;
            inset: 0;
            background:
                linear-gradient(180deg, rgba(10, 26, 32, 0.08), rgba(10, 26, 32, 0.3)),
                radial-gradient(circle at 78% 20%, rgba(250, 188, 92, 0.2), transparent 18%);
        }

        .home-feature-photo::after {
            content: "";
            position: absolute;
            left: 0.9rem;
            right: 0.9rem;
            bottom: 0.75rem;
            height: 0.22rem;
            border-radius: 999px;
            background: linear-gradient(90deg, rgba(255, 247, 232, 0.12), rgba(255, 247, 232, 0.7), rgba(255, 247, 232, 0.12));
        }

        .home-feature-chip {
            position: absolute;
            left: 0.9rem;
            top: 0.8rem;
            z-index: 2;
            display: inline-flex;
            align-items: center;
            padding: 0.34rem 0.62rem;
            border-radius: 999px;
            border: 1px solid rgba(255,255,255,0.42);
            background: rgba(14, 34, 41, 0.42);
            color: #fff7ea;
            font-size: 0.72rem;
            font-weight: 800;
            letter-spacing: 0.08rem;
            text-transform: uppercase;
            backdrop-filter: blur(5px);
            color: #fff8ee !important;
            -webkit-text-fill-color: #fff8ee !important;
            text-shadow: none !important;
        }

        div[data-testid="stAppViewContainer"] .home-feature-art .home-feature-chip,
        div[data-testid="stAppViewContainer"] .home-feature-art .home-feature-chip *,
        div[data-testid="stAppViewContainer"] .home-feature-photo .home-feature-chip,
        div[data-testid="stAppViewContainer"] .home-feature-photo .home-feature-chip * {
            color: #fff8ee !important;
            -webkit-text-fill-color: #fff8ee !important;
            opacity: 1 !important;
        }

        .home-feature-copy {
            padding: 1rem 1rem 1.1rem;
        }

        .home-feature-copy strong {
            display: block;
            margin-bottom: 0.28rem;
            font-family: "Fjalla One", Impact, sans-serif;
            font-size: 1rem;
            letter-spacing: 0.05rem;
            text-transform: uppercase;
            color: var(--retro-teal-deep);
        }

        .home-feature-copy p {
            margin: 0;
            color: rgba(23, 52, 61, 0.78);
            line-height: 1.52;
            font-size: 0.93rem;
        }

        .home-credit {
            margin-top: 0.9rem;
            color: rgba(255, 246, 231, 0.86);
            font-size: 0.84rem;
            line-height: 1.45;
        }

        @media (max-width: 900px) {
            .retro-hero {
                padding: 1.5rem 1.35rem 1.6rem;
                min-height: 25rem;
            }

            .retro-hero h1 {
                max-width: none;
                font-size: clamp(2.25rem, 9vw, 3.4rem);
            }

            .section-shell h2 {
                font-size: 1.6rem;
            }

            .retro-panorama-copy {
                position: static;
                margin: 0.8rem;
            }

            .home-feature-grid {
                grid-template-columns: 1fr 1fr;
            }

            .retro-mural {
                grid-template-columns: 1fr 1fr;
            }
        }

        @media (max-width: 640px) {
            .home-feature-grid,
            .retro-mural {
                grid-template-columns: 1fr;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def initialize_app() -> None:
    init_db()
    if SAMPLE_CSV.exists():
        seed_from_csv_if_empty(SAMPLE_CSV)


@lru_cache(maxsize=8)
def image_data_uri(path: str) -> str:
    image_path = Path(path)
    suffix = image_path.suffix.lower()
    mime = "image/jpeg"
    if suffix == ".png":
        mime = "image/png"
    elif suffix == ".webp":
        mime = "image/webp"
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def render_hero(background_uri: str | None = None) -> None:
    hero_style = ""
    if background_uri:
        hero_style = (
            " style=\"background-image: "
            f"linear-gradient(90deg, rgba(14, 34, 41, 0.9) 0%, rgba(14, 34, 41, 0.76) 32%, rgba(14, 34, 41, 0.22) 56%, rgba(14, 34, 41, 0.02) 100%), "
            f"url('{background_uri}'); "
            "background-size: 100% 100%, contain; "
            "background-repeat: no-repeat, no-repeat; "
            "background-position: left top, right center; "
            "background-color: #17343d;\""
        )
    st.markdown(
        f"""
        <section class="retro-hero"{hero_style}>
            <div class="retro-hero-grid"></div>
            <div class="retro-orbit"></div>
            <div class="retro-hero-content">
                <div class="retro-kicker">Orbit Lounge Control Desk</div>
                <h1>Job Search Control Deck</h1>
                <p>
                    Keep your applications, role analysis, resume emphasis, and outreach notes in one sharp command
                    board so you can see which opportunities are worth the next move.
                </p>
                <div class="retro-badges">
                    <span>Application Log</span>
                    <span>Fit Scanner</span>
                    <span>Resume Angles</span>
                    <span>Outreach Drafts</span>
                </div>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def section_art_svg(kind: str) -> str:
    art_map = {
        "intake": """
        <svg viewBox="0 0 220 120" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <linearGradient id="skyA" x1="0" x2="1">
              <stop offset="0%" stop-color="#f4bc74"/>
              <stop offset="52%" stop-color="#dce5d2"/>
              <stop offset="100%" stop-color="#7fc4cb"/>
            </linearGradient>
            <linearGradient id="glassA" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stop-color="#fff8ed" stop-opacity="0.82"/>
              <stop offset="100%" stop-color="#fff8ed" stop-opacity="0.4"/>
            </linearGradient>
          </defs>
          <rect width="220" height="120" rx="22" fill="#fbf0dc"/>
          <rect x="10" y="10" width="200" height="100" rx="18" fill="url(#skyA)"/>
          <path d="M20 88 C52 48, 84 34, 116 28 C150 22, 178 24, 204 42" fill="none" stroke="url(#glassA)" stroke-width="10" stroke-linecap="round"/>
          <path d="M30 98 C64 80, 92 78, 116 96" fill="#fdf5e8"/>
          <path d="M112 98 C144 70, 172 68, 204 98" fill="#f3dfbf"/>
          <rect x="26" y="62" width="48" height="30" rx="12" fill="#2a6169"/>
          <rect x="142" y="58" width="54" height="34" rx="14" fill="#d9856d"/>
          <path d="M118 44 C138 30, 162 28, 184 42 C166 52, 136 54, 118 44 Z" fill="#d65f59"/>
          <ellipse cx="152" cy="43" rx="34" ry="7" fill="#f8ebcf"/>
          <path d="M78 48 C88 36, 102 34, 116 40 C108 48, 90 50, 78 48 Z" fill="#f1be66"/>
          <rect x="82" y="66" width="6" height="20" rx="3" fill="#fff2de"/>
          <rect x="92" y="70" width="6" height="16" rx="3" fill="#58a8ad"/>
          <rect x="102" y="68" width="6" height="18" rx="3" fill="#d96a79"/>
        </svg>
        """,
        "scanner": """
        <svg viewBox="0 0 220 120" xmlns="http://www.w3.org/2000/svg">
          <rect width="220" height="120" rx="22" fill="#fdf1de"/>
          <rect x="12" y="12" width="196" height="96" rx="18" fill="#193f49"/>
          <circle cx="112" cy="56" r="30" fill="#7db9c4"/>
          <ellipse cx="112" cy="56" rx="54" ry="12" fill="none" stroke="#f2ba63" stroke-opacity="0.8" stroke-width="2.5"/>
          <ellipse cx="112" cy="56" rx="18" ry="40" fill="none" stroke="#f6f0e5" stroke-opacity="0.55" stroke-width="2"/>
          <path d="M44 84 C76 72, 96 72, 122 82" stroke="#f7f1e8" stroke-width="8" stroke-linecap="round"/>
          <path d="M132 84 C154 72, 176 72, 192 82" stroke="#d96a79" stroke-width="8" stroke-linecap="round"/>
          <rect x="34" y="88" width="44" height="12" rx="6" fill="#2c5860"/>
          <rect x="146" y="88" width="40" height="12" rx="6" fill="#2c5860"/>
          <circle cx="162" cy="36" r="12" fill="#f2ba63"/>
          <path d="M162 18 V8 M162 64 V54 M144 36 H134 M190 36 H180" stroke="#fff7ea" stroke-width="3" stroke-linecap="round"/>
        </svg>
        """,
        "dashboard": """
        <svg viewBox="0 0 220 120" xmlns="http://www.w3.org/2000/svg">
          <rect width="220" height="120" rx="22" fill="#fdf1de"/>
          <rect x="10" y="14" width="200" height="92" rx="18" fill="#eef4f0"/>
          <path d="M18 88 C54 66, 98 54, 150 54 C174 54, 188 56, 202 60" fill="none" stroke="#f4f6f2" stroke-width="16" stroke-linecap="round"/>
          <path d="M18 88 C54 66, 98 54, 150 54 C174 54, 188 56, 202 60" fill="none" stroke="#d95754" stroke-width="2.5" stroke-dasharray="9 9" stroke-linecap="round"/>
          <path d="M34 44 C78 24, 122 22, 174 34" fill="none" stroke="#f7fbfa" stroke-width="18" stroke-linecap="round"/>
          <path d="M34 44 C78 24, 122 22, 174 34" fill="none" stroke="#84c7cb" stroke-opacity="0.34" stroke-width="7" stroke-linecap="round"/>
          <path d="M94 34 C122 18, 156 18, 182 28 C158 36, 118 40, 94 34 Z" fill="#d56e63"/>
          <ellipse cx="138" cy="32" rx="44" ry="8" fill="#f5ead1"/>
          <rect x="24" y="78" width="36" height="12" rx="6" fill="#23525b"/>
          <rect x="130" y="78" width="48" height="14" rx="7" fill="#d9826b"/>
          <rect x="182" y="74" width="18" height="18" rx="6" fill="#57aab0"/>
          <rect x="62" y="62" width="8" height="18" rx="4" fill="#f1be66"/>
          <rect x="74" y="58" width="8" height="22" rx="4" fill="#5baab2"/>
          <rect x="86" y="54" width="8" height="26" rx="4" fill="#d96a79"/>
        </svg>
        """,
        "comms": """
        <svg viewBox="0 0 220 120" xmlns="http://www.w3.org/2000/svg">
          <rect width="220" height="120" rx="22" fill="#fbf0dc"/>
          <rect x="12" y="12" width="196" height="96" rx="18" fill="#224f58"/>
          <rect x="26" y="24" width="92" height="60" rx="20" fill="#f8efe0"/>
          <path d="M34 76 C56 46, 84 40, 112 48" fill="none" stroke="#90cfd0" stroke-width="8" stroke-linecap="round"/>
          <path d="M126 92 h62" stroke="#f6f1e8" stroke-width="10" stroke-linecap="round"/>
          <rect x="130" y="42" width="48" height="36" rx="14" fill="#d9826b"/>
          <path d="M136 54 h36" stroke="#f8ead0" stroke-width="4" stroke-linecap="round"/>
          <path d="M136 64 h28" stroke="#8ec8cb" stroke-width="4" stroke-linecap="round"/>
          <circle cx="180" cy="32" r="12" fill="#f3be66"/>
          <path d="M180 14 V6 M180 58 V50 M162 32 H154 M206 32 H198 M166 18 L160 12 M194 46 L200 52 M194 18 L200 12 M166 46 L160 52" stroke="#fff7ea" stroke-width="3" stroke-linecap="round"/>
        </svg>
        """,
    }
    return art_map.get(kind, art_map["dashboard"])


def render_home_tab() -> None:
    background_uri = image_data_uri(str(HOME_BG_IMAGE)) if HOME_BG_IMAGE.exists() else None
    add_job_uri = image_data_uri(str(HOME_FEATURE_IMAGES["add_job"])) if HOME_FEATURE_IMAGES["add_job"].exists() else background_uri
    analyze_jd_uri = image_data_uri(str(HOME_FEATURE_IMAGES["analyze_jd"])) if HOME_FEATURE_IMAGES["analyze_jd"].exists() else background_uri
    dashboard_uri = image_data_uri(str(HOME_FEATURE_IMAGES["dashboard"])) if HOME_FEATURE_IMAGES["dashboard"].exists() else background_uri
    outreach_uri = image_data_uri(str(HOME_FEATURE_IMAGES["outreach"])) if HOME_FEATURE_IMAGES["outreach"].exists() else background_uri
    render_hero(background_uri=background_uri)
    st.markdown(
        f"""
        <section class="home-feature-grid">
            <div class="home-feature-card">
                <div class="home-feature-art">
                    <div class="home-feature-photo" style="background-image: url('{add_job_uri}'); background-position: center center;">
                        <span class="home-feature-chip">Intake</span>
                    </div>
                </div>
                <div class="home-feature-copy">
                    <strong>Add Job</strong>
                    <p>Capture each role once with the core details, dates, notes, and job description that drive the rest of the workflow.</p>
                </div>
            </div>
            <div class="home-feature-card">
                <div class="home-feature-art">
                    <div class="home-feature-photo" style="background-image: url('{analyze_jd_uri}'); background-position: center center;">
                        <span class="home-feature-chip">Analysis</span>
                    </div>
                </div>
                <div class="home-feature-copy">
                    <strong>Analyze JD</strong>
                    <p>Turn a pasted job description into requirements, ATS keywords, fit scoring, and resume emphasis suggestions.</p>
                </div>
            </div>
            <div class="home-feature-card">
                <div class="home-feature-art">
                    <div class="home-feature-photo" style="background-image: url('{dashboard_uri}'); background-position: center center;">
                        <span class="home-feature-chip">Tracker</span>
                    </div>
                </div>
                <div class="home-feature-copy">
                    <strong>Dashboard</strong>
                    <p>Review the full application board, scan priorities, open a larger focus view, and edit records in place.</p>
                </div>
            </div>
            <div class="home-feature-card">
                <div class="home-feature-art">
                    <div class="home-feature-photo" style="background-image: url('{outreach_uri}'); background-position: center center;">
                        <span class="home-feature-chip">Outreach</span>
                    </div>
                </div>
                <div class="home-feature-copy">
                    <strong>Outreach Generator</strong>
                    <p>Draft short, usable networking and follow-up messages without drifting into inflated or robotic language.</p>
                </div>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_section_header(title: str, description: str, kicker: str = "Workflow Station") -> None:
    st.markdown(
        f"""
        <section class="section-shell">
            <div class="section-copy">
                <div class="section-kicker">{kicker}</div>
                <h2>{title}</h2>
                <p>{description}</p>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def pretty_value(value: object) -> str:
    if value is None:
        return "-"
    if isinstance(value, float) and pd.isna(value):
        return "-"
    text = str(value).strip()
    return text if text else "-"


def badge_html(value: object) -> str:
    text = pretty_value(value)
    css_name = (
        text.lower()
        .replace(" ", "-")
        .replace("/", "-")
        .replace(",", "")
        .replace(".", "")
    )
    return f'<span class="retro-badge status-{escape(css_name)}">{escape(text)}</span>'


def extract_labeled_url(notes: object, label: str) -> str:
    if notes is None or (isinstance(notes, float) and pd.isna(notes)):
        return ""
    text = str(notes)
    pattern = rf"{re.escape(label)}:\s*(https?://\S+)"
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return match.group(1).strip() if match else ""


def link_html(url: object, label: str) -> str:
    if url is None or (isinstance(url, float) and pd.isna(url)):
        return "-"
    text = str(url).strip()
    if not text:
        return "-"
    safe_url = escape(text, quote=True)
    safe_label = escape(label)
    return f'<a href="{safe_url}" target="_blank" rel="noopener noreferrer">{safe_label}</a>'


def extract_labeled_text(notes: object, label: str) -> str:
    if notes is None or (isinstance(notes, float) and pd.isna(notes)):
        return ""
    text = str(notes)
    pattern = rf"(?im)^{re.escape(label)}:\s*(.+)$"
    match = re.search(pattern, text)
    return match.group(1).strip() if match else ""


def strip_labeled_lines(notes: object, labels: set[str]) -> str:
    if notes is None or (isinstance(notes, float) and pd.isna(notes)):
        return ""
    prefixes = tuple(f"{label.lower()}:" for label in labels)
    cleaned_lines = [
        line
        for line in str(notes).splitlines()
        if line.strip() and not line.strip().lower().startswith(prefixes)
    ]
    return "\n".join(cleaned_lines).strip()


def upsert_labeled_line(notes: object, label: str, value: object) -> str:
    base_text = strip_labeled_lines(notes, {label})
    parts = [line for line in base_text.splitlines() if line.strip()]
    clean_value = str(value).strip() if value is not None else ""
    if clean_value:
        parts.append(f"{label}: {clean_value}")
    return "\n".join(parts).strip()


def render_analysis_list(title: str, items: object, empty_text: str = "No clear signal surfaced.") -> None:
    cleaned = [str(item).strip() for item in (items or []) if str(item).strip()] if isinstance(items, list) else []
    if not cleaned:
        cleaned = [empty_text]
    list_html = "".join(f"<li>{escape(item)}</li>" for item in cleaned)
    st.markdown(
        f"""
        <div class="analysis-card">
            <h4>{escape(title)}</h4>
            <ul>{list_html}</ul>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_analysis_mini_grid(items: dict[str, object]) -> None:
    columns = st.columns(min(len(items), 4))
    for column, (label, value) in zip(columns, items.items()):
        with column:
            st.markdown(
                f"""
                <div class="analysis-mini">
                    <span>{escape(label)}</span>
                    <strong>{escape(pretty_value(value))}</strong>
                </div>
                """,
                unsafe_allow_html=True,
            )


def apply_fetched_job_to_state(prefix: str, fetched: dict[str, str]) -> None:
    field_map = {
        "company": "company",
        "job_title": "job_title",
        "location": "location",
        "description": "description",
        "jd_link": "jd_link",
        "company_site": "company_site",
    }
    for source_key, target_key in field_map.items():
        value = (fetched.get(source_key) or "").strip()
        if value:
            st.session_state[f"{prefix}_{target_key}"] = value


def render_retro_table(
    df: pd.DataFrame,
    title: str,
    subtitle: str = "",
    badge_columns: set[str] | None = None,
    html_columns: set[str] | None = None,
    max_rows: int | None = None,
    scroll_height: int | None = None,
) -> None:
    badge_columns = badge_columns or set()
    html_columns = html_columns or set()
    if df.empty:
        st.markdown(
            f"""
            <div class="retro-table-shell">
                <div class="retro-table-title">
                    <strong>{escape(title)}</strong>
                    <span class="retro-table-subtle">{escape(subtitle)}</span>
                </div>
                <div class="retro-table-empty">No rows to show yet.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    table_df = df.head(max_rows).copy() if max_rows else df.copy()
    headers = "".join(f"<th>{escape(str(column).replace('_', ' '))}</th>" for column in table_df.columns)
    rows_html: list[str] = []
    for _, row in table_df.iterrows():
        cells: list[str] = []
        for column in table_df.columns:
            value = row[column]
            if column in badge_columns:
                cell_value = badge_html(value)
            elif column in html_columns:
                cell_value = str(value)
            else:
                cell_value = escape(pretty_value(value))
            cells.append(f"<td>{cell_value}</td>")
        rows_html.append("<tr>" + "".join(cells) + "</tr>")

    scroll_style = f' style="max-height: {scroll_height}px;"' if scroll_height else ""

    st.markdown(
        f"""
        <div class="retro-table-shell">
            <div class="retro-table-title">
                <strong>{escape(title)}</strong>
                <span class="retro-table-subtle">{escape(subtitle)}</span>
            </div>
            <div class="retro-table-scroll"{scroll_style}>
                <table>
                    <thead><tr>{headers}</tr></thead>
                    <tbody>{''.join(rows_html)}</tbody>
                </table>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def build_application_board(tracker: pd.DataFrame) -> pd.DataFrame:
    board = tracker.copy()
    board["jd_link"] = board["notes"].apply(lambda value: extract_labeled_url(value, "JD link"))
    board["company_site"] = board["notes"].apply(lambda value: extract_labeled_url(value, "Company site"))
    board["JD Link"] = board["jd_link"].apply(lambda value: link_html(value, "JD"))
    board["Company Site"] = board["company_site"].apply(lambda value: link_html(value, "Site"))
    return board[
        [
            "company",
            "job_title",
            "status",
            "fit_score",
            "fit_category",
            "computed_priority",
            "application_date",
            "follow_up_date",
            "contact_name",
            "JD Link",
            "Company Site",
            "next_action",
        ]
    ].rename(
        columns={
            "company": "Company",
            "job_title": "Role",
            "status": "Status",
            "fit_score": "Fit Score",
            "fit_category": "Fit Category",
            "computed_priority": "Priority",
            "application_date": "Applied On",
            "follow_up_date": "Follow-Up",
            "contact_name": "Contact",
            "next_action": "Next Action",
        }
    )


@st.dialog("Application Board", width="large")
def open_application_board_focus(board_df: pd.DataFrame) -> None:
    render_retro_table(
        board_df,
        title="Application Board",
        subtitle=f"{len(board_df)} roles tracked | focused view",
        badge_columns={"Status", "Fit Category", "Priority"},
        html_columns={"JD Link", "Company Site"},
        scroll_height=760,
    )


def render_sidebar() -> None:
    st.sidebar.title("Workflow Settings")
    st.sidebar.caption(describe_llm_status())
    st.sidebar.markdown(
        "This app turns pasted job descriptions into structured job-search decisions and next actions."
    )


def render_add_job_tab() -> None:
    render_section_header(
        "Add Job Application",
        "Capture a role once, then analyze it, draft outreach, and track the next step from the same record.",
        kicker="Intake Console",
    )

    with st.expander("Import baseline from existing Excel tracker"):
        tracker_path = st.text_input(
            "Tracker file path",
            value=str(DEFAULT_TRACKER_PATH),
            help="Use your existing spreadsheet as the starting point for this app.",
        )
        replace_samples = st.checkbox(
            "Replace demo seed data if this app is still using sample rows",
            value=True,
        )
        if st.button("Import Excel Tracker"):
            try:
                result = import_tracker_into_database(
                    Path(tracker_path),
                    replace_sample_seed=replace_samples,
                )
                st.success(
                    f"Imported {result['imported']} roles from the Excel tracker. "
                    f"Skipped {result['skipped']} duplicate roles."
                )
            except Exception as exc:
                st.error(f"Tracker import failed: {exc}")

    with st.expander("Pull details from a JD link"):
        source_url = st.text_input(
            "Job description URL",
            value=st.session_state.get("add_jd_link", ""),
            placeholder="Paste a LinkedIn or official company job link.",
            key="add_job_fetch_url",
        )
        if st.button("Fetch Job Details", type="secondary"):
            fetched, error = fetch_job_posting(source_url)
            if error:
                st.warning(error)
            else:
                apply_fetched_job_to_state("add", fetched)
                st.success("Job details pulled into the form below.")
                st.rerun()

    with st.form("add_job_form"):
        left, right = st.columns(2)
        with left:
            company = st.text_input("Company", value=st.session_state.get("add_company", ""))
            job_title = st.text_input("Job Title", value=st.session_state.get("add_job_title", ""))
            location = st.text_input("Location", value=st.session_state.get("add_location", ""))
            application_status = st.selectbox("Application Status", STATUS_OPTIONS, index=0)
            application_date = st.date_input("Application Date")
            follow_up_date = st.text_input("Follow-Up Date (YYYY-MM-DD)", placeholder="2026-05-05")
        with right:
            contact_name = st.text_input("Referral / Contact Name")
            referral_source = st.text_input("Referral Source")
            outreach_status = st.selectbox("Outreach Status", OUTREACH_STATUS_OPTIONS, index=0)
            jd_link = st.text_input(
                "JD Description Link",
                value=st.session_state.get("add_jd_link", ""),
                placeholder="https://company.com/job-posting",
            )
            company_site = st.text_input(
                "Company Site Link",
                value=st.session_state.get("add_company_site", ""),
                placeholder="https://company.com",
            )
            notes = st.text_area("Notes", height=104)
        job_description = st.text_area(
            "Job Description",
            value=st.session_state.get("add_description", ""),
            height=220,
        )
        allow_duplicate = st.checkbox("Allow duplicate company + job title")
        submitted = st.form_submit_button("Save Application", type="primary")

    if submitted:
        if not company.strip() or not job_title.strip():
            st.error("Company and job title are required.")
            return

        follow_up_iso = to_iso_date(follow_up_date) if follow_up_date else None
        if follow_up_date and not follow_up_iso:
            st.error("Follow-up date must use YYYY-MM-DD format.")
            return

        application_iso = to_iso_date(application_date)
        priority = compute_priority(
            fit_score=None,
            follow_up_date=follow_up_iso,
            outreach_status=outreach_status,
            status=application_status,
        )
        merged_notes = upsert_labeled_line(notes, "JD link", jd_link)
        merged_notes = upsert_labeled_line(merged_notes, "Company site", company_site)

        ok, message, job_id = add_job(
            {
                "company": company.strip(),
                "job_title": job_title.strip(),
                "location": location.strip(),
                "job_description": job_description.strip(),
                "status": application_status,
                "fit_score": None,
                "fit_category": None,
                "priority": priority,
                "application_date": application_iso,
                "follow_up_date": follow_up_iso,
                "contact_name": contact_name.strip(),
                "referral_source": referral_source.strip(),
                "outreach_status": outreach_status,
                "notes": merged_notes,
            },
            allow_duplicate=allow_duplicate,
        )

        if ok:
            st.success(f"Saved application #{job_id}.")
        else:
            st.warning(message)

    jobs = fetch_jobs()
    if not jobs.empty:
        st.markdown("Recent applications")
        preview_cols = [
            "id",
            "company",
            "job_title",
            "status",
            "fit_score",
            "priority",
            "application_date",
            "follow_up_date",
        ]
        render_retro_table(
            jobs[preview_cols].rename(
                columns={
                    "id": "#",
                    "company": "Company",
                    "job_title": "Role",
                    "status": "Status",
                    "fit_score": "Fit Score",
                    "priority": "Priority",
                    "application_date": "Applied On",
                    "follow_up_date": "Follow-Up",
                }
            ),
            title="Recent Applications",
            subtitle="Latest saved roles",
            badge_columns={"Status", "Priority"},
            max_rows=8,
        )


def render_analysis_results(analysis_bundle: dict) -> None:
    parsed = analysis_bundle["parsed"]
    fit = analysis_bundle["fit"]
    emphasis = analysis_bundle["resume"]

    verdict = fit.get("verdict") or fit.get("fit_category", "Not Scored")
    score = fit.get("overall_fit_score", fit.get("fit_score", "-"))
    recommendation = fit.get("final_recommendation", "Review manually")
    effort = fit.get("application_effort", analysis_bundle.get("priority", "-"))
    outreach = fit.get("outreach_recommendation") if isinstance(fit.get("outreach_recommendation"), dict) else {}
    outreach_label = "Yes" if outreach.get("recommended") else "No"

    st.markdown(
        f"""
        <div class="analysis-hero" style="color:#fffaf1 !important; -webkit-text-fill-color:#fffaf1 !important;">
            <span style="color:#fffaf1 !important; -webkit-text-fill-color:#fffaf1 !important;">Evaluation Verdict</span>
            <h3 style="color:#fffaf1 !important; -webkit-text-fill-color:#fffaf1 !important;">{escape(pretty_value(verdict))}</h3>
            <p style="color:#fffaf1 !important; -webkit-text-fill-color:#fffaf1 !important;">{escape(pretty_value(fit.get("explanation")))}</p>
            <div class="analysis-pill-row">
                <span class="analysis-pill" style="color:#fffaf1 !important; -webkit-text-fill-color:#fffaf1 !important;">Score: {escape(pretty_value(score))}/10</span>
                <span class="analysis-pill" style="color:#fffaf1 !important; -webkit-text-fill-color:#fffaf1 !important;">Effort: {escape(pretty_value(effort))}</span>
                <span class="analysis-pill" style="color:#fffaf1 !important; -webkit-text-fill-color:#fffaf1 !important;">Decision: {escape(pretty_value(recommendation))}</span>
                <span class="analysis-pill" style="color:#fffaf1 !important; -webkit-text-fill-color:#fffaf1 !important;">Outreach: {escape(outreach_label)}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    render_analysis_mini_grid(
        {
            "Best Resume Angle": fit.get("best_resume_angle", "Review manually"),
            "Priority": analysis_bundle.get("priority", "-"),
            "Outreach Target": outreach.get("best_target_type", "Review manually"),
            "Short Angle": outreach.get("suggested_short_angle", "Review manually"),
        }
    )

    left, right = st.columns(2)
    with left:
        render_analysis_list("Why It Fits", fit.get("why_it_fits") or fit.get("strongest_alignment"))
    with right:
        render_analysis_list("Concerns / Risks", fit.get("concerns") or fit.get("weakest_alignment"))

    breakdown = fit.get("score_breakdown") if isinstance(fit.get("score_breakdown"), dict) else {}
    if breakdown:
        breakdown_df = pd.DataFrame(
            [{"Dimension": label, "Score": value} for label, value in breakdown.items()]
        )
        render_retro_table(
            breakdown_df,
            title="Score Breakdown",
            subtitle="Weighted rubric used for the final fit score",
        )

    left, right = st.columns(2)
    with left:
        render_analysis_list("Resume Tweaks", fit.get("suggested_resume_tweaks") or emphasis.get("resume_emphasis"))
        render_analysis_list("Keywords To Carry Over", emphasis.get("suggested_keywords") or parsed.get("ats_keywords"))
    with right:
        render_analysis_list("Core Responsibilities", parsed.get("responsibilities"), "No responsibilities extracted.")
        render_analysis_list("Must-Have Signals", parsed.get("required_skills") or parsed.get("ats_keywords"))

    signal_cols = st.columns(3)
    with signal_cols[0]:
        render_analysis_list("AI / Automation Signals", parsed.get("keywords"), "No clear AI signal found.")
    with signal_cols[1]:
        render_analysis_list("Business / Process Signals", parsed.get("business_keywords"), "No clear process signal found.")
    with signal_cols[2]:
        render_analysis_list("ATS Keywords", parsed.get("ats_keywords"), "No ATS keywords extracted.")

    drift_warning = emphasis.get("drift_warning")
    if drift_warning:
        st.warning(drift_warning)

    if st.checkbox("Show diagnostics", value=False):
        st.json(analysis_bundle)


def render_analyze_tab() -> None:
    render_section_header(
        "Analyze Job Description",
        "Convert a pasted listing into structured responsibilities, fit signals, ATS keywords, and resume emphasis.",
        kicker="Signal Scanner",
    )
    jobs = fetch_jobs()

    mode = st.radio(
        "Source",
        ["Paste a new job description", "Use a saved application"],
        horizontal=True,
    )

    selected_job = None
    default_description = ""

    if mode == "Use a saved application":
        if jobs.empty:
            st.info("Save an application first, or switch to the paste option.")
        else:
            jobs_for_select = jobs.copy()
            jobs_for_select["label"] = jobs_for_select.apply(
                lambda row: f"{row['company']} | {row['job_title']} | #{row['id']}",
                axis=1,
            )
            label = st.selectbox("Saved applications", jobs_for_select["label"].tolist())
            selected_job = jobs_for_select.loc[jobs_for_select["label"] == label].iloc[0].to_dict()
            default_description = selected_job.get("job_description") or ""
    else:
        link_cols = st.columns([4, 1])
        with link_cols[0]:
            analyze_url = st.text_input(
                "Job description link",
                placeholder="Paste a LinkedIn or official company JD link.",
                key="analyze_fetch_url",
            )
        with link_cols[1]:
            st.write("")
            st.write("")
            fetch_clicked = st.button("Fetch JD", type="secondary", use_container_width=True)
        if fetch_clicked:
            fetched, error = fetch_job_posting(analyze_url)
            if error:
                st.warning(error)
            else:
                apply_fetched_job_to_state("analyze", fetched)
                st.session_state["analyze_description"] = fetched["description"]
                st.session_state.pop("analysis_bundle", None)
                st.success("Job description pulled from the link.")
                st.rerun()

    if mode == "Use a saved application":
        st.session_state["analyze_description"] = default_description

    description = st.text_area(
        "Job Description",
        value=st.session_state.get("analyze_description", default_description),
        height=320,
        placeholder="Paste the job description here.",
        key="analyze_description",
    )

    if st.button("Run Analysis", type="primary"):
        if not description.strip():
            st.error("Paste a job description before running analysis.")
        else:
            with st.spinner("Parsing job description, scoring fit, and generating resume emphasis..."):
                parsed, parse_meta = parse_job_description(description)
                fit, fit_meta = score_role_fit(description, parsed)
                emphasis, emphasis_meta = recommend_resume_emphasis(
                    description,
                    parsed,
                    fit,
                )

            priority = compute_priority(
                fit_score=fit["fit_score"],
                follow_up_date=selected_job.get("follow_up_date") if selected_job else None,
                outreach_status=selected_job.get("outreach_status") if selected_job else None,
                status=selected_job.get("status") if selected_job else None,
            )
            analysis_bundle = {
                "parsed": parsed,
                "fit": fit,
                "resume": emphasis,
                "priority": priority,
                "meta": {
                    "parse": parse_meta,
                    "fit": fit_meta,
                    "resume": emphasis_meta,
                },
            }
            st.session_state["analysis_bundle"] = analysis_bundle

            if selected_job:
                update_job_analysis(
                    int(selected_job["id"]),
                    fit_score=fit["fit_score"],
                    fit_category=fit["fit_category"],
                    priority=priority,
                    analysis_payload=analysis_bundle,
                )
                st.success("Analysis saved back to the selected application.")

    analysis_bundle = st.session_state.get("analysis_bundle")
    if analysis_bundle:
        render_analysis_results(analysis_bundle)


def render_dashboard_tab() -> None:
    render_section_header(
        "Applications Dashboard",
        "Monitor total volume, status mix, strong-fit roles, overdue follow-ups, and the jobs that deserve attention first.",
        kicker="Control Deck",
    )
    dashboard_notice = st.session_state.pop("dashboard_notice", None)
    if dashboard_notice:
        st.success(dashboard_notice)

    jobs = fetch_jobs()
    tracker = build_tracker_dataframe(jobs)

    total_applications = len(tracker)
    strong_fit = int(tracker["fit_category"].isin(["Primary Target", "Strong Secondary", "Strong Fit"]).sum()) if not tracker.empty else 0
    overdue = int(tracker["is_overdue"].sum()) if not tracker.empty else 0

    counts = tracker["status"].value_counts().reset_index() if not tracker.empty else pd.DataFrame()
    if not counts.empty:
        counts.columns = ["status", "count"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Applications", total_applications)
    c2.metric("Strong-Fit Roles", strong_fit)
    c3.metric("Overdue Follow-Ups", overdue)
    c4.metric("Top Priority Roles", int((tracker["computed_priority"] == "High").sum()) if not tracker.empty else 0)

    left, right = st.columns(2)
    with left:
        st.markdown("Applications by status")
        if counts.empty:
            st.info("No applications yet.")
        else:
            render_retro_table(
                counts.rename(columns={"status": "Status", "count": "Count"}),
                title="Applications by Status",
                subtitle="Current pipeline mix",
                badge_columns={"Status"},
            )
    with right:
        st.markdown("Top priority roles")
        if tracker.empty:
            st.info("No roles to prioritize yet.")
        else:
            top_priority = tracker.loc[
                tracker["computed_priority"] == "High",
                ["company", "job_title", "status", "fit_score", "next_action", "follow_up_date"],
            ].head(10)
            render_retro_table(
                top_priority.rename(
                    columns={
                        "company": "Company",
                        "job_title": "Role",
                        "status": "Status",
                        "fit_score": "Fit Score",
                        "next_action": "Next Action",
                        "follow_up_date": "Follow-Up",
                    }
                ),
                title="Top Priority Roles",
                subtitle="What deserves attention first",
                badge_columns={"Status"},
                scroll_height=380,
            )

    if not tracker.empty:
        board_df = build_application_board(tracker)
        board_left, board_right = st.columns([7, 1.4], vertical_alignment="center")
        with board_left:
            st.markdown("All applications")
        with board_right:
            if st.button(
                "Focus View",
                key="open_board_focus",
                type="secondary",
                icon=":material/open_in_full:",
                use_container_width=True,
            ):
                open_application_board_focus(board_df)
        render_retro_table(
            board_df,
            title="Application Board",
            subtitle=f"{len(board_df)} roles tracked",
            badge_columns={"Status", "Fit Category", "Priority"},
            html_columns={"JD Link", "Company Site"},
            scroll_height=560,
        )

        with st.expander("Edit application from dashboard", expanded=False):
            jobs_for_edit = jobs.copy()
            jobs_for_edit["label"] = jobs_for_edit.apply(
                lambda row: f"{row['company']} | {row['job_title']} | #{row['id']}",
                axis=1,
            )
            selected_label = st.selectbox(
                "Choose an application to edit",
                jobs_for_edit["label"].tolist(),
                key="dashboard_edit_job",
            )
            selected_job = jobs_for_edit.loc[jobs_for_edit["label"] == selected_label].iloc[0].to_dict()
            selected_job_id = int(selected_job["id"])

            current_notes = selected_job.get("notes") or ""
            notes_without_links = strip_labeled_lines(current_notes, {"JD link", "Company site"})
            current_jd_link = extract_labeled_text(current_notes, "JD link")
            current_company_site = extract_labeled_text(current_notes, "Company site")
            current_application_date = "" if pretty_value(selected_job.get("application_date")) == "-" else pretty_value(selected_job.get("application_date"))
            current_follow_up_date = "" if pretty_value(selected_job.get("follow_up_date")) == "-" else pretty_value(selected_job.get("follow_up_date"))

            with st.form(f"dashboard_edit_form_{selected_job_id}"):
                left, right = st.columns(2)
                with left:
                    company = st.text_input("Company", value=selected_job.get("company") or "")
                    job_title = st.text_input("Job Title", value=selected_job.get("job_title") or "")
                    location = st.text_input("Location", value=selected_job.get("location") or "")
                    application_status = st.selectbox(
                        "Application Status",
                        STATUS_OPTIONS,
                        index=STATUS_OPTIONS.index(selected_job["status"]) if selected_job.get("status") in STATUS_OPTIONS else 0,
                        key=f"dashboard_status_{selected_job_id}",
                    )
                    application_date = st.text_input(
                        "Application Date (YYYY-MM-DD)",
                        value=current_application_date,
                    )
                    follow_up_date = st.text_input(
                        "Follow-Up Date (YYYY-MM-DD)",
                        value=current_follow_up_date,
                    )
                with right:
                    contact_name = st.text_input("Contact Name", value=selected_job.get("contact_name") or "")
                    referral_source = st.text_input("Referral Source", value=selected_job.get("referral_source") or "")
                    outreach_status = st.selectbox(
                        "Outreach Status",
                        OUTREACH_STATUS_OPTIONS,
                        index=OUTREACH_STATUS_OPTIONS.index(selected_job["outreach_status"]) if selected_job.get("outreach_status") in OUTREACH_STATUS_OPTIONS else 0,
                        key=f"dashboard_outreach_{selected_job_id}",
                    )
                    company_site = st.text_input("Company Site", value=current_company_site)
                    jd_link = st.text_input("JD Link", value=current_jd_link)
                    notes = st.text_area("Notes", value=notes_without_links, height=180)

                job_description = st.text_area(
                    "Job Description",
                    value=selected_job.get("job_description") or "",
                    height=220,
                )
                confirm_delete = st.checkbox(
                    "I understand this permanently deletes the selected application.",
                    key=f"dashboard_delete_confirm_{selected_job_id}",
                )
                action_left, action_right = st.columns(2)
                with action_left:
                    save_edit = st.form_submit_button("Save Job Changes", type="primary", use_container_width=True)
                with action_right:
                    delete_selected_job = st.form_submit_button("Delete This Job", use_container_width=True)

            if delete_selected_job:
                if not confirm_delete:
                    st.error("Tick the delete confirmation box before removing a saved job.")
                else:
                    delete_job(selected_job_id)
                    outreach_bundle = st.session_state.get("outreach_bundle")
                    if isinstance(outreach_bundle, dict) and outreach_bundle.get("job_id") == selected_job_id:
                        st.session_state.pop("outreach_bundle", None)
                    st.session_state["dashboard_notice"] = f"Deleted application #{selected_job_id}."
                    st.rerun()

            if save_edit:
                if not company.strip() or not job_title.strip():
                    st.error("Company and job title are required.")
                else:
                    application_iso = to_iso_date(application_date) if application_date else None
                    follow_up_iso = to_iso_date(follow_up_date) if follow_up_date else None
                    if application_date and not application_iso:
                        st.error("Application date must use YYYY-MM-DD format.")
                    elif follow_up_date and not follow_up_iso:
                        st.error("Follow-up date must use YYYY-MM-DD format.")
                    else:
                        merged_notes = upsert_labeled_line(notes, "JD link", jd_link)
                        merged_notes = upsert_labeled_line(merged_notes, "Company site", company_site)
                        priority = compute_priority(
                            fit_score=selected_job.get("fit_score"),
                            follow_up_date=follow_up_iso,
                            outreach_status=outreach_status,
                            status=application_status,
                        )
                        update_job_fields(
                            selected_job_id,
                            {
                                "company": company.strip(),
                                "job_title": job_title.strip(),
                                "location": location.strip(),
                                "status": application_status,
                                "application_date": application_iso,
                                "follow_up_date": follow_up_iso,
                                "contact_name": contact_name.strip(),
                                "referral_source": referral_source.strip(),
                                "outreach_status": outreach_status,
                                "job_description": job_description.strip(),
                                "notes": merged_notes,
                                "priority": priority,
                            },
                        )
                        st.session_state["dashboard_notice"] = f"Updated application #{selected_job_id}."
                        st.rerun()


def render_outreach_tab() -> None:
    render_section_header(
        "Outreach Generator",
        "Draft short, human messages for networking, follow-up, and referrals without drifting into stiff or inflated language.",
        kicker="Comms Bay",
    )
    jobs = fetch_jobs()

    if jobs.empty:
        st.info("Save an application first to generate outreach drafts.")
        return

    jobs["label"] = jobs.apply(lambda row: f"{row['company']} | {row['job_title']} | #{row['id']}", axis=1)
    selected_label = st.selectbox("Choose an application", jobs["label"].tolist(), key="outreach_job")
    selected_job = jobs.loc[jobs["label"] == selected_label].iloc[0].to_dict()
    selected_job_id = int(selected_job["id"])

    st.caption(
        f"Status: {selected_job['status']} | Follow-up: {format_date_or_dash(selected_job.get('follow_up_date'))} | "
        f"Outreach: {selected_job.get('outreach_status') or 'Not Started'}"
    )

    analysis_payload = safe_json_loads(selected_job.get("analysis_json"))
    custom_context = st.text_area(
        "Optional context for outreach",
        placeholder="Example: Reached out after a webinar, or alumni connection through Bologna Business School.",
        height=100,
    )

    if st.button("Generate Outreach Drafts", type="primary"):
        with st.spinner("Writing human-sounding outreach drafts..."):
            drafts, meta = generate_outreach_drafts(
                selected_job,
                analysis_payload=analysis_payload if isinstance(analysis_payload, dict) else None,
                custom_context=custom_context,
            )
        st.session_state["outreach_bundle"] = {"drafts": drafts, "meta": meta, "job_id": selected_job_id}
        update_job_outreach(selected_job_id, outreach_status="Drafted", outreach_payload=drafts)
        st.success("Drafts generated and saved to the application record.")

    outreach_bundle = st.session_state.get("outreach_bundle")
    if outreach_bundle and outreach_bundle.get("job_id") == selected_job_id:
        drafts = outreach_bundle["drafts"]
        st.text_area("LinkedIn connection note", value=drafts["linkedin_note"], height=110)
        st.text_area("Follow-up message", value=drafts["follow_up_message"], height=130)
        st.text_area("Referral request", value=drafts["referral_request_message"], height=130)
        with st.expander("Structured output"):
            st.json(outreach_bundle)

    st.markdown("Update outreach status")
    current_outreach = selected_job.get("outreach_status") or OUTREACH_STATUS_OPTIONS[0]
    new_outreach_status = st.selectbox(
        "Outreach status",
        OUTREACH_STATUS_OPTIONS,
        index=OUTREACH_STATUS_OPTIONS.index(current_outreach) if current_outreach in OUTREACH_STATUS_OPTIONS else 0,
        key="outreach_status_update",
    )
    if st.button("Save Outreach Status"):
        priority = compute_priority(
            fit_score=selected_job.get("fit_score"),
            follow_up_date=selected_job.get("follow_up_date"),
            outreach_status=new_outreach_status,
            status=selected_job.get("status"),
        )
        update_job_fields(
            selected_job_id,
            {
                "outreach_status": new_outreach_status,
                "priority": priority,
            },
        )
        st.success("Outreach status updated.")


def render_follow_up_tab() -> None:
    render_section_header(
        "Follow-Up Tracker",
        "Spot overdue outreach, roles due for a check-in, and strong-fit applications that still need action.",
        kicker="Priority Radar",
    )
    jobs = fetch_jobs()
    tracker = build_tracker_dataframe(jobs)

    if tracker.empty:
        st.info("No applications yet.")
        return

    metrics = st.columns(3)
    metrics[0].metric("Due Today", int(tracker["is_due_today"].sum()))
    metrics[1].metric("Overdue", int(tracker["is_overdue"].sum()))
    metrics[2].metric("High Priority Without Outreach", int(tracker["needs_outreach"].sum()))

    overdue_df = tracker.loc[tracker["is_overdue"]]
    due_today_df = tracker.loc[tracker["is_due_today"]]
    outreach_gap_df = tracker.loc[tracker["needs_outreach"]]

    st.markdown("Overdue follow-ups")
    st.dataframe(
        overdue_df[["company", "job_title", "status", "follow_up_date", "contact_name", "next_action", "computed_priority"]],
        width="stretch",
    )

    st.markdown("Follow-ups due today")
    st.dataframe(
        due_today_df[["company", "job_title", "status", "follow_up_date", "contact_name", "next_action", "computed_priority"]],
        width="stretch",
    )

    st.markdown("High-priority roles with no outreach completed")
    st.dataframe(
        outreach_gap_df[["company", "job_title", "status", "outreach_status", "contact_name", "next_action", "computed_priority"]],
        width="stretch",
    )

    st.markdown("Update a tracked application")
    tracker["label"] = tracker.apply(lambda row: f"{row['company']} | {row['job_title']} | #{row['id']}", axis=1)
    selected_label = st.selectbox("Tracked application", tracker["label"].tolist(), key="follow_up_job")
    selected = tracker.loc[tracker["label"] == selected_label].iloc[0].to_dict()

    with st.form("follow_up_update_form"):
        updated_status = st.selectbox(
            "Application status",
            STATUS_OPTIONS,
            index=STATUS_OPTIONS.index(selected["status"]) if selected["status"] in STATUS_OPTIONS else 0,
        )
        updated_outreach = st.selectbox(
            "Outreach status",
            OUTREACH_STATUS_OPTIONS,
            index=OUTREACH_STATUS_OPTIONS.index(selected["outreach_status"])
            if selected["outreach_status"] in OUTREACH_STATUS_OPTIONS
            else 0,
        )
        updated_follow_up = st.text_input(
            "Follow-up date (YYYY-MM-DD)",
            value=selected.get("follow_up_date") or "",
        )
        updated_contact = st.text_input("Contact name", value=selected.get("contact_name") or "")
        updated_notes = st.text_area("Notes", value=selected.get("notes") or "", height=120)
        submit = st.form_submit_button("Save Tracker Update")

    if submit:
        if updated_follow_up and not to_iso_date(updated_follow_up):
            st.error("Follow-up date must use YYYY-MM-DD format.")
            return

        follow_up_iso = to_iso_date(updated_follow_up) if updated_follow_up else None
        priority = compute_priority(
            fit_score=selected.get("fit_score"),
            follow_up_date=follow_up_iso,
            outreach_status=updated_outreach,
            status=updated_status,
        )
        update_job_fields(
            int(selected["id"]),
            {
                "status": updated_status,
                "outreach_status": updated_outreach,
                "follow_up_date": follow_up_iso,
                "contact_name": updated_contact.strip(),
                "notes": updated_notes.strip(),
                "priority": priority,
            },
        )
        st.success("Application tracker updated.")


def main() -> None:
    initialize_app()
    apply_retro_theme()
    render_sidebar()

    home_tab, add_tab, analyze_tab, dashboard_tab, outreach_tab = st.tabs(
        [
            "Home",
            "Add Job",
            "Analyze JD",
            "Dashboard",
            "Outreach Generator",
        ]
    )

    with home_tab:
        render_home_tab()
    with add_tab:
        render_add_job_tab()
    with analyze_tab:
        render_analyze_tab()
    with dashboard_tab:
        render_dashboard_tab()
    with outreach_tab:
        render_outreach_tab()


if __name__ == "__main__":
    main()
