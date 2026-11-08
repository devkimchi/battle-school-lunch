from __future__ import annotations

import asyncio
import json
import logging
from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.copilot_client import CopilotStructuredChatClient
from app.main import create_app
from app.schemas import (
    EvaluationArea,
    MealData,
    SchoolCandidate,
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


class FakeCopilotSession:
    def __init__(
        self,
        client: FakeCopilotRuntime,
        session_id: str,
        options: dict[str, Any],
    ) -> None:
        self.client = client
        self.session_id = session_id
        self.options = options
        self.abort_calls = 0

    async def send_and_wait_typed(
        self,
        prompt: str,
        response_type: type,
        **_kwargs: Any,
    ) -> Any:
        is_judge = response_type.__name__ == "_JudgeReportOutput"
        self.client.requests.append((prompt, response_type))
        if self.client.error is not None:
            raise self.client.error
        if is_judge:
            self.client.judge_started_after_specialists = (
                self.client.completed_specialists == len(EvaluationArea)
            )
            area = None
        else:
            instructions = self.options["system_message"]["content"]
            area = (
                EvaluationArea.NUTRITION
                if "Nutrition Agent" in instructions
                else EvaluationArea.HEALTH
                if "Health Agent" in instructions
                else EvaluationArea.MENU_QUALITY
            )
            self.client.active_specialists += 1
            self.client.max_active_specialists = max(
                self.client.max_active_specialists,
                self.client.active_specialists,
            )

        delay = {
            EvaluationArea.NUTRITION: 0.01,
            EvaluationArea.HEALTH: 0.03,
            EvaluationArea.MENU_QUALITY: 0.05,
        }
        await asyncio.sleep(delay.get(area, 0.01))
        if is_judge:
            payload = {
                "winner": self.client.judge_winner,
                "headline": "1학교의 급식이 더 높은 점수를 받았습니다.",
                "rationale": ["세 평가 영역의 총점이 더 높습니다."],
                "schoolAImprovements": ["과일을 추가합니다."],
                "schoolBImprovements": ["채소 반찬을 늘립니다."],
                "qualityNotes": [],
                "limitations": [],
            }
        else:
            self.client.active_specialists -= 1
            self.client.completed_specialists += 1
            assessment = {
                "score": 5,
                "evidence": ["현미밥"],
                "strengths": ["균형"],
                "risks": [],
                "improvements": ["과일 추가"],
            }
            other_assessment = {
                **assessment,
                "score": 3,
                "evidence": ["기본 구성"],
            }
            payload = {
                "area": area.value,
                "schoolA": assessment,
                "schoolB": other_assessment,
                "comparison": "1학교가 우수합니다.",
                "limitations": [],
            }
        return response_type.model_validate_json(json.dumps(payload))

    async def abort(self) -> None:
        self.abort_calls += 1

    async def disconnect(self) -> None:
        self.client.disconnected.append(self.session_id)


class FakeCopilotRuntime:
    def __init__(
        self,
        *,
        error: BaseException | None = None,
        judge_winner: str = "school_a",
    ) -> None:
        self.error = error
        self.judge_winner = judge_winner
        self.sessions: list[FakeCopilotSession] = []
        self.requests: list[tuple[str, type]] = []
        self.disconnected: list[str] = []
        self.active_specialists = 0
        self.max_active_specialists = 0
        self.completed_specialists = 0
        self.judge_started_after_specialists = False

    async def create_session(self, **options: Any) -> FakeCopilotSession:
        session = FakeCopilotSession(self, f"session-{len(self.sessions) + 1}", options)
        self.sessions.append(session)
        return session

def copilot_chat_client(runtime: FakeCopilotRuntime) -> CopilotStructuredChatClient:
    return CopilotStructuredChatClient(runtime, model="test-model")


def decode_sse(response_text: str) -> list[dict[str, Any]]:
    events = []
    for line in response_text.splitlines():
        if line.startswith("data: "):
            events.append(json.loads(line.removeprefix("data: ")))
    return events


def test_candidate_request_streams_typed_state() -> None:
    runtime = FakeCopilotRuntime()
    app = create_app(
        data_source=CandidateDataSource(),
        chat_client=copilot_chat_client(runtime),
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
                "state": {
                    "action": "load_candidates",
                    "evaluationProgress": {"nutrition": "completed"},
                },
            },
        )

    assert response.status_code == 200
    events = decode_sse(response.text)
    snapshots = [event["snapshot"] for event in events if event["type"] == "STATE_SNAPSHOT"]
    assert snapshots[-1]["phase"] == "selecting"
    assert len(snapshots[-1]["candidates"]) == 10
    assert snapshots[-1]["evaluationProgress"] == {}
    assert events[0]["type"] == "RUN_STARTED"
    assert events[-1]["type"] == "RUN_FINISHED"
    assert runtime.requests == []


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
    runtime = FakeCopilotRuntime()
    app = create_app(
        data_source=NoMealDataSource(),
        chat_client=copilot_chat_client(runtime),
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
    assert runtime.requests == []


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


def test_rate_limit_returns_user_visible_retryable_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    schools = [candidate(1), candidate(2)]
    runtime = FakeCopilotRuntime(error=RuntimeError("Model request exceeded rate limit."))
    app = create_app(
        data_source=CompleteDataSource(),
        chat_client=copilot_chat_client(runtime),
    )

    with caplog.at_level(logging.ERROR, logger="app.agui"):
        with TestClient(app) as client:
            response = client.post(
                "/agent",
                json={
                    "threadId": "thread-rate-limit",
                    "runId": "run-rate-limit",
                    "messages": [
                        {
                            "id": "message-rate-limit",
                            "role": "user",
                            "content": "두 학교를 비교해줘",
                        }
                    ],
                    "state": {
                        "action": "analyze",
                        "candidates": [
                            school.model_dump(mode="json", by_alias=True)
                            for school in schools
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
    assert snapshots[-1]["error"]["code"] == "MODEL_RATE_LIMITED"
    assert snapshots[-1]["error"]["retryable"] is True
    assert "thread_id=thread-rate-limit" in caplog.text
    assert "run_id=run-rate-limit" in caplog.text
    assert "Model request exceeded rate limit." in caplog.text
    assert len(runtime.requests) == len(EvaluationArea)
    assert len(runtime.disconnected) == len(EvaluationArea)
    assert "completed" not in snapshots[-1]["evaluationProgress"].values()
    assert "failed" in snapshots[-1]["evaluationProgress"].values()


@pytest.mark.parametrize(
    "failure",
    [
        RuntimeError("Authentication failed: no credentials."),
        RuntimeError("Unsupported model: unavailable-model."),
        TimeoutError("Copilot request timed out."),
    ],
    ids=["authentication", "unsupported-model", "timeout"],
)
def test_model_failures_return_provider_neutral_error(failure: BaseException) -> None:
    schools = [candidate(1), candidate(2)]
    runtime = FakeCopilotRuntime(error=failure)
    app = create_app(
        data_source=CompleteDataSource(),
        chat_client=copilot_chat_client(runtime),
    )

    with TestClient(app) as client:
        response = client.post(
            "/agent",
            json={
                "threadId": "thread-auth-failure",
                "runId": "run-auth-failure",
                "messages": [
                    {
                        "id": "message-auth-failure",
                        "role": "user",
                        "content": "두 학교를 비교해줘",
                    }
                ],
                "state": {
                    "action": "analyze",
                    "candidates": [
                        school.model_dump(mode="json", by_alias=True)
                        for school in schools
                    ],
                    "selectedSchoolCodes": ["1", "2"],
                    "selectedDate": date.today().isoformat(),
                },
            },
        )

    events = decode_sse(response.text)
    snapshots = [event["snapshot"] for event in events if event["type"] == "STATE_SNAPSHOT"]
    assert response.status_code == 200
    assert snapshots[-1]["phase"] == "error"
    assert snapshots[-1]["error"]["code"] == "MODEL_UNAVAILABLE"
    assert snapshots[-1]["error"]["retryable"] is True
    assert str(failure) not in response.text
    assert len(runtime.requests) == len(runtime.disconnected)


def test_analysis_streams_concurrent_steps_and_completed_state() -> None:
    schools = [candidate(1), candidate(2)]
    runtime = FakeCopilotRuntime()
    app = create_app(
        data_source=CompleteDataSource(),
        chat_client=copilot_chat_client(runtime),
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
                    "evaluationProgress": {
                        area.value: "completed" for area in EvaluationArea
                    },
                },
            },
        )

    assert response.status_code == 200
    events = decode_sse(response.text)
    snapshots = [event["snapshot"] for event in events if event["type"] == "STATE_SNAPSHOT"]
    assert runtime.max_active_specialists == 3
    assert runtime.judge_started_after_specialists is True
    assert len(runtime.requests) == 4
    assert len(runtime.disconnected) == 4
    assert len(set(runtime.disconnected)) == 4
    specialist_requests = [
        prompt for prompt, response_type in runtime.requests
        if response_type.__name__ == "_SpecialistEvaluationOutput"
    ]
    assert len(specialist_requests) == 3
    assert all("현미밥" in request for request in specialist_requests)
    assert all('"calorie": "700 Kcal"' in request for request in specialist_requests)
    assert any(event["type"] == "STEP_STARTED" for event in events)
    phases = [snapshot["phase"] for snapshot in snapshots]
    assert list(dict.fromkeys(phases)) == [
        "loading_meals", "evaluating", "judging", "completed",
    ]
    assert snapshots[0]["evaluationProgress"] == {
        area.value: "pending" for area in EvaluationArea
    }
    evaluating = [snapshot for snapshot in snapshots if snapshot["phase"] == "evaluating"]
    for area in EvaluationArea:
        statuses = [snapshot["evaluationProgress"][area.value] for snapshot in evaluating]
        assert list(dict.fromkeys(statuses)) == ["pending", "running", "completed"]
    assert any(
        snapshot["evaluationProgress"]["nutrition"] == "completed"
        and snapshot["evaluationProgress"]["menu_quality"] == "running"
        for snapshot in evaluating
    )
    assert all(
        snapshot["evaluationProgress"] == {
            area.value: "completed" for area in EvaluationArea
        }
        for snapshot in snapshots if snapshot["phase"] in {"judging", "completed"}
    )
    assert snapshots[-1]["phase"] == "completed"
    assert snapshots[-1]["result"]["schoolAScore"]["total"] == 100
    assert snapshots[-1]["result"]["schoolBScore"]["total"] == 60
    assert snapshots[-1]["result"]["judge"]["winner"] == "school_a"


def test_judge_winner_must_match_calculated_scores() -> None:
    schools = [candidate(1), candidate(2)]
    runtime = FakeCopilotRuntime(judge_winner="school_b")
    app = create_app(
        data_source=CompleteDataSource(),
        chat_client=copilot_chat_client(runtime),
    )

    with TestClient(app) as client:
        response = client.post(
            "/agent",
            json={
                "threadId": "thread-wrong-winner",
                "runId": "run-wrong-winner",
                "messages": [
                    {
                        "id": "message-wrong-winner",
                        "role": "user",
                        "content": "두 학교를 비교해줘",
                    }
                ],
                "state": {
                    "action": "analyze",
                    "candidates": [
                        school.model_dump(mode="json", by_alias=True)
                        for school in schools
                    ],
                    "selectedSchoolCodes": ["1", "2"],
                    "selectedDate": date.today().isoformat(),
                },
            },
        )

    events = decode_sse(response.text)
    snapshots = [event["snapshot"] for event in events if event["type"] == "STATE_SNAPSHOT"]
    assert response.status_code == 200
    assert snapshots[-1]["phase"] == "error"
    assert snapshots[-1]["error"]["code"] == "MODEL_UNAVAILABLE"
    assert not any(snapshot["phase"] == "completed" for snapshot in snapshots)
    assert len(runtime.requests) == 4
    assert len(runtime.disconnected) == 4
