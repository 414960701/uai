"""Reusable, non-secret JSON Schema compilation and validation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError
from jsonschema.validators import validator_for


@dataclass(frozen=True)
class SchemaViolation:
    path: str = "/"
    keyword: str = "schema"


class InvalidJsonSchema(ValueError):
    def __init__(self, violation: SchemaViolation) -> None:
        self.violation = violation
        super().__init__(
            f"invalid JSON Schema at {violation.path}; "
            f"keyword={violation.keyword}"
        )


def json_pointer(path: Any) -> str:
    parts = [
        str(item).replace("~", "~0").replace("/", "~1")
        for item in path
    ]
    return "/" + "/".join(parts) if parts else "/"


def compile_json_schema(schema: Dict[str, Any]) -> Any:
    dialect = schema.get("$schema")
    validator_class = (
        validator_for(schema, default=None)
        if dialect is not None
        else Draft202012Validator
    )
    if validator_class is None:
        raise InvalidJsonSchema(
            SchemaViolation(keyword="$schema"),
        )
    try:
        validator_class.check_schema(schema)
        return validator_class(schema, format_checker=FormatChecker())
    except SchemaError as exc:
        raise InvalidJsonSchema(
            SchemaViolation(
                path=json_pointer(exc.absolute_path),
                keyword=str(exc.validator or "schema"),
            )
        ) from exc


def first_schema_violation(
    validator: Any,
    value: Any,
) -> Optional[SchemaViolation]:
    """Return the first deterministic violation, or None when valid.

    Exception messages and invalid values are intentionally discarded so caller
    errors, events and API responses cannot echo provider/tool arguments.
    """

    try:
        errors = sorted(
            validator.iter_errors(value),
            key=lambda error: (
                tuple(str(item) for item in error.absolute_path),
                tuple(str(item) for item in error.absolute_schema_path),
            ),
        )
    except Exception:
        return SchemaViolation(keyword="schema_resolution")
    if not errors:
        return None
    first = errors[0]
    return SchemaViolation(
        path=json_pointer(first.absolute_path),
        keyword=str(first.validator or "schema"),
    )
