"""Environment-backed application configuration with structured provider and update settings."""
import json
import logging
import math
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def user_settings_path() -> Path:
    """Return the single canonical per-user settings path on every platform."""
    from platformdirs import user_config_dir

    return Path(user_config_dir("peke", "Peke")) / "settings.json"


def user_config_toml_path() -> Path:
    """Return optional config.toml path in user config directory."""
    from platformdirs import user_config_dir

    return Path(user_config_dir("peke", "Peke")) / "config.toml"


def save_user_settings(values: dict[str, Any], *, merge: bool = True) -> Path:
    """Persist settings atomically, optionally preserving settings owned by other pages."""
    path = user_settings_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name != "nt":
        if path.parent.is_symlink():
            raise OSError("Refusing to use a symbolic link as the settings directory")
        path.parent.chmod(0o700)
    if path.is_symlink():
        raise OSError("Refusing to follow a symbolic link for the settings file")
    if path.exists() and not path.is_file():
        raise OSError("Settings path exists but is not a regular file")
    if path.is_file() and os.name != "nt":
        path.chmod(0o600)
    existing: dict[str, Any] = {}
    if merge and path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                existing = loaded
        except (OSError, json.JSONDecodeError):
            existing = {}
    existing.update(values)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=path.parent,
            prefix=".settings-", suffix=".tmp", delete=False,
        ) as temporary:
            temporary_name = temporary.name
            temporary.write(json.dumps(existing, indent=2, ensure_ascii=False) + "\n")
        temporary_path = Path(temporary_name)
        if os.name != "nt":
            temporary_path.chmod(0o600)
            path.parent.chmod(0o700)
        os.replace(temporary_path, path)
    except OSError:
        if temporary_name:
            Path(temporary_name).unlink(missing_ok=True)
        raise
    return path


class ConfigError(Exception):
    """Invalid or incomplete application configuration."""


@dataclass(frozen=True)
class Settings:
    model_path: Path | None
    n_ctx: int = 8192
    n_gpu_layers: int = 0
    n_threads: int = 0
    max_input_chars: int = 24000
    temperature: float = 0.1
    request_delay_seconds: float = 1.0
    output_dir: Path = Path("output")
    rea_command: str | None = None
    rea_cdp_endpoint: str = "http://127.0.0.1:9222"
    fetch_timeout: float = 30.0
    max_response_bytes: int = 50 * 1024 * 1024  # 0 = unlimited
    searxng_url: str | None = None  # SearXNG instance for `peke ask`; local ports are auto-detected when unset
    subagents_max_probes: int = 0  # 0 = unlimited
    subagents_max_scripts: int = 0  # 0 = unlimited
    # MCP settings
    mcp_read_only: bool = False
    mcp_disabled_tools: tuple[str, ...] = ()
    mcp_allow_stealth: bool = True
    mcp_allow_private_hosts: bool = False
    mcp_allowed_domains: tuple[str, ...] = ()
    mcp_blocked_domains: tuple[str, ...] = ()
    mcp_robots_policy: str = "warn"
    mcp_max_inline_chars: int = 20000
    mcp_max_fetch_bytes: int = 5_242_880
    mcp_max_pages_per_call: int = 5
    mcp_http_port: int = 8765
    # Provider settings
    provider_main_kind: str = "local_builtin"
    provider_main_auto_download: bool = True
    provider_main_repo: str = "richardyoung/Qwen2.5-7B-Instruct-abliterated-GGUF"
    provider_main_file: str = "Qwen2.5-7B-Instruct-abliterated-Q4_K_M.gguf"
    provider_subagents_mode: str = "auto"
    subagents_enabled: bool = True
    subagents_max_parallel_local: int = 1
    subagents_step_timeout_seconds: float = 15.0
    subagents_max_steps: int = 3
    # Update settings
    updates_auto_check: bool = True
    updates_channel: str = "stable"
    updates_last_check_timestamp: float = 0.0

    def __post_init__(self) -> None:
        """Reject unsafe or nonsensical resource settings before work starts."""
        if self.n_ctx < 256 or self.n_ctx > 1_048_576:
            raise ConfigError("N_CTX must be between 256 and 1048576")
        if self.n_gpu_layers < 0:
            raise ConfigError("N_GPU_LAYERS must be zero or greater")
        if self.n_threads < 0:
            raise ConfigError("N_THREADS must be zero or greater")
        if self.max_input_chars < 1 or self.max_input_chars > 10_000_000:
            raise ConfigError("MAX_INPUT_CHARS must be between 1 and 10000000")
        if not math.isfinite(self.temperature) or self.temperature < 0.0:
            raise ConfigError("TEMPERATURE must be a finite, non-negative number")
        if self.temperature > 0.1:
            object.__setattr__(self, "temperature", 0.1)
        if not math.isfinite(self.request_delay_seconds) or not 0.0 <= self.request_delay_seconds <= 3600.0:
            raise ConfigError("REQUEST_DELAY_SECONDS must be between 0 and 3600")
        if not math.isfinite(self.fetch_timeout) or not 0.1 <= self.fetch_timeout <= 300.0:
            raise ConfigError("FETCH_TIMEOUT must be between 0.1 and 300 seconds")
        if self.max_response_bytes < 0 or self.subagents_max_probes < 0 or self.subagents_max_scripts < 0:
            raise ConfigError("MAX_RESPONSE_BYTES, SUBAGENTS_MAX_PROBES and SUBAGENTS_MAX_SCRIPTS must be zero (unlimited) or greater")
        if self.mcp_robots_policy not in {"off", "warn", "respect"}:
            raise ConfigError("MCP_ROBOTS_POLICY must be off, warn, or respect")
        if self.mcp_max_inline_chars < 100 or self.mcp_max_inline_chars > 1_000_000:
            raise ConfigError("MCP_MAX_INLINE_CHARS must be between 100 and 1000000")
        if self.mcp_max_fetch_bytes < 1024 or self.mcp_max_fetch_bytes > 10_000_000_000:
            raise ConfigError("MCP_MAX_FETCH_BYTES must be between 1024 and 10000000000")
        if self.mcp_max_pages_per_call < 1 or self.mcp_max_pages_per_call > 100_000:
            raise ConfigError("MCP_MAX_PAGES_PER_CALL must be between 1 and 100000")
        if self.mcp_http_port < 1024 or self.mcp_http_port > 65535:
            raise ConfigError("MCP_HTTP_PORT must be between 1024 and 65535")
        if self.provider_subagents_mode not in {"auto", "per_role"}:
            raise ConfigError("PROVIDER_SUBAGENTS_MODE must be 'auto' or 'per_role'")
        if self.updates_channel not in {"stable", "prerelease"}:
            raise ConfigError("UPDATES_CHANNEL must be 'stable' or 'prerelease'")

    def require_model(self) -> Path:
        """Return an existing model path or explain how to configure one."""
        if self.model_path is None or not self.model_path.is_file():
            if self.provider_main_kind == "local_builtin":
                from peke.models.manager import ModelManager
                mgr = ModelManager()
                active = mgr.get_active_model()
                if active and Path(active.local_path).is_file():
                    return Path(active.local_path)
            raise ConfigError(
                "A local GGUF model is required for LLM extraction. Set MODEL_PATH in your "
                ".env file or user settings to the full path of a llama.cpp-compatible .gguf file."
            )
        if self.model_path.suffix.lower() != ".gguf":
            raise ConfigError("MODEL_PATH must point to a local .gguf model file.")
        return self.model_path


def load_settings() -> Settings:
    """Load settings from environment, TOML config, and user settings JSON with legacy migration."""
    load_dotenv()
    config_values: dict[str, object] = {}

    try:
        config_path = user_settings_path()
        if config_path.is_file():
            loaded = json.loads(config_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                config_values = loaded
    except (ImportError, OSError, json.JSONDecodeError) as exc:
        logger.debug("Could not read user settings file: %s", exc)

    toml_path = user_config_toml_path()
    if toml_path.is_file():
        try:
            from peke.toml_compat import tomllib
            toml_data = tomllib.loads(toml_path.read_text(encoding="utf-8"))
            if isinstance(toml_data, dict):
                providers_main = toml_data.get("providers", {}).get("main", {})
                if "kind" in providers_main and "provider_main_kind" not in config_values:
                    config_values["provider_main_kind"] = providers_main["kind"]
                if "auto_download" in providers_main and "provider_main_auto_download" not in config_values:
                    config_values["provider_main_auto_download"] = providers_main["auto_download"]
                if "repo" in providers_main and "provider_main_repo" not in config_values:
                    config_values["provider_main_repo"] = providers_main["repo"]
                if "file" in providers_main and "provider_main_file" not in config_values:
                    config_values["provider_main_file"] = providers_main["file"]

                subagents_cfg = toml_data.get("subagents", {})
                if "enabled" in subagents_cfg and "subagents_enabled" not in config_values:
                    config_values["subagents_enabled"] = subagents_cfg["enabled"]
                if "step_timeout_seconds" in subagents_cfg and "subagents_step_timeout_seconds" not in config_values:
                    config_values["subagents_step_timeout_seconds"] = subagents_cfg["step_timeout_seconds"]

                updates_cfg = toml_data.get("updates", {})
                if "auto_check" in updates_cfg and "updates_auto_check" not in config_values:
                    config_values["updates_auto_check"] = updates_cfg["auto_check"]
                if "channel" in updates_cfg and "updates_channel" not in config_values:
                    config_values["updates_channel"] = updates_cfg["channel"]
        except Exception as exc:
            logger.debug("Could not read config.toml: %s", exc)

    def value(key: str, default: object) -> str:
        env_val = os.getenv(key)
        if env_val is not None:
            return env_val
        if key in config_values:
            return str(config_values[key])
        if key.lower() in config_values:
            return str(config_values[key.lower()])
        return str(default)

    def integer(key: str, default: int) -> int:
        try:
            return int(value(key, default))
        except ValueError as exc:
            raise ConfigError(f"{key} must be an integer") from exc

    def number(key: str, default: float) -> float:
        try:
            return float(value(key, default))
        except ValueError as exc:
            raise ConfigError(f"{key} must be a number") from exc

    def boolean(key: str, default: bool) -> bool:
        raw = value(key, default)
        if isinstance(raw, bool):
            return raw
        return str(raw).lower() in {"1", "true", "yes", "on"}

    def string_list(key: str, default: tuple[str, ...]) -> tuple[str, ...]:
        raw = config_values.get(key)
        if raw is None:
            raw = os.getenv(key)
        if raw is None:
            return default
        if isinstance(raw, (list, tuple)):
            return tuple(str(x).strip() for x in raw if str(x).strip())
        if isinstance(raw, str):
            return tuple(x.strip() for x in raw.split(",") if x.strip())
        return default

    model = value("MODEL_PATH", "").strip()
    temperature = number("TEMPERATURE", 0.1)
    if not math.isfinite(temperature):
        raise ConfigError("TEMPERATURE must be a finite number")
    temperature = max(0.0, min(0.1, temperature))

    if "MODEL_PATH" in config_values and "provider_main_kind" not in config_values:
        logger.info("Migrated legacy MODEL_PATH setting into provider_main configuration.")

    return Settings(
        model_path=Path(model).expanduser() if model else None,
        n_ctx=integer("N_CTX", 8192),
        n_gpu_layers=integer("N_GPU_LAYERS", 0),
        n_threads=integer("N_THREADS", 0),
        max_input_chars=integer("MAX_INPUT_CHARS", 24000),
        temperature=temperature,
        request_delay_seconds=number("REQUEST_DELAY_SECONDS", 1.0),
        output_dir=Path(value("OUTPUT_DIR", "output")),
        rea_command=value("REA_COMMAND", "").strip() or None,
        rea_cdp_endpoint=value("REA_CDP_ENDPOINT", "http://127.0.0.1:9222").strip(),
        fetch_timeout=number("FETCH_TIMEOUT", 30.0),
        max_response_bytes=integer("MAX_RESPONSE_BYTES", 50 * 1024 * 1024),
        searxng_url=value("SEARXNG_URL", "").strip() or None,
        subagents_max_probes=integer("SUBAGENTS_MAX_PROBES", 0),
        subagents_max_scripts=integer("SUBAGENTS_MAX_SCRIPTS", 0),
        mcp_read_only=boolean("MCP_READ_ONLY", False),
        mcp_disabled_tools=string_list("MCP_DISABLED_TOOLS", ()),
        mcp_allow_stealth=boolean("MCP_ALLOW_STEALTH", True),
        mcp_allow_private_hosts=boolean("MCP_ALLOW_PRIVATE_HOSTS", False),
        mcp_allowed_domains=string_list("MCP_ALLOWED_DOMAINS", ()),
        mcp_blocked_domains=string_list("MCP_BLOCKED_DOMAINS", ()),
        mcp_robots_policy=value("MCP_ROBOTS_POLICY", "warn").strip().lower(),
        mcp_max_inline_chars=integer("MCP_MAX_INLINE_CHARS", 20000),
        mcp_max_fetch_bytes=integer("MCP_MAX_FETCH_BYTES", 5_242_880),
        mcp_max_pages_per_call=integer("MCP_MAX_PAGES_PER_CALL", 5),
        mcp_http_port=integer("MCP_HTTP_PORT", 8765),
        provider_main_kind=value("PROVIDER_MAIN_KIND", "local_builtin").strip(),
        provider_main_auto_download=boolean("PROVIDER_MAIN_AUTO_DOWNLOAD", True),
        provider_main_repo=value("PROVIDER_MAIN_REPO", "richardyoung/Qwen2.5-7B-Instruct-abliterated-GGUF").strip(),
        provider_main_file=value("PROVIDER_MAIN_FILE", "Qwen2.5-7B-Instruct-abliterated-Q4_K_M.gguf").strip(),
        provider_subagents_mode=value("PROVIDER_SUBAGENTS_MODE", "auto").strip().lower(),
        subagents_enabled=boolean("SUBAGENTS_ENABLED", True),
        subagents_max_parallel_local=integer("SUBAGENTS_MAX_PARALLEL_LOCAL", 1),
        subagents_step_timeout_seconds=number("SUBAGENTS_STEP_TIMEOUT_SECONDS", 15.0),
        subagents_max_steps=integer("SUBAGENTS_MAX_STEPS", 3),
        updates_auto_check=boolean("UPDATES_AUTO_CHECK", True),
        updates_channel=value("UPDATES_CHANNEL", "stable").strip().lower(),
        updates_last_check_timestamp=number("UPDATES_LAST_CHECK_TIMESTAMP", 0.0),
    )


get_settings = load_settings
