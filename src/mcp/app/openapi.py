from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from jsonschema import Draft7Validator, SchemaError


class OpenApiSpecError(RuntimeError):
    """Raised when the MCP tool source specification cannot be loaded safely."""


@dataclass(frozen=True)
class ToolOperation:
    name: str
    description: str
    path: str
    response_key: str
    input_schema: dict[str, Any]
    defaults: dict[str, Any]


@dataclass(frozen=True)
class OpenApiDefinition:
    base_url: str
    operations: tuple[ToolOperation, ...]

    def operation(self, name: str) -> ToolOperation:
        for operation in self.operations:
            if operation.name == name:
                return operation
        raise KeyError(name)


_EXPECTED_OPERATIONS = {"getSchoolInfo", "getMealServiceDietInfo"}
_OPTIONAL_DEFAULTS: dict[str, Any] = {
    "Type": "json",
    "pIndex": 1,
    "pSize": 100,
}
_SCHEMA_FIELDS = {
    "type",
    "format",
    "enum",
    "pattern",
    "minimum",
    "maximum",
    "minLength",
    "maxLength",
    "default",
}


def default_openapi_path() -> Path:
    module_path = Path(__file__).resolve()
    source_path = module_path.parents[2] / "openapi.json"
    if source_path.is_file():
        return source_path
    return module_path.parents[1] / "openapi.json"


def load_openapi_definition(path: Path | None = None) -> OpenApiDefinition:
    spec_path = path or default_openapi_path()
    document = _read_document(spec_path)
    base_url = _read_base_url(document)
    operations = _read_operations(document)

    missing = sorted(_EXPECTED_OPERATIONS - {operation.name for operation in operations})
    if missing:
        raise OpenApiSpecError(f"OpenAPI document is missing required operations: {', '.join(missing)}")

    return OpenApiDefinition(base_url=base_url, operations=tuple(operations))


def _read_document(path: Path) -> dict[str, Any]:
    try:
        raw_document = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise OpenApiSpecError(f"Unable to read OpenAPI document at {path}: {exc}") from exc

    try:
        document = json.loads(raw_document)
    except json.JSONDecodeError as exc:
        raise OpenApiSpecError(f"Invalid JSON in OpenAPI document at {path}: {exc}") from exc

    if not isinstance(document, dict):
        raise OpenApiSpecError("OpenAPI document root must be an object")

    version = document.get("openapi")
    if not isinstance(version, str) or not version.startswith("3.0."):
        raise OpenApiSpecError("OpenAPI document must use OpenAPI 3.0.x")

    return document


def _read_base_url(document: dict[str, Any]) -> str:
    servers = document.get("servers")
    if not isinstance(servers, list) or not servers or not isinstance(servers[0], dict):
        raise OpenApiSpecError("OpenAPI document must define a default server")

    base_url = servers[0].get("url")
    if not isinstance(base_url, str):
        raise OpenApiSpecError("OpenAPI default server URL must be a string")

    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.query or parsed.fragment:
        raise OpenApiSpecError(f"OpenAPI default server URL is invalid: {base_url}")

    return base_url.rstrip("/")


def _read_operations(document: dict[str, Any]) -> list[ToolOperation]:
    paths = document.get("paths")
    if not isinstance(paths, dict):
        raise OpenApiSpecError("OpenAPI document must define paths")

    components = document.get("components")
    if not isinstance(components, dict):
        raise OpenApiSpecError("OpenAPI document must define components")

    component_parameters = components.get("parameters", {})
    if not isinstance(component_parameters, dict):
        raise OpenApiSpecError("OpenAPI components.parameters must be an object")

    operations: list[ToolOperation] = []
    operation_names: set[str] = set()

    for path, path_item in paths.items():
        if not isinstance(path, str) or not path.startswith("/") or not isinstance(path_item, dict):
            raise OpenApiSpecError("Every OpenAPI path must be an absolute path object")

        operation = path_item.get("get")
        if operation is None:
            continue
        if not isinstance(operation, dict):
            raise OpenApiSpecError(f"GET operation for {path} must be an object")

        name = operation.get("operationId")
        if not isinstance(name, str) or not name:
            raise OpenApiSpecError(f"GET operation for {path} must define operationId")
        if name in operation_names:
            raise OpenApiSpecError(f"Duplicate OpenAPI operationId: {name}")
        operation_names.add(name)

        description = operation.get("description") or operation.get("summary")
        if not isinstance(description, str) or not description:
            raise OpenApiSpecError(f"OpenAPI operation {name} must define a description or summary")

        path_parameters = path_item.get("parameters", [])
        operation_parameters = operation.get("parameters", [])
        if not isinstance(path_parameters, list) or not isinstance(operation_parameters, list):
            raise OpenApiSpecError(f"OpenAPI operation {name} parameters must be arrays")

        input_schema, defaults = _build_input_schema(
            name,
            [*path_parameters, *operation_parameters],
            component_parameters,
        )
        operations.append(
            ToolOperation(
                name=name,
                description=description,
                path=path,
                response_key=path.rsplit("/", maxsplit=1)[-1],
                input_schema=input_schema,
                defaults=defaults,
            )
        )

    if not operations:
        raise OpenApiSpecError("OpenAPI document does not define any GET operations")

    return operations


def _build_input_schema(
    operation_name: str,
    parameters: list[Any],
    component_parameters: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    properties: dict[str, Any] = {}
    required: list[str] = []
    defaults: dict[str, Any] = {}

    for raw_parameter in parameters:
        parameter = _resolve_parameter(raw_parameter, component_parameters)
        name = parameter.get("name")
        if not isinstance(name, str) or not name:
            raise OpenApiSpecError(f"OpenAPI operation {operation_name} has a parameter without a name")
        if name in properties:
            raise OpenApiSpecError(f"OpenAPI operation {operation_name} has duplicate parameter {name}")
        if parameter.get("in") != "query":
            raise OpenApiSpecError(
                f"OpenAPI operation {operation_name} uses unsupported non-query parameter {name}"
            )

        raw_schema = parameter.get("schema")
        if not isinstance(raw_schema, dict):
            raise OpenApiSpecError(f"OpenAPI parameter {name} must define a schema")

        property_schema = {
            key: deepcopy(value)
            for key, value in raw_schema.items()
            if key in _SCHEMA_FIELDS
        }
        description = parameter.get("description")
        if isinstance(description, str) and description:
            property_schema["description"] = description

        if name in _OPTIONAL_DEFAULTS:
            default = _OPTIONAL_DEFAULTS[name]
            property_schema["default"] = default
            defaults[name] = default
            if name == "Type":
                property_schema["enum"] = ["json"]
        elif operation_name == "getMealServiceDietInfo" and name == "MMEAL_SC_CODE":
            property_schema["enum"] = ["2"]
            property_schema["default"] = "2"
            defaults[name] = "2"
        elif parameter.get("required") is True:
            required.append(name)
        elif "default" in property_schema:
            defaults[name] = property_schema["default"]

        properties[name] = property_schema

    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
    if required:
        input_schema["required"] = required

    try:
        Draft7Validator.check_schema(input_schema)
    except SchemaError as exc:
        raise OpenApiSpecError(f"Invalid generated schema for {operation_name}: {exc.message}") from exc

    return input_schema, defaults


def _resolve_parameter(
    raw_parameter: Any,
    component_parameters: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(raw_parameter, dict):
        raise OpenApiSpecError("OpenAPI parameters must be objects")

    reference = raw_parameter.get("$ref")
    if reference is None:
        return raw_parameter
    if not isinstance(reference, str):
        raise OpenApiSpecError("OpenAPI parameter $ref must be a string")

    prefix = "#/components/parameters/"
    if not reference.startswith(prefix):
        raise OpenApiSpecError(f"Unsupported OpenAPI parameter reference: {reference}")

    component_name = reference.removeprefix(prefix)
    parameter = component_parameters.get(component_name)
    if not isinstance(parameter, dict):
        raise OpenApiSpecError(f"OpenAPI parameter reference does not exist: {reference}")

    return parameter
