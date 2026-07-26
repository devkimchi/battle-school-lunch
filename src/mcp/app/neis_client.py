from __future__ import annotations

from typing import Any

import httpx

from .openapi import ToolOperation


class NeisError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


_SUCCESS_CODES = {"INFO-000", "INFO-200"}


class NeisClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(15.0),
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def execute(
        self,
        operation: ToolOperation,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        query = {
            **operation.defaults,
            **arguments,
            "KEY": self._api_key,
            "Type": "json",
        }
        if operation.name == "getMealServiceDietInfo":
            query["MMEAL_SC_CODE"] = "2"

        try:
            response = await self._client.get(operation.path, params=query)
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise NeisError("TIMEOUT", "NEIS request timed out") from exc
        except httpx.HTTPStatusError as exc:
            raise NeisError(
                "HTTP-ERROR",
                f"NEIS returned HTTP {exc.response.status_code}",
            ) from exc
        except httpx.RequestError as exc:
            raise NeisError("HTTP-ERROR", "Unable to reach NEIS") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise NeisError("INVALID-JSON", "NEIS returned an invalid JSON response") from exc

        if not isinstance(payload, dict):
            raise NeisError("INVALID-JSON", "NEIS JSON response must be an object")

        code, message = _extract_result(payload, operation.response_key)
        if code not in _SUCCESS_CODES:
            raise NeisError(code, message)

        return payload


def _extract_result(payload: dict[str, Any], response_key: str) -> tuple[str, str]:
    result = payload.get("RESULT")
    if isinstance(result, dict):
        return _result_values(result)

    sections = payload.get(response_key)
    if isinstance(sections, list):
        for section in sections:
            if not isinstance(section, dict):
                continue
            heads = section.get("head")
            if not isinstance(heads, list):
                continue
            for head in heads:
                if not isinstance(head, dict):
                    continue
                nested_result = head.get("RESULT")
                if isinstance(nested_result, dict):
                    return _result_values(nested_result)

    raise NeisError("ERROR-UNKNOWN", "Unknown NEIS response")


def _result_values(result: dict[str, Any]) -> tuple[str, str]:
    code = result.get("CODE")
    message = result.get("MESSAGE")
    if not isinstance(code, str) or not isinstance(message, str):
        raise NeisError("ERROR-UNKNOWN", "Malformed NEIS result")
    return code, message
