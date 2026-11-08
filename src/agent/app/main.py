import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager, suppress
from pathlib import Path
from typing import Any

from agent_framework import SupportsChatGetResponse
from agent_framework.ag_ui import add_agent_framework_fastapi_endpoint
from copilot import CopilotClient, RuntimeConnection
from fastapi import FastAPI

from .agui import LunchAnalysisAGUIWorkflow
from .config import Settings, get_settings
from .copilot_client import CopilotStructuredChatClient
from .data import LunchDataSource, McpLunchDataSource
from .schemas import AnalysisState


class _LifespanChatClient:
    def __init__(self) -> None:
        self.client: CopilotStructuredChatClient | None = None
        self.additional_properties: dict[str, Any] = {}

    def get_response(self, *args: Any, **kwargs: Any) -> Any:
        if self.client is None:
            raise RuntimeError("Copilot runtime is not running.")
        return self.client.get_response(*args, **kwargs)


def _create_copilot_runtime(settings: Settings) -> CopilotClient:
    token_variables = {"COPILOT_GITHUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"}
    child_env = {
        name: value for name, value in os.environ.items()
        if name.upper() not in token_variables
    }
    local = settings.copilot_auth_mode == "local"
    return CopilotClient(
        connection=RuntimeConnection.for_stdio(),
        mode="copilot-cli" if local else "empty",
        base_directory=(
            None if local else str(Path(__file__).resolve().parent.parent / ".copilot-runtime")
        ),
        use_logged_in_user=local,
        github_token=(
            None if local else settings.copilot_github_token.get_secret_value()
        ),
        env=child_env,
        log_level="none",
    )


async def _stop_copilot_runtime(runtime: CopilotClient) -> None:
    try:
        await runtime.stop()
    except BaseException:
        with suppress(BaseException):
            await runtime.force_stop()
        raise RuntimeError("Copilot runtime shutdown failed.") from None


async def _complete_cleanup(stack: AsyncExitStack) -> None:
    # Complete owned-process cleanup even if the worker is cancelled again.
    task = asyncio.create_task(stack.aclose())
    cancelled = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            cancelled = True
    if cancelled:
        with suppress(BaseException):
            task.result()
        raise asyncio.CancelledError
    task.result()


def create_app(
    *,
    settings: Settings | None = None,
    data_source: LunchDataSource | None = None,
    chat_client: SupportsChatGetResponse | None = None,
) -> FastAPI:
    owns_runtime = data_source is None or chat_client is None
    resolved_settings = settings or (get_settings() if owns_runtime else None)

    mcp_tool = None
    managed_chat_client = None
    if data_source is None:
        assert resolved_settings is not None
        mcp_tool, data_source = McpLunchDataSource.create(str(resolved_settings.mcp_url))
    if chat_client is None:
        assert resolved_settings is not None
        managed_chat_client = _LifespanChatClient()
        chat_client = managed_chat_client

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        stack = AsyncExitStack()
        failed = False
        try:
            if managed_chat_client is not None:
                assert resolved_settings is not None
                try:
                    runtime = _create_copilot_runtime(resolved_settings)
                except Exception:
                    raise RuntimeError("Copilot runtime configuration failed.") from None
                stack.push_async_callback(_stop_copilot_runtime, runtime)
                try:
                    await runtime.start()
                except Exception:
                    raise RuntimeError("Copilot runtime startup failed.") from None
                managed_chat_client.client = CopilotStructuredChatClient(
                    runtime, model=resolved_settings.copilot_model
                )
                stack.callback(setattr, managed_chat_client, "client", None)
            if mcp_tool is not None:
                stack.push_async_exit(mcp_tool)
                try:
                    await mcp_tool.__aenter__()
                except Exception:
                    raise RuntimeError("MCP runtime startup failed.") from None
            yield
        except BaseException:
            failed = True
            raise
        finally:
            try:
                await _complete_cleanup(stack)
            except asyncio.CancelledError:
                if not failed:
                    raise
            except Exception:
                if not failed:
                    raise RuntimeError("Agent runtime shutdown failed.") from None

    app = FastAPI(title="School Lunch Analysis Agent", lifespan=lifespan)
    runner = LunchAnalysisAGUIWorkflow(
        data_source=data_source,
        chat_client=chat_client,
    )
    add_agent_framework_fastapi_endpoint(
        app,
        runner,
        "/agent",
        state_schema=AnalysisState,
        default_state=AnalysisState().model_dump(mode="json", by_alias=True),
        keepalive_seconds=15,
    )

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
