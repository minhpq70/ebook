"""
Standalone worker entrypoint.
Chạy riêng nếu muốn tách ingestion khỏi FastAPI process.
"""
from __future__ import annotations

import asyncio

from services.ingestion_worker import run_worker_forever


def main() -> None:
    asyncio.run(run_worker_forever("standalone-worker"))


if __name__ == "__main__":
    main()
