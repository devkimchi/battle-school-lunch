import json
from pathlib import Path

import pytest

from app.openapi import (
    OpenApiSpecError,
    default_openapi_path,
    load_openapi_definition,
)


pytestmark = pytest.mark.unit


def test_loads_expected_tools_from_openapi() -> None:
    definition = load_openapi_definition()

    assert definition.base_url == "https://open.neis.go.kr/hub"
    assert [operation.name for operation in definition.operations] == [
        "getSchoolInfo",
        "getMealServiceDietInfo",
    ]
    assert all(operation.description for operation in definition.operations)


def test_normalizes_defaults_and_lunch_constraint() -> None:
    definition = load_openapi_definition()
    school_schema = definition.operation("getSchoolInfo").input_schema
    meal_schema = definition.operation("getMealServiceDietInfo").input_schema

    assert school_schema["additionalProperties"] is False
    assert school_schema.get("required") is None
    assert school_schema["properties"]["Type"]["enum"] == ["json"]
    assert school_schema["properties"]["Type"]["default"] == "json"
    assert school_schema["properties"]["pIndex"]["default"] == 1
    assert school_schema["properties"]["pSize"]["default"] == 100

    assert meal_schema["required"] == ["ATPT_OFCDC_SC_CODE", "SD_SCHUL_CODE"]
    assert meal_schema["properties"]["MMEAL_SC_CODE"]["enum"] == ["2"]
    assert meal_schema["properties"]["MMEAL_SC_CODE"]["default"] == "2"
    assert "KEY" not in meal_schema["properties"]
    assert "NEIS_API_KEY" not in meal_schema["properties"]


def test_missing_spec_fails_explicitly(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.json"

    with pytest.raises(OpenApiSpecError, match="Unable to read OpenAPI document"):
        load_openapi_definition(missing_path)


def test_invalid_json_fails_explicitly(tmp_path: Path) -> None:
    spec_path = tmp_path / "openapi.json"
    spec_path.write_text("{invalid", encoding="utf-8")

    with pytest.raises(OpenApiSpecError, match="Invalid JSON"):
        load_openapi_definition(spec_path)


def test_missing_required_operation_fails_without_partial_definition(tmp_path: Path) -> None:
    document = json.loads(default_openapi_path().read_text(encoding="utf-8"))
    del document["paths"]["/mealServiceDietInfo"]
    spec_path = tmp_path / "openapi.json"
    spec_path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(OpenApiSpecError, match="getMealServiceDietInfo"):
        load_openapi_definition(spec_path)


def test_unknown_parameter_reference_fails_explicitly(tmp_path: Path) -> None:
    document = json.loads(default_openapi_path().read_text(encoding="utf-8"))
    document["paths"]["/schoolInfo"]["get"]["parameters"][0] = {
        "$ref": "#/components/parameters/Missing"
    }
    spec_path = tmp_path / "openapi.json"
    spec_path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(OpenApiSpecError, match="reference does not exist"):
        load_openapi_definition(spec_path)
