from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route
from starlette.types import Receive, Scope, Send

from .config import Settings, get_settings
from .neis_client import NeisClient, NeisError
from .openapi import OpenApiDefinition, ToolOperation, load_openapi_definition


def create_mcp_server(
    definition: OpenApiDefinition,
    neis_client: NeisClient,
) -> Server[None]:
    server: Server[None] = Server(
        "school-lunch-mcp",
        version="0.1.0",
        instructions="Query NEIS school information and lunch-only meal data.",
    )
    operations = {operation.name: operation for operation in definition.operations}
    tools = [_to_mcp_tool(operation) for operation in definition.operations]

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return tools

    @server.call_tool()
    async def call_tool(
        name: str,
        arguments: dict[str, Any],
    ) -> types.CallToolResult:
        operation = operations.get(name)
        if operation is None:
            return _error_result("TOOL-NOT-FOUND", f"Unknown tool: {name}")

        try:
            payload = await neis_client.execute(operation, arguments)
        except NeisError as exc:
            return _error_result(exc.code, exc.message)

        return types.CallToolResult(
            content=[
                types.TextContent(
                    type="text",
                    text=json.dumps(payload, ensure_ascii=False),
                )
            ],
            structuredContent=payload,
        )

    return server


def create_app(
    *,
    definition: OpenApiDefinition | None = None,
    settings: Settings | None = None,
    neis_client: NeisClient | None = None,
) -> Starlette:
    resolved_definition = definition or load_openapi_definition()
    resolved_settings = settings or get_settings()
    owns_client = neis_client is None
    client = neis_client or NeisClient(
        resolved_settings.neis_base_url or resolved_definition.base_url,
        resolved_settings.neis_api_key,
    )
    mcp_server = create_mcp_server(resolved_definition, client)
    session_manager = StreamableHTTPSessionManager(
        app=mcp_server,
        json_response=True,
        stateless=True,
    )

    async def handle_mcp(scope: Scope, receive: Receive, send: Send) -> None:
        await session_manager.handle_request(scope, receive, send)

    @asynccontextmanager
    async def lifespan(application: Starlette) -> AsyncIterator[None]:
        application.state.mcp_server = mcp_server
        async with session_manager.run():
            try:
                yield
            finally:
                if owns_client:
                    await client.aclose()

    return Starlette(
        routes=[
            Route("/health", endpoint=health),
            Mount("/mcp", app=handle_mcp),
        ],
        lifespan=lifespan,
    )


async def health(_request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


def _to_mcp_tool(operation: ToolOperation) -> types.Tool:
    return types.Tool(
        name=operation.name,
        description=operation.description,
        inputSchema=operation.input_schema,
    )


def _error_result(code: str, message: str) -> types.CallToolResult:
    error = {"code": code, "message": message}
    return types.CallToolResult(
        content=[
            types.TextContent(
                type="text",
                text=json.dumps(error, ensure_ascii=False),
            )
        ],
        structuredContent=error,
        isError=True,
    )


app = create_app()
