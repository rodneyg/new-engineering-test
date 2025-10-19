from __future__ import annotations

import os
import sys

from dotenv import load_dotenv


def main() -> int:
    load_dotenv()
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY is not set. Populate it in your environment or .env file.", file=sys.stderr)
        return 1

    try:
        import google.generativeai as genai
    except Exception as exc:  # pragma: no cover - import failure path
        print(f"Failed to import google.generativeai: {exc}", file=sys.stderr)
        return 1

    genai.configure(api_key=api_key)

    print("Available Gemini models (supporting generateContent):")
    try:
        models = genai.list_models()
    except Exception as exc:
        print(f"Failed to list models: {exc}", file=sys.stderr)
        return 1

    count = 0
    for model in models:
        methods = getattr(model, "supported_generation_methods", []) or []
        if "generateContent" in methods:
            print(f"- {model.name}")
            count += 1

    if count == 0:
        print("No models supporting generateContent were returned.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
