from datetime import date

import pytest

from app.dates import allowed_analysis_range, validate_analysis_date

pytestmark = pytest.mark.unit


def test_allowed_range_covers_previous_month_through_today() -> None:
    assert allowed_analysis_range(date(2026, 7, 26)) == (
        date(2026, 6, 1),
        date(2026, 7, 26),
    )


def test_allowed_range_crosses_year_boundary() -> None:
    assert allowed_analysis_range(date(2026, 1, 4)) == (
        date(2025, 12, 1),
        date(2026, 1, 4),
    )


@pytest.mark.parametrize(
    "value",
    [date(2026, 5, 31), date(2026, 7, 27)],
)
def test_validate_analysis_date_rejects_outside_range(value: date) -> None:
    with pytest.raises(ValueError, match="must be between"):
        validate_analysis_date(value, date(2026, 7, 26))
