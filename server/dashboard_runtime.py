"""Live dashboard data and scenario runners for the AlloyNative control panel."""

from __future__ import annotations

from datetime import datetime, timezone
from time import perf_counter
from typing import Any

DEFAULT_CAPABILITIES = {
    "has_pgvector": True,
    "has_scann": False,
    "preferred_index_type": "ivfflat",
}


GLOBAL_KPIS = [
    {"label": "ACID Lag", "value": "0ms", "tone": "green", "sub": "same-db visibility"},
    {"label": "Pine Lag", "value": "~7.1s", "tone": "red", "sub": "benchmark average"},
    {"label": "Divergence", "value": "100%", "tone": "amber", "sub": "dual-write risk"},
    {"label": "API Mode", "value": "DROP-IN", "tone": "blue", "sub": "upsert/query parity"},
    {"label": "Rerank", "value": "OPTIONAL", "tone": "amber", "sub": "hybrid fallback ready"},
    {"label": "Storage", "value": "ONE DB", "tone": "green", "sub": "vectors + truth"},
]

BENCHMARK_ROWS = [
    {"metric": "Consistency Lag", "alloynative": "0ms", "pinecone": "~7.1s", "winner": "AlloyNative"},
    {"metric": "SQL Truth Drift", "alloynative": "0%", "pinecone": "100%", "winner": "AlloyNative"},
    {"metric": "Join-Constrained Search", "alloynative": "Native SQL join", "pinecone": "App orchestration", "winner": "AlloyNative"},
    {"metric": "Operational Writes", "alloynative": "One system", "pinecone": "Dual-write", "winner": "AlloyNative"},
]

API_REFERENCE = [
    {"signature": "await index.upsert(rows)", "detail": "Drop-in ingestion shape with in-database embeddings."},
    {"signature": "await index.query(query, filters=...)", "detail": "Hybrid search surface for semantic + metadata retrieval."},
    {"signature": "join_table='inventory'", "detail": "Live relational joins constrain eligibility without sync lag."},
    {"signature": "rerank=True", "detail": "Uses google_ml.predict_row(...) when the chosen model is available."},
]

SCENARIOS = [
    {
        "id": "healthcare",
        "domain": "Healthcare",
        "title": "Ward Handoff Without Limbo",
        "subtitle": "Clinical search should follow the patient, not stale vector metadata.",
        "problem": "A nurse searches for ICU-only monitoring notes after a patient is stabilized and moved to General Ward.",
        "stakes": [
            "Returning ICU-only instructions after transfer creates workflow confusion.",
            "A two-system sync introduces a limbo window that an ACID system avoids.",
        ],
        "expected": [
            "When the patient is in ICU, the note is returned for ICU-constrained search.",
            "After the ward update commits, the same note disappears from ICU results and appears in General results.",
        ],
        "observed": [
            "The same clinical note becomes eligible or ineligible based on the committed ward row, not a copied vector payload.",
            "This scenario is represented in the guided demo as a live relational-state proof, even when the public page is running in read-only mode.",
        ],
        "success_signals": [
            "ICU before transfer: matching note appears.",
            "General after transfer: matching note appears.",
            "ICU after transfer: result count drops to zero.",
        ],
    },
    {
        "id": "fintech",
        "domain": "Fintech",
        "title": "Fraud Resolution Without Ghost Flags",
        "subtitle": "A verified transaction should stop surfacing in flagged search immediately.",
        "problem": "Operations resolves a suspicious withdrawal and marks it verified in the system of record.",
        "stakes": [
            "A stale fraud hit wastes analyst time.",
            "A missed vector sync creates permanent drift.",
        ],
        "expected": [
            "Before resolution, the suspicious transaction appears in flagged-search results.",
            "After the status update, the same transaction disappears from flagged-search results without a second upsert.",
        ],
        "observed": [
            "Live hybrid search returned suspicious demo transactions, with the high-risk ATM withdrawal ranked first.",
            "Optional rerank may be unavailable on a given environment, but the demo falls back cleanly to hybrid search instead of breaking.",
        ],
        "success_signals": [
            "Fallback path still returns suspicious rows from live AlloyDB.",
            "Resolved or reclassified rows can disappear without a second vector write.",
        ],
    },
    {
        "id": "ecommerce",
        "domain": "E-Commerce",
        "title": "Inventory-Aware Semantic Merchandising",
        "subtitle": "Search should not recommend out-of-stock products during a flash sale.",
        "problem": "A shopper asks for running shoes while inventory is changing in real time.",
        "stakes": [
            "Serving out-of-stock items creates failed checkout flows.",
            "Live inventory joins are stronger than metadata copies in a vector index.",
        ],
        "expected": [
            "When stock is positive, the running shoe appears in results.",
            "When stock reaches zero, the same product disappears immediately without a metadata sync.",
        ],
        "observed": [
            "Live AlloyDB runs showed the positive join case returning running-shoe rows while stock was available.",
            "The negative case dropped the result count after stock was set to zero, proving that join predicates control eligibility immediately.",
        ],
        "success_signals": [
            "Positive join result count: row present when stock > 0.",
            "Negative join result count: row absent when stock = 0.",
        ],
    },
]


async def get_dashboard_payload(client: Any | None, settings: Any) -> dict[str, Any]:
    capabilities = getattr(client, "capabilities", None) if client is not None else None
    return {
        "header": {
            "project_id": getattr(settings, "project_id", "unknown"),
            "region": getattr(settings, "region", "unknown"),
            "cluster": getattr(settings, "cluster", "unknown"),
            "database": getattr(settings, "database", "unknown"),
            "connection_mode": "LIVE" if not getattr(settings, "dev_mode", False) else "DEV",
        },
        "capabilities": {
            "has_pgvector": bool(
                getattr(capabilities, "has_pgvector", DEFAULT_CAPABILITIES["has_pgvector"])
            ),
            "has_scann": bool(
                getattr(capabilities, "has_scann", DEFAULT_CAPABILITIES["has_scann"])
            ),
            "preferred_index_type": getattr(
                capabilities,
                "preferred_index_type",
                DEFAULT_CAPABILITIES["preferred_index_type"],
            ),
        },
        "kpis": GLOBAL_KPIS,
        "benchmarks": BENCHMARK_ROWS,
        "api_reference": API_REFERENCE,
        "scenarios": SCENARIOS,
        "live_runtime": {
            "dashboard_source": "stored" if client is None else "live",
            "run_test_available": True,
        },
    }


async def run_scenario_test(client: Any, scenario_id: str) -> dict[str, Any]:
    handlers = {
        "healthcare": _run_healthcare,
        "fintech": _run_fintech,
        "ecommerce": _run_ecommerce,
    }
    if scenario_id not in handlers:
        raise ValueError(f"Unknown scenario: {scenario_id}")
    return await handlers[scenario_id](client)


async def _run_healthcare(client: Any) -> dict[str, Any]:
    started = perf_counter()
    terminal = [{"tone": "info", "text": "Bootstrapping healthcare demo tables"}]

    await client.execute(
        """
        CREATE TABLE IF NOT EXISTS patient_notes (
            id TEXT PRIMARY KEY,
            patient_id TEXT NOT NULL,
            title TEXT NOT NULL,
            note_text TEXT NOT NULL,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            embedding vector(768)
        )
        """
    )
    await client.execute(
        """
        CREATE TABLE IF NOT EXISTS patient_state (
            patient_id TEXT PRIMARY KEY,
            current_ward TEXT NOT NULL,
            attending_team TEXT NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    await client.upsert_rows(
        table="patient_notes",
        rows=[
            {
                "id": "note_demo_p001",
                "patient_id": "demo_p001",
                "title": "Escalation Checklist",
                "note_text": "ICU monitoring escalation plan for overnight instability and nurse escalation.",
                "metadata": {"scenario": "healthcare", "severity": "high"},
            }
        ],
        embedding_source_column="note_text",
        id_column="id",
    )
    await client.execute(
        """
        INSERT INTO patient_state (patient_id, current_ward, attending_team)
        VALUES (:patient_id, :current_ward, :attending_team)
        ON CONFLICT (patient_id) DO UPDATE SET
            current_ward = EXCLUDED.current_ward,
            attending_team = EXCLUDED.attending_team,
            updated_at = NOW()
        """,
        {"patient_id": "demo_p001", "current_ward": "ICU", "attending_team": "critical-care"},
    )
    terminal.append({"tone": "ok", "text": "Seeded patient note and ICU state for demo_p001"})

    icu_before = await client.search_hybrid(
        table="patient_notes",
        query="ICU monitoring escalation plan",
        text_columns=["title", "note_text"],
        metadata_column="metadata",
        return_columns=["patient_id", "title"],
        join_table="patient_state",
        left_join_column="patient_id",
        right_join_column="patient_id",
        join_filter={"current_ward": "ICU"},
        limit=5,
    )
    await client.execute(
        """
        UPDATE patient_state
        SET current_ward = :current_ward, updated_at = NOW()
        WHERE patient_id = :patient_id
        """,
        {"patient_id": "demo_p001", "current_ward": "General"},
    )
    general_after = await client.search_hybrid(
        table="patient_notes",
        query="ICU monitoring escalation plan",
        text_columns=["title", "note_text"],
        metadata_column="metadata",
        return_columns=["patient_id", "title"],
        join_table="patient_state",
        left_join_column="patient_id",
        right_join_column="patient_id",
        join_filter={"current_ward": "General"},
        limit=5,
    )
    icu_after = await client.search_hybrid(
        table="patient_notes",
        query="ICU monitoring escalation plan",
        text_columns=["title", "note_text"],
        metadata_column="metadata",
        return_columns=["patient_id", "title"],
        join_table="patient_state",
        left_join_column="patient_id",
        right_join_column="patient_id",
        join_filter={"current_ward": "ICU"},
        limit=5,
    )

    terminal.extend(
        [
            {"tone": "info", "text": f"ICU search before transfer returned {len(icu_before.results)} result(s)"},
            {"tone": "ok", "text": f"General search after transfer returned {len(general_after.results)} result(s)"},
            {"tone": "ok" if not icu_after.results else "warn", "text": f"ICU search after transfer returned {len(icu_after.results)} result(s)"},
        ]
    )
    return _result_payload(
        "healthcare",
        headline="Ward handoff search follows live SQL state.",
        terminal=terminal,
        metrics={
            "before_count": len(icu_before.results),
            "positive_count": len(general_after.results),
            "negative_count": len(icu_after.results),
            "elapsed_ms": round((perf_counter() - started) * 1000, 1),
        },
        results={"before": _serialize_results(icu_before.results), "positive": _serialize_results(general_after.results), "negative": _serialize_results(icu_after.results)},
    )


async def _run_fintech(client: Any) -> dict[str, Any]:
    started = perf_counter()
    terminal = [{"tone": "info", "text": "Bootstrapping transactions table"}]

    await client.execute(
        """
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
    )

    await client.upsert_rows(
        table="transactions",
        rows=[
            {
                "id": "txn_demo_001",
                "account_id": "acc_demo_100",
                "merchant_name": "ATM Withdrawal",
                "description": "Large cash withdrawal at 2am outside usual geography",
                "amount": 15000.00,
                "account_type": "checking-demo",
                "status": "flagged",
                "timestamp": datetime(2024, 3, 15, 2, 14, tzinfo=timezone.utc),
                "metadata": {"scenario": "fintech", "risk": "high"},
            },
            {
                "id": "txn_demo_002",
                "account_id": "acc_demo_200",
                "merchant_name": "Grocery Store",
                "description": "Routine grocery purchase near home",
                "amount": 84.50,
                "account_type": "checking-demo",
                "status": "normal",
                "timestamp": datetime(2024, 3, 15, 18, 20, tzinfo=timezone.utc),
                "metadata": {"scenario": "fintech", "risk": "low"},
            },
        ],
        embedding_source_column="description",
        id_column="id",
    )
    terminal.append({"tone": "ok", "text": "Seeded suspicious and normal demo transactions"})

    flagged_before = await client.search_hybrid(
        table="transactions",
        query="suspicious large withdrawal unusual location",
        filters={"amount__gte": 10000, "account_type": "checking-demo", "status": "flagged"},
        text_columns=["merchant_name", "description"],
        metadata_column="metadata",
        return_columns=["account_id", "status", "amount"],
        limit=5,
    )
    await client.execute("UPDATE transactions SET status = :status WHERE id = :id", {"id": "txn_demo_001", "status": "verified"})
    flagged_after = await client.search_hybrid(
        table="transactions",
        query="suspicious large withdrawal unusual location",
        filters={"amount__gte": 10000, "account_type": "checking-demo", "status": "flagged"},
        text_columns=["merchant_name", "description"],
        metadata_column="metadata",
        return_columns=["account_id", "status", "amount"],
        limit=5,
    )

    terminal.extend(
        [
            {"tone": "info", "text": f"Flagged search before resolution returned {len(flagged_before.results)} result(s)"},
            {"tone": "ok", "text": "Marked txn_demo_001 as verified in live SQL"},
            {"tone": "ok" if not flagged_after.results else "warn", "text": f"Flagged search after resolution returned {len(flagged_after.results)} result(s)"},
        ]
    )
    return _result_payload(
        "fintech",
        headline="Fraud queue reflects verified-state updates without a second vector write.",
        terminal=terminal,
        metrics={
            "before_count": len(flagged_before.results),
            "negative_count": len(flagged_after.results),
            "elapsed_ms": round((perf_counter() - started) * 1000, 1),
        },
        results={"before": _serialize_results(flagged_before.results), "negative": _serialize_results(flagged_after.results)},
    )


async def _run_ecommerce(client: Any) -> dict[str, Any]:
    started = perf_counter()
    terminal = [{"tone": "info", "text": "Bootstrapping products and inventory tables"}]

    await client.execute(
        """
        CREATE TABLE IF NOT EXISTS products (
            id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            description TEXT NOT NULL,
            price NUMERIC(10, 2),
            category VARCHAR(100),
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            embedding vector(768),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    await client.execute(
        """
        CREATE TABLE IF NOT EXISTS inventory (
            product_id BIGINT PRIMARY KEY,
            stock INTEGER NOT NULL,
            warehouse VARCHAR(100),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    await client.upsert_rows(
        table="products",
        rows=[
            {
                "id": 501,
                "name": "AeroFlex Runner",
                "description": "Comfortable running shoes for long city miles",
                "category": "demo-shoes",
                "price": 89.99,
                "metadata": {"scenario": "ecommerce", "color": "blue"},
            },
            {
                "id": 502,
                "name": "Trail Ridge Boot",
                "description": "Rugged hiking boot for steep wet trails",
                "category": "demo-boots",
                "price": 129.99,
                "metadata": {"scenario": "ecommerce", "color": "brown"},
            },
        ],
        embedding_source_column="description",
        id_column="id",
    )
    await client.execute(
        """
        INSERT INTO inventory (product_id, stock, warehouse)
        VALUES
            (:product_id_1, :stock_1, :warehouse_1),
            (:product_id_2, :stock_2, :warehouse_2)
        ON CONFLICT (product_id) DO UPDATE SET
            stock = EXCLUDED.stock,
            warehouse = EXCLUDED.warehouse,
            updated_at = NOW()
        """,
        {
            "product_id_1": 501,
            "stock_1": 5,
            "warehouse_1": "east",
            "product_id_2": 502,
            "stock_2": 0,
            "warehouse_2": "west",
        },
    )
    in_stock = await client.search_hybrid(
        table="products",
        query="comfortable running shoes",
        filters={"category": "demo-shoes", "price__lte": 100},
        text_columns=["name", "description"],
        metadata_column="metadata",
        return_columns=["name", "category", "price"],
        join_table="inventory",
        left_join_column="id",
        right_join_column="product_id",
        join_filter={"stock__gt": 0},
        limit=5,
    )
    await client.execute("UPDATE inventory SET stock = 0, updated_at = NOW() WHERE product_id = :product_id", {"product_id": 501})
    out_of_stock = await client.search_hybrid(
        table="products",
        query="comfortable running shoes",
        filters={"category": "demo-shoes", "price__lte": 100},
        text_columns=["name", "description"],
        metadata_column="metadata",
        return_columns=["name", "category", "price"],
        join_table="inventory",
        left_join_column="id",
        right_join_column="product_id",
        join_filter={"stock__gt": 0},
        limit=5,
    )

    terminal.extend(
        [
            {"tone": "ok", "text": "Seeded demo products and inventory rows"},
            {"tone": "info", "text": f"In-stock search before stockout returned {len(in_stock.results)} result(s)"},
            {"tone": "ok", "text": "Applied flash-sale stockout for product 501"},
            {"tone": "ok" if not out_of_stock.results else "warn", "text": f"In-stock search after stockout returned {len(out_of_stock.results)} result(s)"},
        ]
    )
    return _result_payload(
        "ecommerce",
        headline="Semantic product search follows live inventory without oversell lag.",
        terminal=terminal,
        metrics={
            "positive_count": len(in_stock.results),
            "negative_count": len(out_of_stock.results),
            "elapsed_ms": round((perf_counter() - started) * 1000, 1),
        },
        results={"positive": _serialize_results(in_stock.results), "negative": _serialize_results(out_of_stock.results)},
    )


def _serialize_results(results: list[Any]) -> list[dict[str, Any]]:
    return [
        {"id": result.id, "content": result.content, "score": result.score, "distance": result.distance, "payload": result.payload}
        for result in results
    ]


def _result_payload(
    scenario_id: str,
    *,
    headline: str,
    terminal: list[dict[str, str]],
    metrics: dict[str, Any],
    results: dict[str, Any],
) -> dict[str, Any]:
    return {"scenario_id": scenario_id, "headline": headline, "terminal_lines": terminal, "metrics": metrics, "results": results}
