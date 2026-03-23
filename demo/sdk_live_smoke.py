import asyncio
import os

from alloynative import AlloyIndex


async def main() -> None:
    index = await AlloyIndex.aconnect(
        table="products",
        project_id=os.environ["ALLOYNATIVE_PROJECT_ID"],
        region=os.environ["ALLOYNATIVE_REGION"],
        cluster=os.environ["ALLOYNATIVE_CLUSTER"],
        instance=os.environ["ALLOYNATIVE_INSTANCE"],
        database=os.environ["ALLOYNATIVE_DATABASE"],
        db_user=os.environ["ALLOYNATIVE_DB_USER"],
        text_columns=["name", "description"],
        metadata_column="metadata",
        embedding_column="embedding",
        embedding_source_column="description",
    )

    print("Capabilities:", index.capabilities)

    await index.upsert(
        [
            {
                "id": 1,
                "name": "Lightweight Running Shoe",
                "description": "Breathable daily trainer for road running",
                "category": "shoes",
                "price": 79.99,
                "metadata": {"brand": "demo", "color": "blue"},
            }
        ]
    )

    results = await index.query(
        "comfortable running shoes",
        filters={"category": "shoes", "price__lte": 100},
        limit=5,
    )

    print("Result count:", len(results.results))
    for item in results.results:
        print(item)

    await index.close()


asyncio.run(main())
