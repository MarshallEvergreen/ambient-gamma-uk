"""Tests for annual year data models."""

import datetime

import pytest
from pydantic import ValidationError
from uk_rimnet_core.models import (
    MonthlyData,
    MonthlyYearData,
    PreMobileYearData,
    QuarterlyData,
    QuarterlyYearData,
    TransitionYearData,
)

_CURRENT_YEAR: int = datetime.datetime.now(tz=datetime.UTC).year


class TestPreMobileYearData:  # noqa: D101
    def _quarterly(self) -> QuarterlyData:
        return QuarterlyData(
            q1="/p/q1.csv",
            q2="/p/q2.csv",
            q3="/p/q3.csv",
            q4="/p/q4.csv",
        )

    def test_valid(self) -> None:
        # Arrange
        quarterly = self._quarterly()

        # Act / Assert
        PreMobileYearData(year=2014, fixed=quarterly)

    def test_raises_when_year_is_in_mobile_era(self) -> None:
        # 2016 is the first year with mobile monitoring
        # Arrange
        quarterly = self._quarterly()

        # Act / Assert
        with pytest.raises(ValidationError):
            PreMobileYearData(year=2016, fixed=quarterly)

    def test_raises_when_year_is_in_quarterly_era(self) -> None:
        # Arrange
        quarterly = self._quarterly()

        # Act / Assert
        with pytest.raises(ValidationError):
            PreMobileYearData(year=2018, fixed=quarterly)


class TestQuarterlyYearData:  # noqa: D101
    def _quarterly(self) -> QuarterlyData:
        return QuarterlyData(
            q1="/p/q1.csv",
            q2="/p/q2.csv",
            q3="/p/q3.csv",
            q4="/p/q4.csv",
        )

    def test_valid(self) -> None:
        # Arrange
        quarterly = self._quarterly()

        # Act / Assert
        QuarterlyYearData(year=2018, fixed=quarterly, mobile=quarterly)

    def test_raises_when_year_is_before_mobile_era(self) -> None:
        # 2015 predates mobile monitoring
        # Arrange
        quarterly = self._quarterly()

        # Act / Assert
        with pytest.raises(ValidationError):
            QuarterlyYearData(year=2015, fixed=quarterly, mobile=quarterly)

    def test_raises_when_year_is_transition_year(self) -> None:
        # 2022 belongs to TransitionYearData, not QuarterlyYearData
        # Arrange
        quarterly = self._quarterly()

        # Act / Assert
        with pytest.raises(ValidationError):
            QuarterlyYearData(year=2022, fixed=quarterly, mobile=quarterly)


class TestTransitionYearData:  # noqa: D101
    def _quarterly_h1(self) -> QuarterlyData:
        return QuarterlyData(q1="/p/q1.csv", q2="/p/q2.csv")

    def _monthly_h2(self) -> MonthlyData:
        return MonthlyData(
            jul="/p/jul.csv",
            aug="/p/aug.csv",
            sep="/p/sep.csv",
            oct="/p/oct.csv",
            nov="/p/nov.csv",
            dec="/p/dec.csv",
        )

    def test_valid(self) -> None:
        # Arrange
        quarterly = self._quarterly_h1()
        monthly = self._monthly_h2()

        # Act / Assert
        TransitionYearData(
            quarterly_fixed=quarterly,
            quarterly_mobile=quarterly,
            monthly_fixed=monthly,
            monthly_mobile=monthly,
        )

    def test_raises_when_quarterly_data_includes_q3(self) -> None:
        # q3 in the quarterly files conflicts with the monthly data already covering Q3
        # Arrange
        bad_quarterly = QuarterlyData(q1="/p/q1.csv", q2="/p/q2.csv", q3="/p/q3.csv")
        monthly = self._monthly_h2()

        # Act / Assert
        with pytest.raises(ValidationError):
            TransitionYearData(
                quarterly_fixed=bad_quarterly,
                quarterly_mobile=self._quarterly_h1(),
                monthly_fixed=monthly,
                monthly_mobile=monthly,
            )

    def test_raises_when_monthly_data_includes_h1_month(self) -> None:
        # A January file in the monthly data conflicts with the quarterly files for Q1
        # Arrange
        quarterly = self._quarterly_h1()
        bad_monthly = MonthlyData(
            jan="/p/jan.csv",
            jul="/p/jul.csv",
            aug="/p/aug.csv",
            sep="/p/sep.csv",
            oct="/p/oct.csv",
            nov="/p/nov.csv",
            dec="/p/dec.csv",
        )

        # Act / Assert
        with pytest.raises(ValidationError):
            TransitionYearData(
                quarterly_fixed=quarterly,
                quarterly_mobile=quarterly,
                monthly_fixed=bad_monthly,
                monthly_mobile=self._monthly_h2(),
            )

    def test_raises_when_monthly_h2_is_incomplete(self) -> None:
        # Sep missing from fixed monthly — all six H2 months must be present
        # Arrange
        quarterly = self._quarterly_h1()
        incomplete_monthly = MonthlyData(
            jul="/p/jul.csv",
            aug="/p/aug.csv",
            oct="/p/oct.csv",
            nov="/p/nov.csv",
            dec="/p/dec.csv",
        )

        # Act / Assert
        with pytest.raises(ValidationError):
            TransitionYearData(
                quarterly_fixed=quarterly,
                quarterly_mobile=quarterly,
                monthly_fixed=incomplete_monthly,
                monthly_mobile=self._monthly_h2(),
            )

    def test_raises_when_year_is_not_2022(self) -> None:
        # Act / Assert
        with pytest.raises(ValidationError):
            TransitionYearData.model_validate(
                {
                    "year": 2023,
                    "quarterly_fixed": {},
                    "quarterly_mobile": {},
                    "monthly_fixed": {},
                    "monthly_mobile": {},
                },
            )


class TestMonthlyYearData:  # noqa: D101
    def _monthly(self) -> MonthlyData:
        return MonthlyData(
            jan="/p/jan.csv",
            feb="/p/feb.csv",
            mar="/p/mar.csv",
            apr="/p/apr.csv",
            may="/p/may.csv",
            jun="/p/jun.csv",
            jul="/p/jul.csv",
            aug="/p/aug.csv",
            sep="/p/sep.csv",
            oct="/p/oct.csv",
            nov="/p/nov.csv",
            dec="/p/dec.csv",
        )

    def test_valid_with_full_data(self) -> None:
        # Arrange
        monthly = self._monthly()

        # Act / Assert
        MonthlyYearData(year=2024, fixed=monthly, mobile=monthly)

    def test_valid_with_no_data_for_current_year(self) -> None:
        # For the current year data arrives progressively; no files yet is valid
        # Act / Assert
        MonthlyYearData(year=_CURRENT_YEAR)

    def test_raises_when_year_is_transition_year(self) -> None:
        # 2022 belongs to TransitionYearData
        # Act / Assert
        with pytest.raises(ValidationError):
            MonthlyYearData(year=2022)

    def test_raises_when_year_is_before_monthly_era(self) -> None:
        # Act / Assert
        with pytest.raises(ValidationError):
            MonthlyYearData(year=2019)
