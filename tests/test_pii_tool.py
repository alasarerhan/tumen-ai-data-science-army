"""Tests for ``ai_data_science_team.tools.pii`` (B5 tool layer)."""

from __future__ import annotations

import re

import numpy as np
import pandas as pd
import pytest

from ai_data_science_team.tools.pii import (
    anonymize_dataframe,
    default_strategies_for,
    scan_pii,
)


# ---------------------------------------------------------------------------
# Scan
# ---------------------------------------------------------------------------


class TestScanPII:
    def test_email_detected(self):
        df = pd.DataFrame(
            {"email": [f"user{i}@example.com" for i in range(20)]}
        )
        r = scan_pii(df)
        assert "email" in r.pii_columns
        f = next(x for x in r.findings if x.column == "email")
        assert f.pii_type == "EMAIL_ADDRESS"
        assert f.severity == "high"

    def test_tckn_detected_by_pattern(self):
        # 11-digit numbers; many noisy entries reduce match ratio
        # intentionally — the name hint upgrades the signal.
        nums = ["12345678901"] * 5 + ["00000"] * 15
        df = pd.DataFrame({"tckn": nums})
        r = scan_pii(df)
        # Either by name hint or because of the strong pattern match.
        f = next(x for x in r.findings if x.column == "tckn")
        assert f.pii_type == "TR_ID_NUMBER"

    def test_tckn_detected_by_name_only(self):
        # Column name triggers detection even with mixed values.
        df = pd.DataFrame({"customer_tckn": [str(i) for i in range(20)]})
        r = scan_pii(df)
        assert "customer_tckn" in r.pii_columns

    def test_phone_detected(self):
        phones = [
            "+905551234567", "05551234567", "0 555 123 45 67", "5551234567",
        ] + ["n/a"] * 16
        df = pd.DataFrame({"phone": phones})
        r = scan_pii(df)
        assert "phone" in r.pii_columns

    def test_no_pii_returns_zero_findings(self):
        df = pd.DataFrame(
            {
                "transaction_id": [f"tx-{i:06d}" for i in range(50)],
                "amount": np.linspace(10, 500, 50),
            }
        )
        r = scan_pii(df)
        assert r.pii_columns == []

    def test_sample_rows_limits_work(self):
        df = pd.DataFrame({"email": ["a@b.com"] * 100})
        r = scan_pii(df, sample_rows=10)
        # n_rows_scanned should reflect the sample cap.
        assert r.n_rows_scanned == 10

    def test_internal_columns_skipped(self):
        df = pd.DataFrame(
            {
                "__rowid__": range(5),
                "email": ["a@b.com"] * 5,
            }
        )
        r = scan_pii(df)
        cols = [f.column for f in r.findings]
        assert "__rowid__" not in cols
        assert "email" in cols

    def test_to_dict_round_trip(self):
        df = pd.DataFrame({"email": ["a@b.com"] * 5})
        r = scan_pii(df)
        d = r.to_dict()
        assert "findings" in d
        assert "pii_columns" in d


# ---------------------------------------------------------------------------
# Default strategies
# ---------------------------------------------------------------------------


class TestDefaultStrategies:
    def test_tckn_defaults_to_hash(self):
        df = pd.DataFrame({"tckn": ["12345678901"] * 10})
        scan = scan_pii(df)
        strategies = default_strategies_for(scan)
        assert strategies["tckn"]["strategy"] == "hash"

    def test_email_defaults_to_mask(self):
        df = pd.DataFrame({"email": ["a@b.com"] * 10})
        scan = scan_pii(df)
        strategies = default_strategies_for(scan)
        # Email defaults to a mask-flavoured strategy (mask or mask_email).
        assert strategies["email"]["strategy"].startswith("mask")

    def test_no_pii_no_strategies(self):
        df = pd.DataFrame({"x": ["a", "b", "c"]})
        scan = scan_pii(df)
        strategies = default_strategies_for(scan)
        assert strategies == {}


# ---------------------------------------------------------------------------
# Anonymisation
# ---------------------------------------------------------------------------


class TestAnonymizeDataframe:
    def test_email_mask(self):
        df = pd.DataFrame({"email": ["user@example.com"]})
        out = anonymize_dataframe(
            df,
            {"email": {"pii_type": "EMAIL_ADDRESS", "strategy": "mask"}},
        )
        assert out.df["email"][0] == "***@***"

    def test_email_mask_keep_domain(self):
        df = pd.DataFrame({"email": ["user@example.com"]})
        out = anonymize_dataframe(
            df,
            {
                "email": {
                    "pii_type": "EMAIL_ADDRESS",
                    "strategy": "mask",
                    "params": {"keep_domain": True},
                }
            },
        )
        assert out.df["email"][0] == "***@example.com"

    def test_hash_deterministic(self):
        df = pd.DataFrame({"x": ["12345678901"]})
        out1 = anonymize_dataframe(
            df,
            {"x": {"pii_type": "TR_ID_NUMBER", "strategy": "hash"}},
        )
        out2 = anonymize_dataframe(
            df,
            {"x": {"pii_type": "TR_ID_NUMBER", "strategy": "hash"}},
        )
        assert out1.df["x"][0] == out2.df["x"][0]
        # Default sha256 hash should produce a 16-char hex.
        assert re.match(r"^[a-f0-9]{16}$", out1.df["x"][0]) is not None

    def test_hash_with_salt_changes_value(self):
        df = pd.DataFrame({"x": ["12345678901"]})
        out1 = anonymize_dataframe(
            df,
            {
                "x": {
                    "pii_type": "TR_ID_NUMBER",
                    "strategy": "hash",
                    "params": {"salt": "abc"},
                }
            },
        )
        out2 = anonymize_dataframe(
            df,
            {"x": {"pii_type": "TR_ID_NUMBER", "strategy": "hash"}},
        )
        assert out1.df["x"][0] != out2.df["x"][0]

    def test_tokenize_uses_token_prefix(self):
        df = pd.DataFrame({"x": ["foo"]})
        out = anonymize_dataframe(
            df,
            {"x": {"pii_type": "PERSON", "strategy": "tokenize"}},
        )
        assert out.df["x"][0].startswith("<TOK_")
        assert out.df["x"][0].endswith(">")

    def test_drop_replaces_with_empty(self):
        df = pd.DataFrame({"x": ["foo", "bar"]})
        out = anonymize_dataframe(
            df,
            {"x": {"pii_type": "PERSON", "strategy": "drop"}},
        )
        assert all(out.df["x"] == "")

    def test_unknown_column_does_nothing(self):
        df = pd.DataFrame({"x": ["foo"]})
        out = anonymize_dataframe(
            df,
            {"missing_col": {"pii_type": "PERSON", "strategy": "hash"}},
        )
        assert out.df["x"][0] == "foo"
        assert len([a for a in out.actions if a["column"] == "missing_col"]) == 0

    def test_actions_recorded(self):
        df = pd.DataFrame({"a": ["foo@bar.com"], "b": ["x"]})
        out = anonymize_dataframe(
            df,
            {
                "a": {"pii_type": "EMAIL_ADDRESS", "strategy": "mask"},
            },
        )
        cols = [a["column"] for a in out.actions]
        assert "a" in cols
        for a in out.actions:
            if a["column"] == "a":
                assert a["rows_changed"] == 1

    def test_fail_on_unhandled_pii(self):
        df = pd.DataFrame(
            {"email": ["a@b.com"] * 10, "other": [str(i) for i in range(10)]}
        )
        scan = scan_pii(df)
        with pytest.raises(ValueError):
            anonymize_dataframe(
                df,
                {"other": {"pii_type": "CUSTOM", "strategy": "hash"}},
                scan=scan,
                fail_on_unhandled_pii=True,
            )

    def test_fail_disabled_warns(self):
        df = pd.DataFrame(
            {"email": ["a@b.com"] * 10, "other": [str(i) for i in range(10)]}
        )
        scan = scan_pii(df)
        out = anonymize_dataframe(
            df,
            {"other": {"pii_type": "CUSTOM", "strategy": "hash"}},
            scan=scan,
            fail_on_unhandled_pii=False,
        )
        warnings = [a for a in out.actions if "warning" in a]
        assert any("email" in a.get("column", "") for a in warnings)
        assert "email" in out.failed_columns

    def test_to_dict_shape(self):
        df = pd.DataFrame({"a": ["x"]})
        out = anonymize_dataframe(
            df,
            {"a": {"pii_type": "PERSON", "strategy": "mask"}},
        )
        d = out.to_dict()
        assert "actions" in d
        assert "failed_columns" in d
