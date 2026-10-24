"""Schema agent: infer what an endpoint returns, then (optionally) ask the AI to interpret it."""
import json
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

_PAGINATION_KEYS = {"next", "next_page", "nextpage", "cursor", "next_cursor", "page", "pages", "per_page",
                    "page_size", "limit", "offset", "total", "total_count", "count", "has_more", "hasmore"}
_BUILTIN_SCHEMAS = {"Article", "Product", "Listing"}

SYSTEM_PROMPT = (
    "You analyse the structure of an authorized web API response. Using ONLY the field names and "
    "types provided, choose the best built-in schema (Article, Product or Listing) and describe what "
    "the endpoint returns. Never invent fields. Respond with JSON only."
)
JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "schema_name": {"type": "string", "enum": sorted(_BUILTIN_SCHEMAS)},
        "description": {"type": "string"},
        "field_mapping": {"type": "object", "additionalProperties": {"type": "string"}},
    },
    "required": ["schema_name", "description"],
}


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, list):
        return "list"
    return "object"


def infer_shape(value: Any, depth: int = 3) -> Any:
    """Return a compact structural description (types only, no values)."""
    if isinstance(value, dict):
        if depth <= 0:
            return "object"
        return {str(k): infer_shape(v, depth - 1) for k, v in list(value.items())[:40]}
    if isinstance(value, list):
        if not value:
            return ["empty"]
        return [infer_shape(value[0], depth - 1) if depth > 0 else _type_name(value[0]), f"len={len(value)}"]
    return _type_name(value)


def find_items(data: Any, max_depth: int = 4) -> tuple[str | None, list[dict[str, Any]]]:
    """Locate the largest list of objects; return a dotted ``item_path`` (matches Profile.item_path)."""
    best: tuple[str | None, list[dict[str, Any]]] = (None, [])
    stack: list[tuple[str, Any, int]] = [("", data, 0)]
    while stack:
        path, node, depth = stack.pop()
        if isinstance(node, list) and node and all(isinstance(x, dict) for x in node[:5]):
            if len(node) > len(best[1]):
                best = (path or None, node)
        if depth < max_depth and isinstance(node, dict):
            for key, child in node.items():
                stack.append((f"{path}.{key}" if path else str(key), child, depth + 1))
    return best


def field_types(items: list[dict[str, Any]], sample: int = 50) -> dict[str, str]:
    types: dict[str, set[str]] = {}
    for item in items[:sample]:
        for key, val in item.items():
            types.setdefault(str(key), set()).add(_type_name(val))
    return {k: "|".join(sorted(v)) for k, v in types.items()}


def pagination_hints(data: Any) -> list[str]:
    if not isinstance(data, dict):
        return []
    found = [k for k in data if str(k).lower() in _PAGINATION_KEYS]
    for child in data.values():
        if isinstance(child, dict):
            found += [f"{k}" for k in child if str(k).lower() in _PAGINATION_KEYS]
    return sorted(set(found))


@dataclass
class SchemaAgentResult:
    findings: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


class SchemaAgent:
    def analyze(self, payloads: dict[str, Any], provider: Any | None = None) -> SchemaAgentResult:
        result = SchemaAgentResult()
        for url, data in payloads.items():
            item_path, items = find_items(data)
            finding: dict[str, Any] = {
                "url": url,
                "item_path": item_path,
                "item_count": len(items),
                "fields": field_types(items) if items else {},
                "pagination": pagination_hints(data),
                "schema_name": "Listing" if items else "Article",
                "ai": None,
            }
            if provider is not None and finding["fields"]:
                finding["ai"] = self._ask_ai(provider, finding)
                if finding["ai"] and finding["ai"].get("schema_name") in _BUILTIN_SCHEMAS:
                    finding["schema_name"] = finding["ai"]["schema_name"]
            result.findings.append(finding)
        result.notes.append(f"Inferred structure for {len(result.findings)} JSON endpoint(s).")
        return result

    @staticmethod
    def _ask_ai(provider: Any, finding: dict[str, Any]) -> dict[str, Any] | None:
        try:
            user = json.dumps({"fields": finding["fields"], "item_path": finding["item_path"],
                               "pagination": finding["pagination"]})
            out = provider.complete_json(SYSTEM_PROMPT, user, JSON_SCHEMA, temperature=0.1, max_tokens=512)
            parsed = out.parsed if isinstance(out.parsed, dict) else json.loads(out.raw_text)
            return parsed if isinstance(parsed, dict) else None
        except Exception as exc:  # AI is an enhancement; never fail discovery because of it
            logger.warning("Schema agent AI pass skipped: %s", type(exc).__name__)
            return None
