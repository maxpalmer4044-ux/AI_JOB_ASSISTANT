from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import requests
from dotenv import load_dotenv

from src.utils import safe_json_loads


load_dotenv()


@dataclass
class ProviderResolution:
    provider: str
    model: str
    mode: str
    reason: str


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def resolve_llm() -> ProviderResolution:
    api_key = _env("HF_TOKEN")
    model = _env("HF_MODEL", "meta-llama/Llama-3.3-70B-Instruct:groq")
    if api_key:
        return ProviderResolution("llama", model, "live", "Using Hugging Face Router with the configured HF token.")
    return ProviderResolution("mock", "mock-local", "mock", "HF token missing. Falling back to mock mode.")


def describe_llm_status() -> str:
    resolved = resolve_llm()
    return f"Mode: {resolved.mode} | Provider: {resolved.provider} | Model: {resolved.model}. {resolved.reason}"


def _call_llama(system_prompt: str, user_prompt: str, model: str) -> str:
    response = requests.post(
        "https://router.huggingface.co/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {_env('HF_TOKEN')}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        },
        timeout=45,
    )
    response.raise_for_status()
    payload = response.json()
    return payload["choices"][0]["message"]["content"]


def call_json_llm(system_prompt: str, user_prompt: str) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    resolution = resolve_llm()
    meta = {
        "provider": resolution.provider,
        "model": resolution.model,
        "mode": resolution.mode,
        "reason": resolution.reason,
        "error": None,
    }

    if resolution.mode == "mock":
        return None, meta

    try:
        if resolution.provider == "llama":
            raw_text = _call_llama(system_prompt, user_prompt, resolution.model)
        else:
            raise ValueError(f"Unsupported provider: {resolution.provider}")

        parsed = safe_json_loads(raw_text)
        if not isinstance(parsed, dict):
            raise ValueError("Provider returned malformed JSON.")
        meta["raw_preview"] = raw_text[:250]
        return parsed, meta
    except Exception as exc:
        meta["error"] = str(exc)
        meta["mode"] = "mock"
        meta["reason"] = "Live LLM call failed. Falling back to mock mode."
        return None, meta
