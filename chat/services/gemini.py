from __future__ import annotations

import json
import os
from typing import List, Dict, Any


class GeminiServiceError(RuntimeError):
    pass


def _get_model_name() -> str:
    return os.environ.get("GEMINI_MODEL", "models/gemini-2.5-flash-lite")


def _get_client():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise GeminiServiceError("Gemini API key is missing; set GEMINI_API_KEY in .env")
    try:
        import google.generativeai as genai
    except Exception as e:  # pragma: no cover - import error path
        raise GeminiServiceError(f"Gemini client not available: {e}")
    genai.configure(api_key=api_key)
    model_name = _get_model_name()
    try:
        model = genai.GenerativeModel(model_name)
    except Exception as e:
        raise GeminiServiceError(f"Gemini model init failed: {e}")
    return model


def generate_reply(history: List[Dict[str, str]], prompt: str, timeout_s: int = 10) -> str:
    """
    Minimal wrapper around google-generativeai.
    - history: list of {"role": "user"|"ai", "text": "..."}
    - prompt: the latest user input
    Returns plain text reply or raises GeminiServiceError on failure.
    """
    try:
        model = _get_client()
        # Build messages in Gemini format
        messages = []
        for msg in history:
            role = msg.get("role", "user")
            content = msg.get("text", "")
            # Gemini expects role: "user" or "model"
            messages.append({
                "role": "user" if role == "user" else "model",
                "parts": [content],
            })
        # Append current prompt as user
        messages.append({"role": "user", "parts": [prompt]})

        # Synchronous call
        resp = model.generate_content(messages, request_options={"timeout": timeout_s})
        text = getattr(resp, "text", None) or ""
        text = text.strip()
        if not text:
            raise GeminiServiceError("Empty response from Gemini")
        return text
    except Exception as e:
        raise GeminiServiceError(f"Gemini request failed: {e}")


def generate_actionable_insights(summary: Dict[str, Any], timeout_s: int = 15) -> str:
    """
    Generate actionable insights based on aggregated feedback summary data.
    """
    summary_json = json.dumps(summary, default=str, indent=2)
    prompt = (
        "You are a product operations analyst reviewing user feedback for an AI assistant.\n"
        "Using the structured data below, produce three concise, actionable recommendations "
        "for improving the assistant. Focus on clear next steps grounded in the data trends.\n\n"
        f"Feedback summary:\n{summary_json}\n\n"
        "Respond with a markdown bullet list (max 4 bullets). Start each bullet with a strong verb."
    )

    try:
        model = _get_client()
        resp = model.generate_content(
            [{"role": "user", "parts": [prompt]}],
            request_options={"timeout": timeout_s},
        )
        text = getattr(resp, "text", None) or ""
        text = text.strip()
        if not text:
            raise GeminiServiceError("Empty response from Gemini")
        return text
    except GeminiServiceError:
        raise
    except Exception as e:
        raise GeminiServiceError(f"Gemini request failed: {e}")
