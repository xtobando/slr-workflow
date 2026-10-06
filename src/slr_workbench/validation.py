"""Pure-Python dataclass contracts, recursive validation and JSON Schema generation.

The model_* methods retain the workbench's existing serialization interface so
stored proposals, decisions and adapters do not need a database migration.
"""

from __future__ import annotations

import copy
import json
import math
import re
import types
from collections.abc import Mapping
from dataclasses import MISSING, fields
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from functools import cache
from typing import Any, Literal, Self, Union, get_args, get_origin, get_type_hints


@cache
def annotations(model: type) -> dict[str, Any]:
    return get_type_hints(model)


def validate_value(annotation: Any, value: Any, path: str) -> Any:
    """Validate nested values, preserving the input conversions used by our contracts."""
    origin, args = get_origin(annotation), get_args(annotation)
    if annotation is Any:
        return value
    if origin in (Union, types.UnionType):
        for candidate in args:
            try:
                return validate_value(candidate, value, path)
            except (ValueError, TypeError):
                pass
        raise ValueError(f"{path}: value does not match any permitted type")
    if annotation is type(None):
        if value is None:
            return None
        raise ValueError(f"{path}: expected null")
    if origin is Literal:
        for allowed in args:
            if value == allowed:
                return allowed
        raise ValueError(f"{path}: expected one of {args}")
    if isinstance(annotation, type) and issubclass(annotation, StrictModel):
        try:
            return annotation.model_validate(value)
        except (ValueError, TypeError) as error:
            raise ValueError(f"{path}: {error}") from error
    if origin is list:
        if not isinstance(value, (list, tuple, set, frozenset)):
            raise ValueError(f"{path}: expected a list")
        return [validate_value(args[0], item, f"{path}[{i}]") for i, item in enumerate(value)]
    if origin is dict:
        if not isinstance(value, Mapping):
            raise ValueError(f"{path}: expected an object")
        return {
            validate_value(args[0], key, f"{path}.key"): validate_value(
                args[1], item, f"{path}.{key}"
            )
            for key, item in value.items()
        }
    if annotation is str:
        if isinstance(value, (bytes, bytearray)):
            value = value.decode("utf-8")
        if isinstance(value, str):
            return value
    elif annotation is bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)) and value in (0, 1):
            return bool(value)
        if isinstance(value, (str, bytes)):
            text = value.decode() if isinstance(value, bytes) else value
            if text.lower() in ("1", "true", "t", "yes", "y", "on"):
                return True
            if text.lower() in ("0", "false", "f", "no", "n", "off"):
                return False
    elif annotation is int:
        if isinstance(value, int):
            return int(value)
        if isinstance(value, float) and math.isfinite(value) and value.is_integer():
            return int(value)
        if isinstance(value, (str, bytes)):
            try:
                text = value.decode() if isinstance(value, bytes) else value
                if not re.fullmatch(r"[+-]?[0-9](?:_?[0-9])*(?:\.0+)?", text.strip()):
                    raise ValueError(f"{path}: expected an integer")
                number = Decimal(text)
                if number.is_finite() and number == number.to_integral_value():
                    return int(number)
            except InvalidOperation:
                pass
    elif annotation is date:
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        try:
            if isinstance(value, (str, bytes)):
                text = value.decode() if isinstance(value, bytes) else value
                if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
                    return date.fromisoformat(text)
                if re.match(r"\d{4}-\d{2}-\d{2}[Tt ]", text):
                    value = datetime.fromisoformat(text)
                else:
                    value = float(text)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                seconds = value / 1000 if abs(value) > 20_000_000_000 else value
                value = datetime.fromtimestamp(seconds, UTC)
            if isinstance(value, datetime) and value.time().isoformat() == "00:00:00":
                return value.date()
        except (ValueError, OverflowError, OSError):
            pass
    raise ValueError(f"{path}: expected {getattr(annotation, '__name__', annotation)}")


def serialize(value: Any, mode: str) -> Any:
    if isinstance(value, StrictModel):
        return value.model_dump(mode=mode)
    if isinstance(value, dict):
        return {key: serialize(item, mode) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [serialize(item, mode) for item in value]
    if mode == "json" and isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


class StrictModel:
    """Validated keyword-only dataclasses with independent mutable defaults."""

    def __post_init__(self) -> None:
        hints = annotations(type(self))
        for item in fields(self):
            path = f"{type(self).__name__}.{item.name}"
            value = validate_value(hints[item.name], getattr(self, item.name), path)
            if value is not None:
                if "min_length" in item.metadata and len(value) < item.metadata["min_length"]:
                    raise ValueError(f"{path}: minimum length is {item.metadata['min_length']}")
                if "ge" in item.metadata and value < item.metadata["ge"]:
                    raise ValueError(f"{path}: minimum value is {item.metadata['ge']}")
            setattr(self, item.name, value)
        self.validate_model()

    def validate_model(self) -> None:
        """Subclasses implement cross-field scientific configuration constraints."""

    @classmethod
    def model_validate(cls, value: Any) -> Self:
        if isinstance(value, cls):
            return value
        if not isinstance(value, Mapping):
            # Keep validation failures ValueError-compatible with stored-input callers.
            raise ValueError(f"{cls.__name__}: expected an object")  # noqa: TRY004
        declared = {item.name for item in fields(cls)}
        unknown = set(value) - declared
        if unknown:
            raise ValueError(f"{cls.__name__}: unknown fields: {', '.join(map(str, unknown))}")
        missing = [
            item.name
            for item in fields(cls)
            if item.default is MISSING
            and item.default_factory is MISSING
            and item.name not in value
        ]
        if missing:
            raise ValueError(f"{cls.__name__}: missing required fields: {', '.join(missing)}")
        return cls(**value)

    @classmethod
    def model_validate_json(cls, value: str | bytes) -> Self:
        return cls.model_validate(json.loads(value))

    def model_dump(self, *, mode: str = "python") -> dict[str, Any]:
        if mode not in ("python", "json"):
            raise ValueError("Serialization mode must be python or json")
        return {item.name: serialize(getattr(self, item.name), mode) for item in fields(self)}

    def model_dump_json(self, *, indent: int | None = None) -> str:
        return json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=False,
            indent=indent,
            separators=(",", ":") if indent is None else None,
        )

    def model_copy(self, *, update: dict[str, Any] | None = None, deep: bool = False) -> Self:
        """Copy trusted model state; like the previous API, updates are not revalidated."""
        result = copy.deepcopy(self) if deep else copy.copy(self)
        for key, value in (update or {}).items():
            if key not in annotations(type(self)):
                raise ValueError(f"Unknown field: {key}")
            setattr(result, key, value)
        return result

    @classmethod
    def model_json_schema(cls) -> dict[str, Any]:
        definitions: dict[str, Any] = {}

        def type_schema(annotation: Any, metadata: Mapping[str, Any]) -> dict[str, Any]:
            origin, args = get_origin(annotation), get_args(annotation)
            if annotation is Any:
                return {}
            if origin in (Union, types.UnionType):
                return {"anyOf": [type_schema(part, metadata) for part in args]}
            if isinstance(annotation, type) and issubclass(annotation, StrictModel):
                if annotation.__name__ not in definitions:
                    definitions[annotation.__name__] = object_schema(annotation)
                return {"$ref": f"#/$defs/{annotation.__name__}"}
            if origin is Literal:
                result = {"const": args[0]} if len(args) == 1 else {"enum": list(args)}
                result["type"] = "string" if isinstance(args[0], str) else "integer"
            elif origin is list:
                result = {"type": "array", "items": type_schema(args[0], {})}
            elif origin is dict:
                result = {
                    "type": "object",
                    "additionalProperties": type_schema(args[1], {}) or True,
                }
            else:
                result = {
                    "type": {
                        str: "string",
                        int: "integer",
                        bool: "boolean",
                        date: "string",
                        type(None): "null",
                    }[annotation]
                }
                if annotation is date:
                    result["format"] = "date"
            if annotation is not type(None):
                if "min_length" in metadata:
                    result["minItems" if origin is list else "minLength"] = metadata["min_length"]
                if "ge" in metadata:
                    result["minimum"] = metadata["ge"]
            return result

        def object_schema(model: type[StrictModel]) -> dict[str, Any]:
            properties, required = {}, []
            for item in fields(model):
                schema = type_schema(annotations(model)[item.name], item.metadata)
                if "$ref" not in schema:
                    schema["title"] = item.name.replace("_", " ").title()
                if item.default is not MISSING:
                    schema["default"] = serialize(item.default, "json")
                elif item.default_factory is MISSING:
                    required.append(item.name)
                properties[item.name] = schema
            result = {
                "additionalProperties": False,
                "properties": properties,
                "title": model.__name__,
                "type": "object",
            }
            if required:
                result["required"] = required
            return result

        root = object_schema(cls)
        return {"$defs": dict(sorted(definitions.items())), **root} if definitions else root
