"""Tests for ``ai_data_science_team.tools.f4_model_card`` (F4 tool layer)."""

from __future__ import annotations

import pytest

import ai_data_science_team.tools.f4_model_card as f4


@pytest.fixture(autouse=True)
def reset_registry():
    f4.CARD_REGISTRY.clear()
    yield
    f4.CARD_REGISTRY.clear()


class TestGenerateCard:
    def test_basic(self):
        c = f4.generate_card("m1")
        assert c.model_id == "m1"
        assert c.version == 1
        assert set(c.sections) == set(f4.CARD_SECTIONS)

    def test_sections_populated(self):
        c = f4.generate_card(
            "m2",
            details={"name": "xgb_churn", "version": "3"},
            intended_use="churn prediction",
            features=["recency", "frequency"],
            metrics={"auc": 0.91, "f1": 0.62},
            lineage=["dbt pipeline"],
            limitations="Sensitive to class drift.",
        )
        assert "xgb_churn" in c.sections["model_details"].content
        assert c.sections["intended_use"].content == "churn prediction"
        assert "recency" in c.sections["features"].content
        assert "auc" in c.sections["metrics"].content
        assert "dbt pipeline" in c.sections["lineage"].content
        assert c.sections["limitations"].is_draft is True
        assert c.sections["model_details"].is_draft is False


class TestUpdateSection:
    def test_version_increments(self):
        c = f4.generate_card("m1")
        c2 = f4.update_section(c, "intended_use", "loan default")
        assert c2.version == 2
        assert c2.card_id == c.card_id
        assert c2.sections["intended_use"].content == "loan default"

    def test_unknown_section_raises(self):
        c = f4.generate_card("m1")
        with pytest.raises(KeyError):
            f4.update_section(c, "not_a_section", "x")

    def test_no_increment(self):
        c = f4.generate_card("m1")
        c2 = f4.update_section(c, "intended_use", "x", increment_version=False)
        assert c2.version == 1


class TestToDict:
    def test_round_trip(self):
        c = f4.generate_card("m1", metrics={"auc": 0.9})
        d = c.to_dict()
        assert d["model_id"] == "m1"
        assert d["version"] == 1
        assert "metrics" in d["sections"]
        assert d["sections"]["metrics"]["content"].find("auc") != -1


class TestRender:
    def test_html(self):
        c = f4.generate_card("m1", intended_use="loan", metrics={"auc": 0.91})
        html = f4.render_html(c)
        assert "m1" in html
        assert "<h1>" in html
        assert "loan" in html

    def test_html_draft_marker(self):
        c = f4.generate_card("m1", limitations="drift")
        c = f4.update_section(c, "limitations", "drift", is_draft=True)
        html = f4.render_html(c)
        assert "DRAFT" in html

    def test_pdf_falls_back_to_html(self):
        c = f4.generate_card("m1")
        out = f4.render_pdf(c)
        # No weasyprint installed in this env → bytes are HTML.
        assert b"<html" in out


class TestRegistry:
    def test_get_card(self):
        c = f4.generate_card("m1")
        assert f4.get_card(c.card_id) is c

    def test_get_card_missing(self):
        with pytest.raises(KeyError):
            f4.get_card("nope")

    def test_list_cards(self):
        f4.generate_card("m1")
        f4.generate_card("m1")
        f4.generate_card("m2")
        assert len(f4.list_cards("m1")) == 2
        assert len(f4.list_cards("m2")) == 1


class TestToolRegistry:
    def test_present(self):
        names = f4.F4_MODEL_CARD_TOOL_NAMES
        for x in ("f4_generate_card", "f4_update_section",
                  "f4_render_html", "f4_render_pdf",
                  "f4_list_cards"):
            assert x in names
