"""Tests for AlloyNative SQL builders."""

from unittest import TestCase

from alloynative.sql import (
    build_search_hybrid_statement,
    build_upsert_raw_text_statement,
    build_upsert_rows_statement,
)


class SQLBuilderTest(TestCase):
    """Assert that the generated SQL encodes the core AlloyNative behavior."""

    def test_build_upsert_raw_text_statement_uses_in_database_embeddings(self) -> None:
        statement = build_upsert_raw_text_statement(
            table="documents",
            texts=["hello world"],
            metadata=[{"source": "demo"}],
            embedding_model="text-embedding-005",
            id_column="id",
            ids=["doc-1"],
        )

        self.assertIn("google_ml.embedding(:embedding_model, :content_0)::vector", statement.sql)
        self.assertIn('ON CONFLICT ("id") DO UPDATE SET', statement.sql)
        self.assertEqual(statement.params["embedding_model"], "text-embedding-005")
        self.assertEqual(statement.params["id_0"], "doc-1")

    def test_build_search_hybrid_statement_contains_rrf_search(self) -> None:
        statement = build_search_hybrid_statement(
            table="documents",
            query="running shoes",
            filters={"category": "shoes", "price__lte": 100},
            limit=10,
            embedding_model="text-embedding-005",
            text_columns=["title", "body"],
            return_columns=["title", "category", "price"],
            metadata_column=None,
        )

        self.assertIn("WITH candidates AS (WITH vector_search AS", statement.sql)
        self.assertIn("FULL OUTER JOIN text_search", statement.sql)
        self.assertIn("google_ml.embedding(:embedding_model, :query_text)::vector", statement.sql)
        self.assertIn("concat_ws(' ', COALESCE(\"title\"::text, ''), COALESCE(\"body\"::text, ''))", statement.sql)
        self.assertIn("jsonb_build_object('title', \"title\", 'category', \"category\", 'price', \"price\")", statement.sql)
        self.assertEqual(statement.params["filter_0"], "shoes")
        self.assertEqual(statement.params["filter_1"], 100)

    def test_build_search_hybrid_statement_supports_join_constrained_search(self) -> None:
        statement = build_search_hybrid_statement(
            table="products",
            query="running shoes",
            filters={"category": "shoes"},
            join_table="inventory",
            left_join_column="id",
            right_join_column="product_id",
            join_filter={"stock__gt": 0},
            limit=10,
            embedding_model="text-embedding-005",
            text_columns=["name", "description"],
            return_columns=["name", "category", "price"],
            metadata_column=None,
        )

        self.assertIn('INNER JOIN "inventory" AS joined', statement.sql)
        self.assertIn('base."id" = joined."product_id"', statement.sql)
        self.assertIn('joined."stock" > :join_filter_0', statement.sql)
        self.assertEqual(statement.params["join_filter_0"], 0)

    def test_build_search_hybrid_statement_contains_predict_row_when_reranking(self) -> None:
        statement = build_search_hybrid_statement(
            table="documents",
            query="running shoes",
            filters=None,
            limit=5,
            embedding_model="text-embedding-005",
            rerank=True,
            rerank_model="gemini_flash_model",
        )

        self.assertIn("google_ml.predict_row(", statement.sql)
        self.assertIn("::jsonb -> 0 -> 'candidates'", statement.sql)
        self.assertEqual(statement.params["rerank_model"], "gemini_flash_model")

    def test_build_upsert_rows_statement_supports_arbitrary_schema(self) -> None:
        statement = build_upsert_rows_statement(
            table="products",
            rows=[
                {
                    "id": 1,
                    "name": "Shoe",
                    "description": "Lightweight trainer",
                    "category": "shoes",
                    "price": 79.99,
                    "metadata": {"brand": "demo"},
                }
            ],
            embedding_source_column="description",
            embedding_model="text-embedding-005",
            embedding_column="embedding",
            id_column="id",
        )

        self.assertIn("INSERT INTO \"products\"", statement.sql)
        self.assertIn("google_ml.embedding(:embedding_model, :row_0_2)::vector", statement.sql)
        self.assertIn("ON CONFLICT (\"id\") DO UPDATE SET", statement.sql)
        self.assertEqual(statement.params["row_0_2"], "Lightweight trainer")
        self.assertEqual(
            statement.params["row_0_5"],
            '{"brand": "demo"}',
        )
        self.assertIn("CAST(:row_0_5 AS jsonb)", statement.sql)

    def test_build_search_hybrid_statement_requires_explicit_join_columns(self) -> None:
        with self.assertRaisesRegex(Exception, "left_join_column and right_join_column"):
            build_search_hybrid_statement(
                table="products",
                query="running shoes",
                filters=None,
                limit=5,
                embedding_model="text-embedding-005",
                join_table="inventory",
            )
