from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import httpx
import pytest
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.memory import create_connected_server_and_client_session

from app.config import Settings
from app.main import create_app, create_mcp_server
from app.neis_client import NeisClient, NeisError
from app.openapi import load_openapi_definition


pytestmark = pytest.mark.integration


@pytest.fixture
def neis_client() -> AsyncMock:
    return AsyncMock(spec=NeisClient)


@asynccontextmanager
async def _mcp_session(neis_client: AsyncMock) -> AsyncIterator[ClientSession]:
    server = create_mcp_server(load_openapi_definition(), neis_client)
    async with create_connected_server_and_client_session(
        server,
        raise_exceptions=True,
    ) as session:
        yield session


async def test_lists_openapi_derived_tools(neis_client: AsyncMock) -> None:
    async with _mcp_session(neis_client) as session:
        result = await session.list_tools()

    assert [tool.name for tool in result.tools] == [
        "getSchoolInfo",
        "getMealServiceDietInfo",
    ]
    meal_tool = next(tool for tool in result.tools if tool.name == "getMealServiceDietInfo")
    assert meal_tool.inputSchema["required"] == [
        "ATPT_OFCDC_SC_CODE",
        "SD_SCHUL_CODE",
    ]
    assert meal_tool.inputSchema["properties"]["MMEAL_SC_CODE"]["enum"] == ["2"]
    assert "KEY" not in meal_tool.inputSchema["properties"]


async def test_returns_neis_json_as_structured_content(
    neis_client: AsyncMock,
) -> None:
    payload = {
        "schoolInfo": [
            {"head": [{"RESULT": {"CODE": "INFO-000", "MESSAGE": "OK"}}]},
            {"row": [{"SCHUL_NM": "서울고등학교"}]},
        ]
    }
    neis_client.execute.return_value = payload

    async with _mcp_session(neis_client) as session:
        result = await session.call_tool("getSchoolInfo", {"SCHUL_NM": "서울고"})

    assert result.isError is False
    assert result.structuredContent == payload
    assert "서울고등학교" in result.content[0].text


async def test_neis_error_returns_mcp_tool_error(
    neis_client: AsyncMock,
) -> None:
    neis_client.execute.side_effect = NeisError("ERROR-290", "invalid key")

    async with _mcp_session(neis_client) as session:
        result = await session.call_tool("getSchoolInfo", {})

    assert result.isError is True
    assert result.structuredContent == {
        "code": "ERROR-290",
        "message": "invalid key",
    }


async def test_schema_validation_returns_mcp_tool_error(
    neis_client: AsyncMock,
) -> None:
    async with _mcp_session(neis_client) as session:
        result = await session.call_tool("getMealServiceDietInfo", {})

    assert result.isError is True
    assert "Input validation error" in result.content[0].text


async def test_streamable_http_uses_exact_mcp_path(neis_client: AsyncMock) -> None:
    application = create_app(
        settings=Settings(neis_api_key="test"),
        neis_client=neis_client,
    )
    transport = httpx.ASGITransport(app=application)

    async with application.router.lifespan_context(application):
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
            follow_redirects=False,
        ) as http_client:
            health = await http_client.get("/health")
            assert health.status_code == 200
            assert health.json() == {"status": "ok"}

            async with streamable_http_client(
                "http://testserver/mcp",
                http_client=http_client,
            ) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.list_tools()

    assert [tool.name for tool in result.tools] == [
        "getSchoolInfo",
        "getMealServiceDietInfo",
    ]
