"""Peke MCP Resources (peke://runs, peke://profiles/{name}, peke://schemas/{name})."""

import json

from mcp.server import MCPServer

from peke.mcp.runs import get_run_part, list_runs
from peke.mcp.security import redact_secrets
from peke.profile import load_profile
from peke.schemas import get_schema


def register_resources(server: MCPServer) -> None:
    """Register Peke resources on the MCPServer instance."""

    @server.resource("peke://runs")
    def get_runs_index() -> str:
        """Resource listing stored run metadata."""
        runs = list_runs(limit=50)
        return json.dumps(runs, indent=2, ensure_ascii=False)

    @server.resource("peke://runs/{run_id}/{part}")
    def get_run_artifact(run_id: str, part: str) -> str:
        """Resource fetching specific run artifact (meta, content, records, endpoints, events)."""
        data, truncated, next_off = get_run_part(run_id, part=part, offset=0, limit=20000)
        res = {
            "run_id": run_id,
            "part": part,
            "data": data,
            "truncated": truncated,
            "next_offset": next_off,
        }
        return json.dumps(res, indent=2, ensure_ascii=False)

    @server.resource("peke://profiles/{name}")
    def get_profile_resource(name: str) -> str:
        """Resource providing profile configuration with secrets redacted."""
        profile = load_profile(name)
        pdict = profile.model_dump(mode="json")
        redacted = redact_secrets(pdict)
        return json.dumps(redacted, indent=2, ensure_ascii=False)

    @server.resource("peke://schemas/{name}")
    def get_schema_resource(name: str) -> str:
        """Resource providing JSON Schema structure for a named schema."""
        schema_cls = get_schema(name)
        jschema = schema_cls.model_json_schema()
        return json.dumps(jschema, indent=2, ensure_ascii=False)
