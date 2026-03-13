"""
scripts/init_db.py
───────────────────
One-shot DB initialiser. Run once before starting the server.
Usage: python scripts/init_db.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import get_settings
from app.db.database import create_all_tables


async def main():
    s = get_settings()
    print(f"Database: {s.database_url}")
    await create_all_tables()
    print("✅  All tables created.")


if __name__ == "__main__":
    asyncio.run(main())
