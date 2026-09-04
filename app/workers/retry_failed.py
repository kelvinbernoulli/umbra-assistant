"""Run bounded retries for failed ingestion jobs."""

from __future__ import annotations

import argparse
import asyncio

from app.db.session import SessionLocal
from app.services.ingestion.retry import run_retry_worker


def main() -> None:
    parser = argparse.ArgumentParser(description="Retry failed Umbra ingestion jobs")
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    result = asyncio.run(run_retry_worker(SessionLocal, limit=args.limit))
    print(
        f"selected={result['selected']} succeeded={result['succeeded']} "
        f"failed={result['failed']}"
    )


if __name__ == "__main__":
    main()
