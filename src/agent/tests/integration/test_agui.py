import json
import os
import asyncio
from datetime import date
from typing import Any

import pytest
from agent_framework import ChatResponse, ChatResponseUpdate, Content, Message, ResponseStream
from fastapi.testclient import TestClient

os.environ.setdefault("FOUNDRY_PROJECT_ENDPOINT", "https://example.services.ai.azure.com/api/projects/test")
os.environ.setdefault("FOUNDRY_MODEL_DEPLOYMENT_NAME", "test-model")

from app.main import create_app
from app.schemas import (
    EvaluationArea,
    JudgeReport,
    MealData,
    SchoolAssessment,
    SchoolCandidate,
    SpecialistEvaluation,
)

pytestmark = pytest.mark.integration


def candidate(index: int) -> SchoolCandidate:
    return SchoolCandidate(
        school_code=str(index),
        edu_office_code="B10",
        school_name=f"{index}학교",
        edu_office_name="서울특별시교육청",
    )


class CandidateDataSource:
    async def random_schools(self, count: int = 10) -> list[SchoolCandidate]:
        return [candidate(index) for index in range(count)]

    async def meals_for(
        self,
        school_a: SchoolCandidate,
        school_b: SchoolCandidate,
        analysis_date: date,
    ) -> tuple[MealData, MealData]:
        raise AssertionError("meals_for should not be called")


class UnusedChatClient:
    async def get_response(self, *_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("chat client should not be called")


def decode_sse(response_text: str) -> list[dict[str, Any]]:
    events = []
    for line in response_text.splitlines():
        if line.startswith("data: "):
            events.append(json.loads(line.removeprefix("data: ")))
    return events


def test_candidate_request_streams_typed_state() -> None:
    app = create_app(
        data_source=CandidateDataSource(),
        chat_client=UnusedChatClient(),
    )

    with TestClient(app) as client:
        response = client.post(
            "/agent",
            json={
                "threadId": "thread-1",
                "runId": "run-1",
                "messages": [
                    {"id": "message-1", "role": "user", "content": "학교 후보를 보여줘"}
                ],
                "state": {"action": "load_candidates"},
            },
        )

    assert response.status_code == 200
    events = decode_sse(response.text)
    snapshots = [event["snapshot"] for event in events if event["type"] == "STATE_SNAPSHOT"]
    assert snapshots[-1]["phase"] == "selecting"
    assert len(snapshots[-1]["candidates"]) == 10
    assert events[0]["type"] == "RUN_STARTED"
    assert events[-1]["type"] == "RUN_FINISHED"


class NoMealDataSource(CandidateDataSource):
    async def meals_for(
        self,
        school_a: SchoolCandidate,
        school_b: SchoolCandidate,
        analysis_date: date,
    ) -> tuple[MealData, MealData]:
        from app.data import LunchDataError

        raise LunchDataError("선택 날짜 중식 데이터가 없습니다. 다른 날짜를 선택해 주세요.")


def test_no_meal_returns_user_visible_error_state() -> None:
    schools = [candidate(1), candidate(2)]
    app = create_app(
        data_source=NoMealDataSource(),
        chat_client=UnusedChatClient(),
    )

    with TestClient(app) as client:
        response = client.post(
            "/agent",
            json={
                "threadId": "thread-2",
                "runId": "run-2",
                "messages": [
                    {"id": "message-2", "role": "user", "content": "두 학교를 비교해줘"}
                ],
                "state": {
                    "action": "analyze",
                    "candidates": [
                        school.model_dump(mode="json", by_alias=True) for school in schools
                    ],
                    "selectedSchoolCodes": ["1", "2"],
                    "selectedDate": date.today().isoformat(),
                },
            },
        )

    assert response.status_code == 200
    events = decode_sse(response.text)
    snapshots = [event["snapshot"] for event in events if event["type"] == "STATE_SNAPSHOT"]
    assert snapshots[-1]["phase"] == "error"
    assert snapshots[-1]["error"]["code"] == "DATA_UNAVAILABLE"
    assert "다른 날짜" in snapshots[-1]["error"]["message"]


class CompleteDataSource(CandidateDataSource):
    async def meals_for(
        self,
        school_a: SchoolCandidate,
        school_b: SchoolCandidate,
        analysis_date: date,
    ) -> tuple[MealData, MealData]:
        def meal(school: SchoolCandidate) -> MealData:
            return MealData(
                school=school,
                date=analysis_date,
                dishes=["현미밥", "된장국", "채소무침"],
                calorie="700 Kcal",
                nutrition=["탄수화물(g): 80"],
            )

        return meal(school_a), meal(school_b)


class StructuredChatClient:
    def __init__(self) -> None:
        self.active = 0
        self.max_active = 0

    def get_response(
        self,
        messages: list[Message],
        *,
        stream: bool = False,
        options: dict[str, Any] | None = None,
        **_kwargs: Any,
    ) -> Any:
        assert messages
        if not stream:
            return self._response(options)

        async def updates() -> Any:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            await asyncio.sleep(0.01)
            response = await self._response(options)
            self.active -= 1
            yield ChatResponseUpdate(
                role="assistant",
                contents=[Content.from_text(response.value.model_dump_json())],
            )

        async def finalize(_updates: Any) -> ChatResponse[Any]:
            return await self._response(options)

        return ResponseStream(updates(), finalizer=finalize)

    async def _response(
        self,
        options: dict[str, Any] | None,
    ) -> ChatResponse[Any]:
        instructions = str((options or {}).get("instructions", ""))
        if (options or {}).get("response_format") is JudgeReport:
            value: Any = JudgeReport(
                winner="school_a",
                headline="1학교의 급식이 더 높은 점수를 받았습니다.",
                rationale=["세 평가 영역의 총점이 더 높습니다."],
                school_a_improvements=["과일을 추가합니다."],
                school_b_improvements=["채소 반찬을 늘립니다."],
            )
        else:
            area = (
                EvaluationArea.NUTRITION
                if "Nutrition Agent" in instructions
                else EvaluationArea.HEALTH
                if "Health Agent" in instructions
                else EvaluationArea.MENU_QUALITY
            )
            value = SpecialistEvaluation(
                area=area,
                school_a=SchoolAssessment(
                    score=5,
                    evidence=["현미밥"],
                    strengths=["균형"],
                    improvements=["과일 추가"],
                ),
                school_b=SchoolAssessment(
                    score=3,
                    evidence=["기본 구성"],
                    strengths=["한 끼 구성"],
                    improvements=["채소 추가"],
                ),
                comparison="1학교가 우수합니다.",
            )
        return ChatResponse(
            messages=[Message(role="assistant", contents=["structured"])],
            value=value,
        )


def test_analysis_streams_concurrent_steps_and_completed_state() -> None:
    schools = [candidate(1), candidate(2)]
    chat_client = StructuredChatClient()
    app = create_app(
        data_source=CompleteDataSource(),
        chat_client=chat_client,
    )

    with TestClient(app) as client:
        response = client.post(
            "/agent",
            json={
                "threadId": "thread-3",
                "runId": "run-3",
                "messages": [
                    {"id": "message-3", "role": "user", "content": "두 학교를 비교해줘"}
                ],
                "state": {
                    "action": "analyze",
                    "candidates": [
                        school.model_dump(mode="json", by_alias=True) for school in schools
                    ],
                    "selectedSchoolCodes": ["1", "2"],
                    "selectedDate": date.today().isoformat(),
                },
            },
        )

    assert response.status_code == 200
    events = decode_sse(response.text)
    snapshots = [event["snapshot"] for event in events if event["type"] == "STATE_SNAPSHOT"]
    assert chat_client.max_active == 3
    assert any(event["type"] == "STEP_STARTED" for event in events)
    assert snapshots[-1]["phase"] == "completed"
    assert snapshots[-1]["result"]["schoolAScore"]["total"] == 100
    assert snapshots[-1]["result"]["schoolBScore"]["total"] == 60
