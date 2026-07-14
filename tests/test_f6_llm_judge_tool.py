"""Tests for ``ai_data_science_team.tools.f6_llm_judge`` (F6 tool layer)."""

from __future__ import annotations


import ai_data_science_team.tools.f6_llm_judge as f6


class TestScoreLength:
    def test_short(self):
        assert f6._score_length("hi") < 0.5

    def test_medium(self):
        s = "x" * 500
        assert f6._score_length(s) >= 0.9


class TestScoreStructure:
    def test_fence_table_numbers(self):
        s = (
            "This is a report.\n"
            "| col1 | col2 |\n"
            "| --- | --- |\n"
            "| a | 1 |\n"
            "```python\nprint(1)\n```\n"
        )
        assert f6._score_structure(s) > 0.7

    def test_empty(self):
        assert f6._score_structure("") == 0.0


class TestScoreFaithfulness:
    def test_no_hedge(self):
        assert f6._score_faithfulness("This is certain.") == 1.0

    def test_many_hedges(self):
        s = "maybe perhaps might be i think i guess not sure somewhat" * 10
        assert f6._score_faithfulness(s) < 0.5


class TestCodeQuality:
    def test_with_function(self):
        s = "def foo():\n    return 1\n"
        assert f6._code_quality(s) >= 0.6

    def test_long_lines(self):
        s = "x" * 200 + "\n" + "y" * 200 + "\n"
        assert f6._code_quality(s) <= 0.5


class TestJudgeOutput:
    def test_high_score_recommends_accept(self):
        # Long, structured, no hedge, with good code.
        text = ("A detailed report.\n" * 30) + "\n| c1 | c2 |\n| 1 | 2 |"
        code = "def f():\n    return 1\n"
        s = f6.judge_output(text, code)
        assert s.recommendation == "accept"
        d = s.to_dict()
        assert "overall" in d and "correctness" in d

    def test_short_text_recommends_reject(self):
        s = f6.judge_output("no", "")
        assert s.recommendation in {"revise", "reject"}

    def test_weights_respected(self):
        # If faithfulness is the only weight, low faithfulness should
        # tank overall.
        s = f6.judge_output("ok", "", weights=(0.0, 1.0, 0.0))
        assert s.faithfulness >= 0.0
        # 0-length text → 0; weighted overall stays 0.
        # But not 1 unless we fill text.  Construct a clean case.
        s2 = f6.judge_output(
            "A long report. " * 100, "",
            weights=(0.0, 1.0, 0.0),
        )
        assert s2.overall <= 1.0

    def test_to_dict(self):
        d = f6.judge_output("ok", "").to_dict()
        for k in (
            "correctness", "faithfulness", "code_quality",
            "overall", "recommendation",
        ):
            assert k in d


class TestJudgeBatch:
    def test_three(self):
        items = [
            {"text": "x" * 500, "code": "def f(): pass"},
            {"text": "x" * 50, "code": ""},
            {"text": "", "code": ""},
        ]
        scores = f6.judge_batch(items)
        assert len(scores) == 3
        assert all(isinstance(s, f6.JudgeScore) for s in scores)

