"""Retry due optional integration outbox events, for a local or scheduled worker."""
import asyncio
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.events import deliver_pending


if __name__ == "__main__":
    print(f"Delivered {asyncio.run(deliver_pending(limit=50))} event(s).")
