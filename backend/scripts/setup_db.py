"""Apply the checked-in schema and ordered, idempotent migrations to DATABASE_URL."""
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.db.connection import apply_schema


if __name__ == "__main__":
    try:
        apply_schema()
    except Exception as error:
        # PostgreSQL diagnostics identify the bad SQL without exposing DATABASE_URL.
        diagnostic = getattr(error, "diag", None)
        detail = getattr(diagnostic, "message_primary", None)
        suffix = f": {detail}" if detail else ". Check DATABASE_URL and database permissions."
        print(f"Database setup failed ({type(error).__name__}){suffix}", file=sys.stderr)
        raise SystemExit(1) from None
    print("TrustFlow database schema and migrations applied.")
