"""Fabricated fraud workflow demo that degrades gracefully when rerank is unavailable."""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone

from alloynative import AlloyIndex
from alloynative.errors import AlloyNativeError


TRANSACTIONS_DDL = """
CREATE TABLE IF NOT EXISTS transactions (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    merchant_name TEXT NOT NULL,
    description TEXT NOT NULL,
    amount NUMERIC(12, 2) NOT NULL,
    account_type TEXT NOT NULL,
    status TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding vector(768)
)
"""

TRANSACTION_ROWS = [
    {
        "id": "txn_001",
        "account_id": "acc_8821",
        "merchant_name": "ATM Withdrawal",
        "description": "Large cash withdrawal at 2am outside usual geography",
        "amount": 15000.00,
        "account_type": "checking",
        "status": "flagged",
        "timestamp": datetime(2024, 3, 15, 2, 14, tzinfo=timezone.utc),
        "metadata": {"country": "SG", "risk": "high"},
    },
    {
        "id": "txn_002",
        "account_id": "acc_8822",
        "merchant_name": "Grocery Store",
        "description": "Routine grocery purchase near home",
        "amount": 84.50,
        "account_type": "checking",
        "status": "normal",
        "timestamp": datetime(2024, 3, 15, 18, 20, tzinfo=timezone.utc),
        "metadata": {"country": "SG", "risk": "low"},
    },
    {
        "id": "txn_003",
        "account_id": "acc_4410",
        "merchant_name": "Card Present Retail",
        "description": "High-value electronics purchase in an unusual location",
        "amount": 11250.00,
        "account_type": "checking",
        "status": "review",
        "timestamp": datetime(2024, 3, 16, 7, 5, tzinfo=timezone.utc),
        "metadata": {"country": "SG", "risk": "medium"},
    },
]


async def run_query(index: AlloyIndex) -> None:
    rerank_model = os.environ.get("ALLOYNATIVE_RERANK_MODEL", "gemini-2.0-flash-global")
    require_rerank = os.environ.get("ALLOYNATIVE_RERANK_REQUIRED", "false").lower() == "true"

    try:
        results = await index.query(
            "suspicious large withdrawal unusual location",
            filters={"amount__gte": 10000, "account_type": "checking"},
            rerank=True,
            rerank_model=rerank_model,
            limit=5,
        )
        print(f"Rerank enabled with model: {rerank_model}")
    except AlloyNativeError as exc:
        if require_rerank:
            raise
        print("Rerank unavailable, falling back to hybrid-only search.")
        print(f"Reason: {exc}")
        results = await index.query(
            "suspicious large withdrawal unusual location",
            filters={"amount__gte": 10000, "account_type": "checking"},
            rerank=False,
            limit=5,
        )

    print("Result count:", len(results.results))
    for item in results.results:
        print(item)


async def main() -> None:
    index = await AlloyIndex.aconnect(
        table="transactions",
        project_id=os.environ["ALLOYNATIVE_PROJECT_ID"],
        region=os.environ["ALLOYNATIVE_REGION"],
        cluster=os.environ["ALLOYNATIVE_CLUSTER"],
        instance=os.environ["ALLOYNATIVE_INSTANCE"],
        database=os.environ["ALLOYNATIVE_DATABASE"],
        db_user=os.environ["ALLOYNATIVE_DB_USER"],
        ip_type=os.environ.get("ALLOYNATIVE_IP_TYPE", "PUBLIC"),
        text_columns=["merchant_name", "description"],
        metadata_column="metadata",
        embedding_column="embedding",
        embedding_source_column="description",
    )

    try:
        print("Capabilities:", index.capabilities)
        await index.client.execute(TRANSACTIONS_DDL)
        await index.upsert(TRANSACTION_ROWS)
        await run_query(index)
    finally:
        await index.close()


asyncio.run(main())
