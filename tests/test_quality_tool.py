"""
Tests for ``ai_data_science_team.tools.quality`` (B2 tool layer).
"""

from __future__ import annotations


import numpy as np
import pandas as pd
import pytest

from ai_data_science_team.tools.quality import (
    expectation_suite_from_template,
    summarise_suite_run,
    validate_against_suite,
)


def _customer_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "id": [1, 2, 3, 4, 5],
            "email": ["a@x.com", "b@x.com", "c@x.com", "d@x.com", "e@x.com"],
            "age": [25, 30, 17, 200, 99],  # 200 is out of [0, 130]
        }
    )


def _transactions_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "transaction_id": ["t1", "t2", "t1", "t4", "t5"],  # t1 duplicate
            "amount": [10.0, 20.0, 30.0, 1_500_000.0, None],  # 1.5M out; one null
        }
    )


class TestExpectationSuiteFromTemplate:
    def test_customer_default_includes_relevant_columns(self):
        df = _customer_df()
        suite = expectation_suite_from_template("customer_default", df)
        cols = [r["column"] for r in suite]
        assert "id" in cols
        assert "email" in cols
        assert "age" in cols

    def test_unknown_template_raises(self):
        df = _customer_df()
        with pytest.raises(ValueError):
            expectation_suite_from_template("not_a_real_template", df)

    def test_overrides_apply_to_indexed_rule(self):
        df = _customer_df()
        # In customer_default, index 2 is age value_range — make it stricter.
        overrides = {"2": {"min": 18, "max": 65}}
        suite = expectation_suite_from_template(
            "customer_default", df, overrides
        )
        assert suite[2]["min"] == 18
        assert suite[2]["max"] == 65


class TestValidateAgainstSuiteNotNull:
    def test_clean_column_passes(self):
        df = pd.DataFrame({"a": [1, 2, 3, 4]})
        suite = [{"kind": "not_null", "column": "a"}]
        result = validate_against_suite(df, suite)
        assert result["passed"] == 1
        assert result["failed"] == 0

    def test_nulls_fail_when_severity_fail(self):
        df = pd.DataFrame({"a": [1, np.nan, 3]})
        suite = [{"kind": "not_null", "column": "a"}]
        result = validate_against_suite(df, suite)
        assert result["failed"] == 1
        assert result["rules"][0]["violations"] == [1]


class TestValidateAgainstSuiteUnique:
    def test_unique_passes(self):
        df = pd.DataFrame({"a": [1, 2, 3, 4]})
        suite = [{"kind": "unique", "column": "a"}]
        result = validate_against_suite(df, suite)
        assert result["passed"] == 1

    def test_duplicates_fail(self):
        df = _transactions_df()
        suite = [{"kind": "unique", "column": "transaction_id"}]
        result = validate_against_suite(df, suite)
        assert result["failed"] == 1


class TestValidateAgainstSuiteColumnType:
    def test_object_match(self):
        df = pd.DataFrame({"a": ["x", "y"]})
        suite = [{"kind": "column_type", "column": "a", "dtype": "object"}]
        result = validate_against_suite(df, suite)
        assert result["passed"] == 1

    def test_int_mismatch(self):
        df = pd.DataFrame({"a": [1.0, 2.0]})  # float
        suite = [{"kind": "column_type", "column": "a", "dtype": "int"}]
        result = validate_against_suite(df, suite)
        assert result["failed"] == 1


class TestValidateAgainstSuiteValueRange:
    def test_in_range(self):
        df = pd.DataFrame({"a": [1, 2, 3]})
        suite = [{"kind": "value_range", "column": "a", "min": 0, "max": 10}]
        result = validate_against_suite(df, suite)
        assert result["passed"] == 1

    def test_out_of_range_with_customer(self):
        df = _customer_df()
        suite = [
            {
                "kind": "value_range",
                "column": "age",
                "min": 0,
                "max": 130,
            }
        ]
        result = validate_against_suite(df, suite)
        assert result["failed"] == 1
        assert 3 in result["rules"][0]["violations"]  # age=200 row index


class TestValidateAgainstSuiteNullRate:
    def test_below_max(self):
        df = pd.DataFrame({"a": [1, 2, None, 4]})
        suite = [{"kind": "null_rate", "column": "a", "max_null_rate": 0.30}]
        result = validate_against_suite(df, suite)
        assert result["passed"] == 1

    def test_warning_threshold(self):
        # null_rate ~ 0.20 > 0.05 ⇒ failed but with severity=warning
        df = pd.DataFrame({"a": [None, None, 4, 5, 6]})  # 2/5 = 0.4
        suite = [
            {
                "kind": "null_rate",
                "column": "a",
                "max_null_rate": 0.05,
                "severity": "warning",
            }
        ]
        result = validate_against_suite(df, suite)
        assert result["warning"] == 1
        assert result["failed"] == 0


class TestValidateAgainstSuiteRegex:
    def test_email_pattern_passes(self):
        df = pd.DataFrame({"email": ["a@x.com", "b@y.org"]})
        suite = [
            {
                "kind": "regex_match",
                "column": "email",
                "pattern": r"[^@]+@[^@]+\.[^@]+",
            }
        ]
        result = validate_against_suite(df, suite)
        assert result["passed"] == 1

    def test_pattern_rejects(self):
        df = pd.DataFrame({"email": ["good@x.com", "not-an-email"]})
        suite = [
            {
                "kind": "regex_match",
                "column": "email",
                "pattern": r"[^@]+@[^@]+",
            }
        ]
        result = validate_against_suite(df, suite)
        assert result["failed"] == 1


class TestMissingColumn:
    def test_missing_column_is_skipped(self):
        df = pd.DataFrame({"a": [1, 2, 3]})
        suite = [{"kind": "not_null", "column": "not_in_df"}]
        result = validate_against_suite(df, suite)
        assert result["skipped"] == 1


class TestUnknownRule:
    def test_unknown_kind_is_error(self):
        df = pd.DataFrame({"a": [1, 2]})
        suite = [{"kind": "no_such_kind", "column": "a"}]
        result = validate_against_suite(df, suite)
        assert result["errors"] == 1


class TestSummariseSuiteRun:
    def test_passed_summary(self):
        df = pd.DataFrame({"a": [1, 2, 3]})
        suite = [{"kind": "not_null", "column": "a"}]
        result = validate_against_suite(df, suite)
        summary = summarise_suite_run(result)
        assert summary["status"] == "passed"
        assert "PASSED" in summary["summary"]

    def test_failed_summary(self):
        df = pd.DataFrame({"a": [1, None]})
        suite = [{"kind": "not_null", "column": "a"}]
        result = validate_against_suite(df, suite)
        summary = summarise_suite_run(result)
        assert summary["status"] == "failed"
        assert summary["failed_severity"] == "fail"

    def test_warning_only_summary(self):
        df = pd.DataFrame({"a": [1, None, None, 3]})  # 50% null
        suite = [
            {
                "kind": "null_rate",
                "column": "a",
                "max_null_rate": 0.10,
                "severity": "warning",
            }
        ]
        result = validate_against_suite(df, suite)
        summary = summarise_suite_run(result)
        assert summary["status"] == "warning"

    def test_skipped_summary(self):
        pd.DataFrame({"a": [1]})
        result = {"passed": 0, "failed": 0, "warning": 0, "skipped": 1, "errors": 0, "dataset_shape": [1, 1]}
        summary = summarise_suite_run(result)
        assert summary["status"] == "skipped"


class TestEndToEndCustomerSuite:
    def test_full_suite_with_one_intentional_violation(self):
        df = _customer_df()  # age=200 violates the [0, 130] range rule
        suite = expectation_suite_from_template("customer_default", df)
        # Tighten age range so 200 fails explicitly.
        suite[2] = {**suite[2], "min": 0, "max": 130}
        result = validate_against_suite(df, suite)
        # We expect: id not_null = pass; email not_null = pass;
        # age value_range = fail; id unique = pass.
        assert result["failed"] == 1
        assert result["passed"] == 3
        summary = summarise_suite_run(result)
        assert summary["status"] == "failed"
