from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from agent_framework import SupportsChatGetResponse
from agent_framework.ag_ui import add_agent_framework_fastapi_endpoint
from agent_framework.foundry import FoundryChatClient
from azure.identity.aio import DefaultAzureCredential
from fastapi import FastAPI

from .agui import LunchAnalysisAGUIWorkflow
from .config import Settings, get_settings
from .data import LunchDataSource, McpLunchDataSource
from .schemas import AnalysisState


def create_app(
    *,
    settings: Settings | None = None,
    data_source: LunchDataSource | None = None,
    chat_client: SupportsChatGetResponse | None = None,
) -> FastAPI:
    owns_runtime = data_source is None or chat_client is None
    resolved_settings = settings or (get_settings() if owns_runtime else None)

    mcp_tool = None
    credential = None
    if data_source is None:
        assert resolved_settings is not None
        mcp_tool, data_source = McpLunchDataSource.create(str(resolved_settings.mcp_url))
    if chat_client is None:
        assert resolved_settings is not None
        credential = DefaultAzureCredential()
        chat_client = FoundryChatClient(
            project_endpoint=str(resolved_settings.foundry_project_endpoint),
            model=resolved_settings.foundry_model_deployment_name,
            credential=credential,
        )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        if mcp_tool is not None:
            async with mcp_tool:
                try:
                    yield
                finally:
                    if credential is not None:
                        await credential.close()
        else:
            yield

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
