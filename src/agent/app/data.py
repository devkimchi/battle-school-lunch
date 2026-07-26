from __future__ import annotations

import asyncio
import json
import random
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any, Protocol

from agent_framework import MCPStreamableHTTPTool

from .schemas import MealData, SchoolCandidate

_SPLIT_PATTERN = re.compile(r"<br\s*/?>", re.IGNORECASE)


class LunchDataError(RuntimeError):
    """Raised when MCP data cannot satisfy an analysis request."""


class McpCaller(Protocol):
    async def call_tool(self, tool_name: str, **kwargs: Any) -> str | list[Any]: ...


class McpLunchDataSource:
    def __init__(
        self,
        tool: McpCaller,
        *,
        random_source: random.Random | random.SystemRandom | None = None,
    ) -> None:
        self._tool = tool
        self._random = random_source or random.SystemRandom()

    @classmethod
    def create(cls, mcp_url: str) -> tuple[MCPStreamableHTTPTool, McpLunchDataSource]:
        tool = MCPStreamableHTTPTool(
            "school-lunch-mcp",
            mcp_url,
            allowed_tools=["getSchoolInfo", "getMealServiceDietInfo"],
            approval_mode="never_require",
            load_prompts=False,
        )
        return tool, cls(tool)

    async def random_schools(self, count: int = 10) -> list[SchoolCandidate]:
        if count < 1:
            raise ValueError("Candidate count must be positive.")

        first_payload = await self._call("getSchoolInfo", pIndex=1, pSize=100)
        total, first_rows = _extract_rows(first_payload, "schoolInfo")
        if total < count:
            raise LunchDataError(f"Only {total} schools are available; {count} are required.")

        selected_indexes = sorted(self._random.sample(range(total), count))
        rows_by_index = {index: row for index, row in enumerate(first_rows)}
        pages: dict[int, list[int]] = defaultdict(list)
        for index in selected_indexes:
            if index not in rows_by_index:
                pages[index // 100 + 1].append(index)

        if pages:
            page_numbers = sorted(pages)
            payloads = await asyncio.gather(
                *(
                    self._call("getSchoolInfo", pIndex=page, pSize=100)
                    for page in page_numbers
                )
            )
            for page, payload in zip(page_numbers, payloads, strict=True):
                _, rows = _extract_rows(payload, "schoolInfo")
                offset = (page - 1) * 100
                rows_by_index.update(
                    (offset + row_index, row)
                    for row_index, row in enumerate(rows)
                )

        candidates = [
            _school_from_row(rows_by_index[index])
            for index in selected_indexes
            if index in rows_by_index
        ]
        unique = {school.school_code: school for school in candidates}
        if len(unique) != count:
            raise LunchDataError("MCP school data did not contain ten unique complete schools.")
        return list(unique.values())

    async def meals_for(
        self,
        school_a: SchoolCandidate,
        school_b: SchoolCandidate,
        analysis_date: date,
    ) -> tuple[MealData, MealData]:
        query_date = analysis_date.strftime("%Y%m%d")
        payload_a, payload_b = await asyncio.gather(
            self._call(
                "getMealServiceDietInfo",
                ATPT_OFCDC_SC_CODE=school_a.edu_office_code,
                SD_SCHUL_CODE=school_a.school_code,
                MLSV_YMD=query_date,
            ),
            self._call(
                "getMealServiceDietInfo",
                ATPT_OFCDC_SC_CODE=school_b.edu_office_code,
                SD_SCHUL_CODE=school_b.school_code,
                MLSV_YMD=query_date,
            ),
        )
        meal_a = _meal_from_payload(payload_a, school_a, analysis_date)
        meal_b = _meal_from_payload(payload_b, school_b, analysis_date)
        if meal_a is None or meal_b is None:
            missing = [
                school.school_name
                for school, meal in ((school_a, meal_a), (school_b, meal_b))
                if meal is None
            ]
            raise LunchDataError(
                f"{', '.join(missing)}의 선택 날짜 중식 데이터가 없습니다. 다른 날짜를 선택해 주세요."
            )
        return meal_a, meal_b

    async def _call(self, name: str, **arguments: Any) -> dict[str, Any]:
        result = await self._tool.call_tool(name, **arguments)
        return _decode_tool_result(result)


def _decode_tool_result(result: str | list[Any]) -> dict[str, Any]:
    if isinstance(result, str):
        text = result
    else:
        text_parts = [
            item.text
            for item in result
            if isinstance(getattr(item, "text", None), str)
        ]
        text = "".join(text_parts)
    try:
        payload = json.loads(text)
    except (TypeError, json.JSONDecodeError) as exc:
        raise LunchDataError("MCP returned an invalid JSON tool result.") from exc
    if not isinstance(payload, dict):
        raise LunchDataError("MCP tool result must be a JSON object.")
    if "code" in payload and "message" in payload:
        raise LunchDataError(f"MCP error {payload['code']}: {payload['message']}")
    return payload


def _extract_rows(
    payload: Mapping[str, Any],
    response_key: str,
) -> tuple[int, list[dict[str, Any]]]:
    sections = payload.get(response_key)
    if sections is None and payload.get("RESULT", {}).get("CODE") == "INFO-200":
        return 0, []
    if not isinstance(sections, Sequence) or isinstance(sections, (str, bytes)):
        raise LunchDataError(f"MCP response is missing {response_key} sections.")

    total: int | None = None
    rows: list[dict[str, Any]] = []
    for section in sections:
        if not isinstance(section, Mapping):
            continue
        heads = section.get("head")
        if isinstance(heads, Sequence) and not isinstance(heads, (str, bytes)):
            for head in heads:
                if isinstance(head, Mapping) and isinstance(head.get("list_total_count"), int):
                    total = head["list_total_count"]
        raw_rows = section.get("row")
        if isinstance(raw_rows, Sequence) and not isinstance(raw_rows, (str, bytes)):
            rows.extend(row for row in raw_rows if isinstance(row, dict))
    return total if total is not None else len(rows), rows


def _school_from_row(row: Mapping[str, Any]) -> SchoolCandidate:
    required = {
        "school_code": row.get("SD_SCHUL_CODE"),
        "edu_office_code": row.get("ATPT_OFCDC_SC_CODE"),
        "school_name": row.get("SCHUL_NM"),
        "edu_office_name": row.get("ATPT_OFCDC_SC_NM"),
    }
    if not all(isinstance(value, str) and value.strip() for value in required.values()):
        raise LunchDataError("MCP returned an incomplete school record.")
    location = row.get("LCTN_SC_NM")
    return SchoolCandidate(
        **required,
        location_name=location if isinstance(location, str) else None,
    )


def _meal_from_payload(
    payload: Mapping[str, Any],
    school: SchoolCandidate,
    analysis_date: date,
) -> MealData | None:
    _, rows = _extract_rows(payload, "mealServiceDietInfo")
    if not rows:
        return None
    row = rows[0]
    return MealData(
        school=school,
        date=analysis_date,
        dishes=_split(row.get("DDISH_NM")),
        calorie=_optional_string(row.get("CAL_INFO")),
        nutrition=_split(row.get("NTR_INFO")),
        origin=_split(row.get("ORPLC_INFO")),
        servings=row.get("MLSV_FGR") if isinstance(row.get("MLSV_FGR"), (int, float)) else None,
    )


def _split(value: Any) -> list[str]:
    if not isinstance(value, str):
        return []
    return [item.strip() for item in _SPLIT_PATTERN.split(value) if item.strip()]


def _optional_string(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None
