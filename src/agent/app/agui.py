from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncGenerator
from datetime import date
from typing import Any, cast

from ag_ui.core import (
    BaseEvent,
    CustomEvent,
    RunErrorEvent,
    RunFinishedEvent,
    RunStartedEvent,
    StateSnapshotEvent,
    StepFinishedEvent,
    StepStartedEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
)
from agent_framework import SupportsChatGetResponse
from agent_framework.ag_ui import AgentFrameworkWorkflow

from .data import LunchDataError, LunchDataSource
from .dates import validate_analysis_date
from .instructions import InstructionLoader
from .schemas import AgentError, AnalysisResult, AnalysisState, SchoolCandidate
from .workflow import build_evaluation_workflow, evaluation_prompt

logger = logging.getLogger(__name__)


class AnalysisWorkflowError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class LunchAnalysisAGUIWorkflow(AgentFrameworkWorkflow):
    def __init__(
        self,
        *,
        data_source: LunchDataSource,
        chat_client: SupportsChatGetResponse[Any],
        instructions: InstructionLoader | None = None,
    ) -> None:
        super().__init__(
            name="school-lunch-analysis",
            description="Compare two school lunches with concurrent specialist agents.",
        )
        self._data_source = data_source
        self._chat_client = chat_client
        self._instructions = instructions or InstructionLoader()

    async def run(self, input_data: dict[str, Any]) -> AsyncGenerator[BaseEvent]:
        thread_id = self._thread_id_from_input(input_data)
        run_id = str(input_data.get("run_id") or input_data.get("runId") or uuid.uuid4())
        state_data = input_data.get("state") or {}
        try:
            state = AnalysisState.model_validate(state_data)
        except ValueError:
            async for event in self._error_events(
                thread_id,
                run_id,
                "INVALID_STATE",
                "학교와 날짜 선택 정보가 올바르지 않습니다.",
            ):
                yield event
            return

        yield RunStartedEvent(thread_id=thread_id, run_id=run_id)
        try:
            if state.action == "load_candidates":
                async for event in self._load_candidates(state):
                    yield event
            elif state.action == "analyze":
                async for event in self._analyze(input_data, state, thread_id, run_id):
                    yield event
            else:
                raise LunchDataError("지원하지 않는 분석 요청입니다.")
        except LunchDataError as exc:
            async for event in self._user_error_events(state, "DATA_UNAVAILABLE", str(exc)):
                yield event
        except AnalysisWorkflowError as exc:
            async for event in self._user_error_events(state, exc.code, str(exc)):
                yield event
        except Exception:
            logger.exception("Unhandled lunch analysis failure")
            yield RunErrorEvent(
                code="ANALYSIS_FAILED",
                message="급식 분석 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
            )
            return
        yield RunFinishedEvent(thread_id=thread_id, run_id=run_id)

    async def _load_candidates(
        self,
        state: AnalysisState,
    ) -> AsyncGenerator[BaseEvent]:
        yield self._state_event(state, phase="loading_candidates", error=None)
        candidates = await self._data_source.random_schools(10)
        yield self._state_event(
            state,
            phase="selecting",
            candidates=candidates,
            selected_school_codes=[],
            selected_date=None,
            result=None,
            error=None,
        )
        async for event in _assistant_message("무작위 학교 후보 10곳을 준비했습니다."):
            yield event

    async def _analyze(
        self,
        input_data: dict[str, Any],
        state: AnalysisState,
        thread_id: str,
        run_id: str,
    ) -> AsyncGenerator[BaseEvent]:
        if len(state.selected_school_codes) != 2:
            raise LunchDataError("서로 다른 학교 두 곳을 선택해 주세요.")
        if state.selected_school_codes[0] == state.selected_school_codes[1]:
            raise LunchDataError("같은 학교를 두 번 선택할 수 없습니다.")
        if state.selected_date is None:
            raise LunchDataError("비교할 날짜를 선택해 주세요.")
        validate_analysis_date(state.selected_date)

        by_code = {candidate.school_code: candidate for candidate in state.candidates}
        try:
            school_a, school_b = (
                by_code[code] for code in state.selected_school_codes
            )
        except KeyError as exc:
            raise LunchDataError("화면에 표시된 후보 학교 중 두 곳을 선택해 주세요.") from exc

        yield self._state_event(state, phase="loading_meals", error=None, result=None)
        school_a_meal, school_b_meal = await self._data_source.meals_for(
            school_a,
            school_b,
            state.selected_date,
        )
        yield self._state_event(state, phase="evaluating")

        workflow = build_evaluation_workflow(
            client=self._chat_client,
            school_a_meal=school_a_meal,
            school_b_meal=school_b_meal,
            instructions=self._instructions,
        )
        latest_message = _latest_user_message(input_data)
        specialist_prompt = evaluation_prompt(school_a_meal, school_b_meal)
        if latest_message:
            specialist_prompt = f"{latest_message}\n\n{specialist_prompt}"
        nested = AgentFrameworkWorkflow(workflow=workflow)
        nested_input = {
            "thread_id": thread_id,
            "run_id": run_id,
            "messages": [
                {
                    "id": str(uuid.uuid4()),
                    "role": "user",
                    "content": specialist_prompt,
                }
            ],
        }
        result: AnalysisResult | None = None
        judging_emitted = False
        async for event in nested.run(nested_input):
            if isinstance(event, (StepStartedEvent, StepFinishedEvent)):
                if (
                    isinstance(event, StepStartedEvent)
                    and event.step_name == "judge"
                    and not judging_emitted
                ):
                    yield self._state_event(state, phase="judging")
                    judging_emitted = True
                yield event
            elif isinstance(event, CustomEvent) and event.name == "workflow_output":
                result = AnalysisResult.model_validate(event.value)
            elif isinstance(event, RunErrorEvent):
                logger.error(
                    "Evaluation workflow failed: thread_id=%s run_id=%s code=%s message=%s",
                    thread_id,
                    run_id,
                    event.code,
                    event.message,
                )
                details = event.message.lower()
                if "rate limit" in details or "429" in details:
                    raise AnalysisWorkflowError(
                        "MODEL_RATE_LIMITED",
                        "AI 모델 요청 한도를 초과했습니다. 잠시 후 다시 시도해 주세요.",
                    )
                raise AnalysisWorkflowError(
                    "MODEL_UNAVAILABLE",
                    "AI 모델이 분석을 완료하지 못했습니다. 잠시 후 다시 시도해 주세요.",
                )
        if result is None:
            raise RuntimeError("Evaluation workflow completed without an AnalysisResult.")

        completed = self._state_event(
            state,
            phase="completed",
            result=result,
            error=None,
        )
        yield completed
        message = result.judge.headline + "\n" + "\n".join(result.judge.rationale)
        async for event in _assistant_message(message):
            yield event

    async def _user_error_events(
        self,
        state: AnalysisState,
        code: str,
        message: str,
    ) -> AsyncGenerator[BaseEvent]:
        error = AgentError(code=code, message=message, retryable=True)
        yield self._state_event(state, phase="error", error=error, result=None)
        async for event in _assistant_message(message):
            yield event

    async def _error_events(
        self,
        thread_id: str,
        run_id: str,
        code: str,
        message: str,
    ) -> AsyncGenerator[BaseEvent]:
        yield RunStartedEvent(thread_id=thread_id, run_id=run_id)
        error = AgentError(code=code, message=message)
        yield StateSnapshotEvent(
            snapshot=AnalysisState(phase="error", error=error).model_dump(
                mode="json",
                by_alias=True,
            )
        )
        async for event in _assistant_message(message):
            yield event
        yield RunFinishedEvent(thread_id=thread_id, run_id=run_id)

    @staticmethod
    def _state_event(
        state: AnalysisState,
        **updates: Any,
    ) -> StateSnapshotEvent:
        updated = state.model_copy(update=updates)
        return StateSnapshotEvent(
            snapshot=updated.model_dump(mode="json", by_alias=True)
        )


def _latest_user_message(input_data: dict[str, Any]) -> str | None:
    messages = input_data.get("messages")
    if not isinstance(messages, list):
        return None
    for message in reversed(messages):
        if not isinstance(message, dict) or message.get("role") != "user":
            continue
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text = "".join(
                str(item.get("text", ""))
                for item in content
                if isinstance(item, dict) and item.get("type") == "text"
            )
            return text or None
    return None


async def _assistant_message(text: str) -> AsyncGenerator[BaseEvent]:
    message_id = str(uuid.uuid4())
    yield TextMessageStartEvent(message_id=message_id, role="assistant")
    yield TextMessageContentEvent(message_id=message_id, delta=text)
    yield TextMessageEndEvent(message_id=message_id)
