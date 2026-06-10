#!/usr/bin/env python3
"""Quick import and app load smoke test."""

import sys


def main() -> int:
    try:
        import fastapi  # noqa: F401
        import uvicorn  # noqa: F401
        import supabase  # noqa: F401
        import stripe  # noqa: F401
        import resend  # noqa: F401
        from app.api.main import app

        print("All imports successful.")
        print(f"FastAPI app: {app.title}")
        return 0
    except Exception as exc:
        print(f"Smoke test failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
