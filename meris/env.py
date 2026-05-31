"""Load .env from project root or cwd."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv


def load_env() -> None:
    for base in (Path.cwd(), Path(__file__).resolve().parent.parent):
        env = base / ".env"
        if env.is_file():
            load_dotenv(env, override=False)
            return
    load_dotenv(override=False)
