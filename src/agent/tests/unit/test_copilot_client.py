from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from agent_framework import Agent, ChatResponse, Message
from copilot.generated.rpc import PermissionDecisionReject
from pydantic import ValidationError

from app.copilot_client import CopilotAdapterError, CopilotStructuredChatClient
from app.schemas import (
    EvaluationArea,
    JudgeReport,
    SchoolAssessment,
    SpecialistEvaluation,
)

pytestmark = pytest.mark.unit


def specialist_payload(**changes: Any) -> dict[str, Any]:
    assessment = {
        "score": 4,
        "evidence": ["현미밥"],
        "strengths": ["균형 잡힌 구성"],
        "risks": [],
        "improvements": ["과일을 추가합니다."],
    }
    payload: dict[str, Any] = {
        "area": EvaluationArea.NUTRITION.value,
        "schoolA": assessment,
        "schoolB": assessment,
        "comparison": "가학교의 영양 구성이 더 균형 잡혔습니다.",
        "limitations": [],
    }
    payload.update(changes)
    return payload


def judge_payload(**changes: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "winner": "school_a",
        "headline": "가학교가 우세합니다.",
        "rationale": ["가학교의 총점이 높습니다."],
        "schoolAImprovements": ["과일을 추가합니다."],
        "schoolBImprovements": ["채소 구성을 보완합니다."],
        "qualityNotes": [],
        "limitations": [],
    }
    payload.update(changes)
    return payload


class FakeSession:
    def __init__(self, client: FakeCopilotClient, session_id: str) -> None:
        self.client = client
        self.session_id = session_id
        self.abort_calls = 0
        self.disconnect_calls = 0

    async def send_and_wait_typed(self, prompt: str, response_type: type, **kwargs: Any) -> Any:
        self.client.requests.append((prompt, response_type, kwargs))
        self.client.started.set()
        if self.client.wait_for_release:
            await self.client.release.wait()
        if self.client.error is not None:
            raise self.client.error
        return response_type.model_validate_json(
            json.dumps(self.client.payload),
            by_alias=True,
            by_name=False,
        )

    async def abort(self) -> None:
        self.abort_calls += 1

    async def disconnect(self) -> None:
        self.disconnect_calls += 1
        if self.client.disconnect_error is not None:
            raise self.client.disconnect_error


class FakeCopilotClient:
    def __init__(
        self,
        payload: dict[str, Any] | None = None,
        *,
        error: BaseException | None = None,
        disconnect_error: BaseException | None = None,
        wait_for_release: bool = False,
    ) -> None:
        self.payload = payload or specialist_payload()
        self.error = error
        self.disconnect_error = disconnect_error
        self.wait_for_release = wait_for_release
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.sessions: list[FakeSession] = []
        self.create_options: list[dict[str, Any]] = []
        self.requests: list[tuple[str, type, dict[str, Any]]] = []

    async def create_session(self, **kwargs: Any) -> FakeSession:
        self.create_options.append(kwargs)
        session = FakeSession(self, f"session-{len(self.sessions) + 1}")
        self.sessions.append(session)
        return session

def specialist_options(**changes: Any) -> dict[str, Any]:
    return {
        "instructions": "역할별 평가 지침",
        "response_format": SpecialistEvaluation,
        **changes,
    }


def test_non_streaming_maps_typed_result_and_limits_session_capabilities() -> None:
    sdk = FakeCopilotClient()
    client = CopilotStructuredChatClient(sdk, model="gpt-5-mini")

    response = asyncio.run(
        client.get_response(
            [Message(role="user", contents=["급식 비교 요청"])],
            options=specialist_options(),
        )
    )

    assert isinstance(response, ChatResponse)
    assert isinstance(response.value, SpecialistEvaluation)
    assert response.value.area is EvaluationArea.NUTRITION
    assert response.value.school_a.score == 4
    assert response.model == "gpt-5-mini"
    assert sdk.requests[0][0] == "급식 비교 요청"
    assert sdk.create_options[0]["model"] == "gpt-5-mini"
    assert sdk.create_options[0]["system_message"] == {
        "mode": "replace",
        "content": "역할별 평가 지침",
    }
    assert sdk.create_options[0]["available_tools"] == []
    assert sdk.create_options[0]["tools"] == []
    assert sdk.create_options[0]["mcp_servers"] == {}
    assert sdk.create_options[0]["enable_config_discovery"] is False
    assert sdk.create_options[0]["enable_file_hooks"] is False
    assert sdk.create_options[0]["enable_skills"] is False
    assert sdk.create_options[0]["enable_host_git_operations"] is False
    assert sdk.create_options[0]["enable_on_demand_instruction_discovery"] is False
    assert sdk.create_options[0]["skip_custom_instructions"] is True
    assert sdk.create_options[0]["enable_mcp_apps"] is False
    assert sdk.create_options[0]["request_extensions"] is False
    assert "reasoning_effort" not in sdk.create_options[0]
    assert sdk.sessions[0].disconnect_calls == 1
    assert sdk.sessions[0].abort_calls == 0


def test_judge_uses_its_typed_output_schema() -> None:
    sdk = FakeCopilotClient(judge_payload())
    client = CopilotStructuredChatClient(sdk)

    response = asyncio.run(
        client.get_response(
            [Message(role="user", contents=["최종 검토"])],
            options={"response_format": JudgeReport, "instructions": "판정 지침"},
        )
    )

    assert isinstance(response.value, JudgeReport)
    assert response.value.winner == "school_a"
    assert sdk.requests[0][1].__name__ == "_JudgeReportOutput"


@pytest.mark.asyncio
async def test_stream_and_non_stream_reuse_the_same_final_typed_result() -> None:
    sdk = FakeCopilotClient()
    client = CopilotStructuredChatClient(sdk)
    non_stream = await client.get_response(
        [Message(role="user", contents=["비교"])],
        options=specialist_options(),
    )

    stream = client.get_response(
        [Message(role="user", contents=["비교"])],
        stream=True,
        options=specialist_options(),
    )
    updates = [update async for update in stream]
    streamed_response = await stream.get_final_response()

    assert len(updates) == 1
    assert updates[0].text == non_stream.text
    assert streamed_response.value == non_stream.value
    assert isinstance(streamed_response.value, SpecialistEvaluation)
    assert len(sdk.requests) == 2
    assert [session.disconnect_calls for session in sdk.sessions] == [1, 1]


@pytest.mark.asyncio
async def test_adapter_integrates_with_agent_framework_stream_finalization() -> None:
    sdk = FakeCopilotClient()
    agent = Agent(
        CopilotStructuredChatClient(sdk),
        instructions="전문가 지침",
        default_options={"response_format": SpecialistEvaluation},
    )

    non_stream = await agent.run("급식 비교")
    stream = agent.run("급식 비교", stream=True)
    async for _update in stream:
        pass
    streamed = await stream.get_final_response()

    assert isinstance(non_stream.value, SpecialistEvaluation)
    assert streamed.value == non_stream.value
    assert len(sdk.requests) == 2
    assert [session.disconnect_calls for session in sdk.sessions] == [1, 1]


@pytest.mark.parametrize(
    "payload",
    [
        specialist_payload(schoolA={**specialist_payload()["schoolA"], "score": 6}),
        specialist_payload(schoolA={key: value for key, value in specialist_payload()["schoolA"].items() if key != "risks"}),
        specialist_payload(unexpected="not allowed"),
        judge_payload(qualityNotes=None),
    ],
)
def test_invalid_or_incomplete_structured_output_fails_and_cleans_up(payload: dict[str, Any]) -> None:
    is_judge = "winner" in payload
    sdk = FakeCopilotClient(payload)
    client = CopilotStructuredChatClient(sdk)
    options = (
        {"response_format": JudgeReport}
        if is_judge
        else {"response_format": SpecialistEvaluation}
    )

    with pytest.raises(ValidationError):
        asyncio.run(client.get_response([Message(role="user", contents=["입력"])], options=options))

    assert sdk.sessions[0].abort_calls == 1
    assert sdk.sessions[0].disconnect_calls == 1


def test_unsupported_schema_and_options_fail_before_creating_a_session() -> None:
    sdk = FakeCopilotClient()
    client = CopilotStructuredChatClient(sdk)

    with pytest.raises(CopilotAdapterError, match="response_format"):
        client.get_response(
            [Message(role="user", contents=["입력"])],
            options={"response_format": dict},
        )
    with pytest.raises(CopilotAdapterError, match="Unsupported chat options"):
        client.get_response(
            [Message(role="user", contents=["입력"])],
            options=specialist_options(reasoning_effort="high"),
        )

    assert sdk.create_options == []


def test_conversation_roles_are_preserved_and_system_messages_are_merged() -> None:
    sdk = FakeCopilotClient()
    client = CopilotStructuredChatClient(sdk)

    asyncio.run(
        client.get_response(
            [
                Message(role="system", contents=["추가 시스템 제약"]),
                Message(role="user", contents=["첫 요청"]),
                Message(role="assistant", contents=["이전 답변"]),
                Message(role="user", contents=["후속 요청"]),
            ],
            options=specialist_options(),
        )
    )

    assert sdk.requests[0][0] == "[user]\n첫 요청\n\n[assistant]\n이전 답변\n\n[user]\n후속 요청"
    assert sdk.create_options[0]["system_message"]["content"] == (
        "역할별 평가 지침\n\n---\n\n추가 시스템 제약"
    )


@pytest.mark.asyncio
async def test_failure_aborts_and_deletes_session_without_masking_original_error() -> None:
    sdk = FakeCopilotClient(
        error=RuntimeError("SDK request failed"),
        disconnect_error=RuntimeError("session disconnect failed"),
    )
    client = CopilotStructuredChatClient(sdk)

    with pytest.raises(RuntimeError, match="SDK request failed"):
        await client.get_response(
            [Message(role="user", contents=["입력"])],
            options=specialist_options(),
        )

    assert sdk.sessions[0].abort_calls == 1
    assert sdk.sessions[0].disconnect_calls == 1


@pytest.mark.asyncio
async def test_cleanup_failure_does_not_return_a_successful_response() -> None:
    sdk = FakeCopilotClient(disconnect_error=RuntimeError("session disconnect failed"))
    client = CopilotStructuredChatClient(sdk)

    with pytest.raises(RuntimeError, match="session disconnect failed"):
        await client.get_response(
            [Message(role="user", contents=["입력"])],
            options=specialist_options(),
        )

    assert sdk.sessions[0].disconnect_calls == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [TimeoutError("timed out"), asyncio.CancelledError()])
async def test_timeout_and_cancellation_abort_and_disconnect_session(error: BaseException) -> None:
    sdk = FakeCopilotClient(error=error)
    client = CopilotStructuredChatClient(sdk)

    with pytest.raises(type(error)):
        await client.get_response(
            [Message(role="user", contents=["입력"])],
            options=specialist_options(),
        )

    assert sdk.sessions[0].abort_calls == 1
    assert sdk.sessions[0].disconnect_calls == 1


@pytest.mark.asyncio
async def test_task_cancellation_aborts_in_flight_session() -> None:
    sdk = FakeCopilotClient(wait_for_release=True)
    client = CopilotStructuredChatClient(sdk)
    task = asyncio.create_task(
        client.get_response(
            [Message(role="user", contents=["입력"])],
            options=specialist_options(),
        )
    )
    await sdk.started.wait()
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert sdk.sessions[0].abort_calls == 1
    assert sdk.sessions[0].disconnect_calls == 1


@pytest.mark.asyncio
async def test_permission_requests_are_explicitly_rejected() -> None:
    sdk = FakeCopilotClient()
    client = CopilotStructuredChatClient(sdk)
    await client.get_response(
        [Message(role="user", contents=["입력"])],
        options=specialist_options(),
    )

    decision = await sdk.create_options[0]["on_permission_request"](object(), object())
    assert isinstance(decision, PermissionDecisionReject)
