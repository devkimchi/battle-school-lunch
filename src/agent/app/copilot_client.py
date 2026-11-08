from __future__ import annotations

from contextlib import suppress
from typing import Any, Literal, Sequence

from agent_framework import (
    ChatResponse,
    ChatResponseUpdate,
    Content,
    Message,
    ResponseStream,
    SupportsChatGetResponse,
)
from copilot import CopilotClient, CopilotSession
from copilot.generated.rpc import PermissionDecisionReject
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from .schemas import EvaluationArea, JudgeReport, SpecialistEvaluation


class _StructuredOutput(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        extra="forbid",
        populate_by_name=True,
        strict=True,
    )


class _SchoolAssessmentOutput(_StructuredOutput):
    score: int = Field(ge=1, le=5)
    evidence: list[str] = Field(min_length=1)
    strengths: list[str] = Field(min_length=1)
    risks: list[str]
    improvements: list[str] = Field(min_length=1)


class _SpecialistEvaluationOutput(_StructuredOutput):
    area: EvaluationArea
    school_a: _SchoolAssessmentOutput
    school_b: _SchoolAssessmentOutput
    comparison: str = Field(min_length=1)
    limitations: list[str]


class _JudgeReportOutput(_StructuredOutput):
    winner: Literal["school_a", "school_b", "tie"]
    headline: str = Field(min_length=1)
    rationale: list[str] = Field(min_length=1)
    school_a_improvements: list[str] = Field(min_length=1)
    school_b_improvements: list[str] = Field(min_length=1)
    quality_notes: list[str]
    limitations: list[str]


class CopilotAdapterError(ValueError):
    """Raised when the app requests a chat feature the Copilot adapter does not support."""


class CopilotStructuredChatClient(SupportsChatGetResponse[Any]):
    """Structured-output-only adapter for the app's two evaluation result types."""

    def __init__(self, client: CopilotClient, *, model: str = "auto") -> None:
        if not isinstance(model, str) or not model.strip():
            raise ValueError("model must be a non-empty string")
        self._client = client
        self._model = model
        self.additional_properties: dict[str, Any] = {}

    def get_response(
        self,
        messages: Sequence[Message],
        *,
        stream: bool = False,
        options: dict[str, Any] | None = None,
        compaction_strategy: Any = None,
        tokenizer: Any = None,
        function_invocation_kwargs: dict[str, Any] | None = None,
        client_kwargs: dict[str, Any] | None = None,
    ) -> Any:
        output_type, domain_type, model, instructions = self._request_options(options)
        if compaction_strategy is not None or tokenizer is not None:
            raise CopilotAdapterError("Compaction and tokenization options are not supported.")
        if function_invocation_kwargs:
            raise CopilotAdapterError("Function invocation arguments are not supported.")
        if client_kwargs and client_kwargs.keys() - {"session"}:
            raise CopilotAdapterError("Client-specific options are not supported.")
        prompt, system_instructions = _build_prompt(messages, instructions)

        if not stream:
            return self._run_request(
                prompt, output_type, domain_type, model, system_instructions
            )

        response_holder: list[ChatResponse[Any]] = []

        async def updates():
            response = await self._run_request(
                prompt, output_type, domain_type, model, system_instructions
            )
            response_holder.append(response)
            yield ChatResponseUpdate(
                contents=[Content.from_text(response.text)],
                role="assistant",
                response_id=response.response_id,
                conversation_id=response.conversation_id,
                model=response.model,
                finish_reason="stop",
            )

        def finalize(_updates: Sequence[ChatResponseUpdate]) -> ChatResponse[Any]:
            if not response_holder:
                raise RuntimeError("Copilot stream completed without a structured response.")
            return response_holder[0]

        return ResponseStream(updates(), finalizer=finalize)

    def _request_options(
        self,
        options: dict[str, Any] | None,
    ) -> tuple[type[BaseModel], type[BaseModel], str, str]:
        options = options or {}
        supported = {"instructions", "response_format", "model", "tool_choice"}
        unsupported = set(options) - supported
        if unsupported:
            raise CopilotAdapterError(
                f"Unsupported chat options: {', '.join(sorted(unsupported))}."
            )

        response_format = options.get("response_format")
        if response_format is SpecialistEvaluation:
            output_type: type[BaseModel] = _SpecialistEvaluationOutput
            domain_type: type[BaseModel] = SpecialistEvaluation
        elif response_format is JudgeReport:
            output_type = _JudgeReportOutput
            domain_type = JudgeReport
        else:
            raise CopilotAdapterError(
                "response_format must be SpecialistEvaluation or JudgeReport."
            )

        tool_choice = options.get("tool_choice")
        if tool_choice not in (None, "auto"):
            raise CopilotAdapterError("Tool selection is not supported.")

        instructions = options.get("instructions", "")
        if not isinstance(instructions, str):
            raise CopilotAdapterError("instructions must be a string.")

        model = options.get("model", self._model)
        if not isinstance(model, str) or not model.strip():
            raise CopilotAdapterError("model must be a non-empty string.")
        return output_type, domain_type, model, instructions

    async def _run_request(
        self,
        prompt: str,
        output_type: type[BaseModel],
        domain_type: type[BaseModel],
        model: str,
        instructions: str,
    ) -> ChatResponse[Any]:
        session: CopilotSession | None = None
        request_failed = False
        try:
            session = await self._client.create_session(
                model=model,
                system_message={"mode": "replace", "content": instructions},
                on_permission_request=_deny_permission_request,
                tools=[],
                available_tools=[],
                mcp_servers={},
                enable_config_discovery=False,
                enable_file_hooks=False,
                enable_skills=False,
                enable_host_git_operations=False,
                enable_session_store=False,
                enable_on_demand_instruction_discovery=False,
                skip_custom_instructions=True,
                custom_agents=[],
                agent_directories=[],
                hook_directories=[],
                plugin_directories=[],
                instruction_directories=[],
                enable_mcp_apps=False,
                enable_file_change_tracking=False,
                request_extensions=False,
                request_canvas_renderer=False,
                canvases=[],
            )
            structured_output = await session.send_and_wait_typed(
                prompt,
                output_type,
                agent_mode="interactive",
            )
            value = domain_type.model_validate(
                structured_output.model_dump(mode="python", by_alias=False)
            )
            return ChatResponse(
                messages=[Message(role="assistant", contents=[value.model_dump_json(by_alias=True)])],
                value=value,
                response_format=domain_type,
                model=model,
            )
        except BaseException:
            request_failed = True
            if session is not None:
                with suppress(BaseException):
                    await session.abort()
            raise
        finally:
            if session is not None:
                try:
                    await session.disconnect()
                except BaseException:
                    if not request_failed:
                        raise


async def _deny_permission_request(*_args: Any, **_kwargs: Any) -> PermissionDecisionReject:
    return PermissionDecisionReject(feedback="This analysis session does not allow tool permissions.")


def _build_prompt(messages: Sequence[Message], instructions: str) -> tuple[str, str]:
    system_messages: list[str] = [instructions] if instructions else []
    conversation: list[tuple[str, str]] = []
    for message in messages:
        role = str(message.role)
        text = message.text
        if role in {"system", "developer"}:
            if text:
                system_messages.append(text)
        elif role in {"user", "assistant"}:
            conversation.append((role, text))
        else:
            raise CopilotAdapterError(f"Message role '{role}' is not supported.")

    if not conversation or not any(role == "user" and text.strip() for role, text in conversation):
        raise CopilotAdapterError("At least one non-empty user message is required.")

    prompt = (
        conversation[0][1]
        if len(conversation) == 1 and conversation[0][0] == "user"
        else "\n\n".join(f"[{role}]\n{text}" for role, text in conversation)
    )
    return prompt, "\n\n---\n\n".join(system_messages)
