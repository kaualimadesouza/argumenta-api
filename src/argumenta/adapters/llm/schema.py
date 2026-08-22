"""The same pydantic schema, in the dialect each vendor speaks. One model
defines the contract; nobody hand writes a second copy that drifts."""

from copy import deepcopy
from typing import Any, cast

_DROPPED = ("title", "default", "$schema")


def _walk(node: Any, transform: Any) -> Any:
    if isinstance(node, dict):
        return transform({key: _walk(value, transform) for key, value in node.items()})
    if isinstance(node, list):
        return [_walk(item, transform) for item in node]
    return node


def strict_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """OpenAI strict mode: no unknown keys, and every property required. A field
    that is optional in pydantic is still sent, as null."""

    def tighten(node: dict[str, Any]) -> dict[str, Any]:
        if node.get("type") != "object" or "properties" not in node:
            return node
        return {**node, "additionalProperties": False, "required": list(node["properties"])}

    return cast(dict[str, Any], _walk(deepcopy(schema), tighten))


def inlined_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Google's response schema has no `$ref`, so the definitions are inlined and
    the annotations it ignores are dropped. Recursive models are not supported
    here, and neither are they in the contracts we send."""
    defs: dict[str, Any] = schema.get("$defs", {})

    def resolve(node: Any) -> Any:
        if isinstance(node, dict):
            reference = node.get("$ref")
            if isinstance(reference, str):
                return resolve(deepcopy(defs[reference.rsplit("/", 1)[-1]]))
            return {
                key: resolve(value)
                for key, value in node.items()
                if key not in _DROPPED and key != "$defs"
            }
        if isinstance(node, list):
            return [resolve(item) for item in node]
        return node

    resolved: dict[str, Any] = resolve(deepcopy(schema))
    return resolved
