#!/usr/bin/env python
import os
import sys
from dotenv import load_dotenv


def main() -> None:
    # Load .env early so runtime checks see env vars
    load_dotenv()
    # Enforce GEMINI_API_KEY presence when starting the dev server
    if any(cmd in sys.argv for cmd in ["runserver", "runserver_plus"]):
        if not os.environ.get("GEMINI_API_KEY"):
            sys.stderr.write("Error: GEMINI_API_KEY is required to run the server. Set it in .env.\n")
            sys.exit(1)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ai_chat.settings")
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
