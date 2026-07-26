from typing import Any

import httpx
import pytest
import respx

from app.neis_client import NeisClient, NeisError
from app.openapi import ToolOperation, load_openapi_definition


pytestmark = pytest.mark.integration
_BASE_URL = "https://neis.example.test"


def _operation(name: str) -> ToolOperation:
    return load_openapi_definition().operation(name)


def _success_payload(response_key: str) -> dict[str, Any]:
    return {
        response_key: [
            {"head": [{"RESULT": {"CODE": "INFO-000", "MESSAGE": "정상 처리"}}]},
            {"row": [{"value": "ok"}]},
        ]
    }


@respx.mock
async def test_execute_injects_secret_defaults_and_lunch_code() -> None:
    route = respx.get(f"{_BASE_URL}/mealServiceDietInfo").mock(
        return_value=httpx.Response(200, json=_success_payload("mealServiceDietInfo"))
    )
    client = NeisClient(_BASE_URL, "server-secret")

    try:
        payload = await client.execute(
            _operation("getMealServiceDietInfo"),
            {
                "ATPT_OFCDC_SC_CODE": "B10",
                "SD_SCHUL_CODE": "7010115",
                "MMEAL_SC_CODE": "1",
            },
        )
    finally:
        await client.aclose()

    assert payload == _success_payload("mealServiceDietInfo")
    query = route.calls.last.request.url.params
    assert query["KEY"] == "server-secret"
    assert query["Type"] == "json"
    assert query["pIndex"] == "1"
    assert query["pSize"] == "100"
    assert query["MMEAL_SC_CODE"] == "2"


@respx.mock
async def test_info_200_returns_original_no_data_payload() -> None:
    payload = {"RESULT": {"CODE": "INFO-200", "MESSAGE": "해당하는 데이터가 없습니다."}}
    respx.get(f"{_BASE_URL}/schoolInfo").mock(return_value=httpx.Response(200, json=payload))
    client = NeisClient(_BASE_URL, "secret")

    try:
        result = await client.execute(_operation("getSchoolInfo"), {"SCHUL_NM": "없는학교"})
    finally:
        await client.aclose()

    assert result == payload


@respx.mock
async def test_neis_error_preserves_code_and_message() -> None:
    respx.get(f"{_BASE_URL}/schoolInfo").mock(
        return_value=httpx.Response(
            200,
            json={"RESULT": {"CODE": "ERROR-290", "MESSAGE": "인증키가 유효하지 않습니다."}},
        )
    )
    client = NeisClient(_BASE_URL, "secret")

    try:
        with pytest.raises(NeisError) as error:
            await client.execute(_operation("getSchoolInfo"), {})
    finally:
        await client.aclose()

    assert error.value.code == "ERROR-290"
    assert error.value.message == "인증키가 유효하지 않습니다."


@respx.mock
async def test_http_error_does_not_expose_secret() -> None:
    respx.get(f"{_BASE_URL}/schoolInfo").mock(return_value=httpx.Response(503))
    client = NeisClient(_BASE_URL, "do-not-leak")

    try:
        with pytest.raises(NeisError) as error:
            await client.execute(_operation("getSchoolInfo"), {})
    finally:
        await client.aclose()

    assert error.value.code == "HTTP-ERROR"
    assert error.value.message == "NEIS returned HTTP 503"
    assert "do-not-leak" not in str(error.value)


@respx.mock
async def test_timeout_maps_to_explicit_error() -> None:
    respx.get(f"{_BASE_URL}/schoolInfo").mock(
        side_effect=httpx.ReadTimeout("timed out")
    )
    client = NeisClient(_BASE_URL, "secret")

    try:
        with pytest.raises(NeisError, match="TIMEOUT"):
            await client.execute(_operation("getSchoolInfo"), {})
    finally:
        await client.aclose()


@respx.mock
async def test_invalid_json_maps_to_explicit_error() -> None:
    respx.get(f"{_BASE_URL}/schoolInfo").mock(
        return_value=httpx.Response(200, text="<xml />")
    )
    client = NeisClient(_BASE_URL, "secret")

    try:
        with pytest.raises(NeisError, match="INVALID-JSON"):
            await client.execute(_operation("getSchoolInfo"), {})
    finally:
        await client.aclose()
