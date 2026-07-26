from datetime import date, datetime
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")


def today_in_korea() -> date:
    return datetime.now(KST).date()


def allowed_analysis_range(today: date | None = None) -> tuple[date, date]:
    current = today or today_in_korea()
    start_of_current_month = current.replace(day=1)
    if start_of_current_month.month == 1:
        start = start_of_current_month.replace(
            year=start_of_current_month.year - 1,
            month=12,
        )
    else:
        start = start_of_current_month.replace(month=start_of_current_month.month - 1)
    return start, current


def validate_analysis_date(value: date, today: date | None = None) -> date:
    start, end = allowed_analysis_range(today)
    if not start <= value <= end:
        raise ValueError(
            f"Analysis date must be between {start.isoformat()} and {end.isoformat()}."
        )
    return value
