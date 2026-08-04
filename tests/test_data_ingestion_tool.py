"""
Tests for ``ai_data_science_team.tools.data_ingestion`` (B7 tool layer).
"""

from __future__ import annotations

import pandas as pd

from ai_data_science_team.tools.data_ingestion import (
    compute_watermark,
    incremental_diff,
    record_run,
    register_ingest_job,
)


class TestRegisterJob:
    def test_minimal_job(self):
        job = register_ingest_job(
            name="daily_orders",
            source="snowflake.public.orders",
            target="warehouse.orders",
        )
        assert job["name"] == "daily_orders"
        assert job["source"] == "snowflake.public.orders"
        assert job["target"] == "warehouse.orders"
        assert job["incremental_key"] is None
        assert len(job["job_id"]) > 10

    def test_full_job(self):
        job = register_ingest_job(
            name="customers",
            source="postgres.public.users",
            target="warehouse.customers",
            incremental_key="updated_at",
            schedule="0 * * * *",
            created_at="2026-07-13T10:00:00Z",
        )
        assert job["incremental_key"] == "updated_at"
        assert job["schedule"] == "0 * * * *"
        assert job["created_at"] == "2026-07-13T10:00:00Z"


class TestComputeWatermark:
    def test_basic(self):
        wm = compute_watermark(
            "job1", "2026-07-13T01:00:00Z", "2026-07-13T02:00:00Z", delta_rows=200
        )
        d = wm.to_dict()
        assert d["job_id"] == "job1"
        assert d["next_high_water"] == "2026-07-13T02:00:00Z"
        assert d["delta_rows"] == 200


class TestIncrementalDiff:
    def test_additions_removals_by_key(self):
        baseline = pd.DataFrame({"id": [1, 2, 3], "v": ["a", "b", "c"]})
        current = pd.DataFrame({"id": [1, 2, 4], "v": ["a", "b2", "d"]})
        diff = incremental_diff(baseline, current, key_columns=["id"], compare_columns=["v"])
        # 4 not in baseline ⇒ added
        assert (4,) in diff["added"]
        # 3 not in current ⇒ removed
        assert (3,) in diff["removed"]
        # 2 differs in v ⇒ changed
        assert (2,) in diff["changed"]
        # 1 unchanged ⇒ not in any bucket


class TestRecordRun:
    def test_success_row(self):
        row = record_run(
            job_id="job1",
            run_id="r1",
            status="success",
            started_at="2026-07-13T10:00:00Z",
            finished_at="2026-07-13T10:00:30Z",
            rows_loaded=150,
        )
        assert row["job_id"] == "job1"
        assert row["rows_loaded"] == 150

    def test_failed_row(self):
        row = record_run(
            job_id="job1",
            run_id="r2",
            status="failed",
            started_at="2026-07-13T10:00:00Z",
            error="connection refused",
        )
        assert row["status"] == "failed"
        assert "connection" in row["error"]
