import json
import random
from datetime import date
from typing import Any

import pytest

from app.data import LunchDataError, McpLunchDataSource
from app.schemas import SchoolCandidate

pytestmark = pytest.mark.unit


class StubMcp:
    def __init__(self, responses: dict[tuple[str, int], dict[str, Any]]) -> None:
        self._responses = responses

    async def call_tool(self, tool_name: str, **kwargs: Any) -> str:
        key = (tool_name, int(kwargs.get("pIndex", 1)))
        return json.dumps(self._responses[key], ensure_ascii=False)


def school_payload(start: int, count: int, total: int) -> dict[str, Any]:
    return {
        "schoolInfo": [
            {
                "head": [
                    {"list_total_count": total},
                    {"RESULT": {"CODE": "INFO-000", "MESSAGE": "정상"}},
                ]
            },
            {
                "row": [
                    {
                        "SD_SCHUL_CODE": str(index),
                        "ATPT_OFCDC_SC_CODE": "B10",
                        "SCHUL_NM": f"{index}학교",
                        "ATPT_OFCDC_SC_NM": "서울특별시교육청",
                        "LCTN_SC_NM": "서울특별시",
                    }
                    for index in range(start, start + count)
                ]
            },
        ]
    }


async def test_random_schools_returns_ten_unique_candidates() -> None:
    source = McpLunchDataSource(
        StubMcp(
            {
                ("getSchoolInfo", 1): school_payload(0, 100, 205),
                ("getSchoolInfo", 2): school_payload(100, 100, 205),
                ("getSchoolInfo", 3): school_payload(200, 5, 205),
            }
        ),
        random_source=random.Random(7),
    )

    candidates = await source.random_schools()

    assert len(candidates) == 10
    assert len({candidate.school_code for candidate in candidates}) == 10


class MealStubMcp:
    def __init__(self, payloads: list[dict[str, Any]]) -> None:
        self._payloads = iter(payloads)

    async def call_tool(self, _tool_name: str, **_kwargs: Any) -> str:
        return json.dumps(next(self._payloads), ensure_ascii=False)


def candidate(code: str, name: str) -> SchoolCandidate:
    return SchoolCandidate(
        school_code=code,
        edu_office_code="B10",
        school_name=name,
        edu_office_name="서울특별시교육청",
    )


async def test_meals_for_stops_when_either_school_has_no_lunch() -> None:
    no_data = {"RESULT": {"CODE": "INFO-200", "MESSAGE": "없음"}}
    source = McpLunchDataSource(MealStubMcp([no_data, no_data]))

    with pytest.raises(LunchDataError, match="다른 날짜"):
        await source.meals_for(
            candidate("1", "가학교"),
            candidate("2", "나학교"),
            date(2026, 7, 1),
        )
