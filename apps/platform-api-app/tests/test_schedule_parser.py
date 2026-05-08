"""Unit tests for the natural language schedule parser."""

from __future__ import annotations

import pytest

from platform_api.scheduler.schedule_parser import ScheduleParser


class TestScheduleParser:
    """Tests for ScheduleParser class."""

    @pytest.fixture
    def parser(self) -> ScheduleParser:
        return ScheduleParser()

    @pytest.mark.parametrize(
        ("expression", "expected_cron"),
        [
            ("her gün 09:00'da", "09 9 * * *"),
            ("her gün saat 09:00", "00 9 * * *"),
            ("every day at 9am", "00 9 * * *"),
            ("every day at 9:30", "30 9 * * *"),
            ("every day at 9:30pm", "30 21 * * *"),
            ("every day at 12pm", "00 12 * * *"),
            ("every day at 12am", "00 0 * * *"),
        ],
    )
    def test_parse_daily_time(
        self,
        parser: ScheduleParser,
        expression: str,
        expected_cron: str,
    ) -> None:
        result = parser.parse(expression)
        assert result == expected_cron

    @pytest.mark.parametrize(
        ("expression", "expected_cron"),
        [
            ("her pazartesi 10:30'da", "30 10 * * MON"),
            ("her salı 09:00'da", "00 9 * * TUE"),
            ("every monday at 10:30", "30 10 * * MON"),
            ("every friday at 5pm", "00 17 * * FRI"),
            ("every saturday at 9am", "00 9 * * SAT"),
        ],
    )
    def test_parse_weekly_time(
        self,
        parser: ScheduleParser,
        expression: str,
        expected_cron: str,
    ) -> None:
        result = parser.parse(expression)
        assert result == expected_cron

    @pytest.mark.parametrize(
        ("expression", "expected_cron"),
        [
            ("her 4 saatte bir", "0 */4 * * *"),
            ("her 2 saatte bir", "0 */2 * * *"),
            ("every 2 hours", "0 */2 * * *"),
            ("every 6 hours", "0 */6 * * *"),
        ],
    )
    def test_parse_every_n_hours(
        self,
        parser: ScheduleParser,
        expression: str,
        expected_cron: str,
    ) -> None:
        result = parser.parse(expression)
        assert result == expected_cron

    @pytest.mark.parametrize(
        ("expression", "expected_cron"),
        [
            ("her 30 dakikada bir", "*/30 * * * *"),
            ("her 15 dakikada bir", "*/15 * * * *"),
            ("every 15 minutes", "*/15 * * * *"),
            ("every 5 minutes", "*/5 * * * *"),
        ],
    )
    def test_parse_every_n_minutes(
        self,
        parser: ScheduleParser,
        expression: str,
        expected_cron: str,
    ) -> None:
        result = parser.parse(expression)
        assert result == expected_cron

    @pytest.mark.parametrize(
        ("expression", "expected_cron"),
        [
            ("her saat", "0 * * * *"),
            ("hourly", "0 * * * *"),
            ("every hour", "0 * * * *"),
        ],
    )
    def test_parse_hourly(
        self,
        parser: ScheduleParser,
        expression: str,
        expected_cron: str,
    ) -> None:
        result = parser.parse(expression)
        assert result == expected_cron

    @pytest.mark.parametrize(
        ("expression", "expected_cron"),
        [
            ("her gün", "0 9 * * *"),
            ("daily", "0 9 * * *"),
            ("every day", "0 9 * * *"),
        ],
    )
    def test_parse_daily(
        self,
        parser: ScheduleParser,
        expression: str,
        expected_cron: str,
    ) -> None:
        result = parser.parse(expression)
        assert result == expected_cron

    @pytest.mark.parametrize(
        ("expression", "expected_cron"),
        [
            ("her hafta", "0 9 * * MON"),
            ("weekly", "0 9 * * MON"),
            ("every week", "0 9 * * MON"),
        ],
    )
    def test_parse_weekly(
        self,
        parser: ScheduleParser,
        expression: str,
        expected_cron: str,
    ) -> None:
        result = parser.parse(expression)
        assert result == expected_cron

    @pytest.mark.parametrize(
        ("expression", "expected_cron"),
        [
            ("her ay", "0 9 1 * *"),
            ("monthly", "0 9 1 * *"),
            ("every month", "0 9 1 * *"),
        ],
    )
    def test_parse_monthly(
        self,
        parser: ScheduleParser,
        expression: str,
        expected_cron: str,
    ) -> None:
        result = parser.parse(expression)
        assert result == expected_cron

    @pytest.mark.parametrize(
        "expression",
        [
            "0 9 * * *",
            "*/15 * * * *",
            "0 */4 * * *",
            "30 10 * * MON",
            "0 8 * * 1-5",
        ],
    )
    def test_parse_direct_cron(
        self,
        parser: ScheduleParser,
        expression: str,
    ) -> None:
        result = parser.parse(expression)
        assert result == expression

    def test_parse_empty_raises_error(self, parser: ScheduleParser) -> None:
        with pytest.raises(ValueError, match="Empty schedule expression"):
            parser.parse("")

    def test_parse_invalid_raises_error(self, parser: ScheduleParser) -> None:
        with pytest.raises(ValueError, match="Cannot parse schedule"):
            parser.parse("this is not a valid schedule")

    def test_is_valid_cron(self, parser: ScheduleParser) -> None:
        assert parser._is_valid_cron("0 9 * * *") is True
        assert parser._is_valid_cron("*/15 * * * *") is True
        assert parser._is_valid_cron("0 */4 * * *") is True
        assert parser._is_valid_cron("30 10 * * MON") is True
        assert parser._is_valid_cron("0 8 * * 1-5") is True
        assert parser._is_valid_cron("invalid") is False
        assert parser._is_valid_cron("0 9 *") is False

    def test_parse_with_description(self, parser: ScheduleParser) -> None:
        cron, description = parser.parse_with_description("her gün 09:00'da")
        assert cron == "09 9 * * *"
        assert description is not None
