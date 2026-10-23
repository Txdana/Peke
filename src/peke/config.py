"""Environment-backed application configuration."""
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


def save_user_settings(values: dict[str, Any], *, merge: bool = True) -> Path:
    """Persist settings atomically, optionally preserving settings owned by other pages."""
    path = user_settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, Any] = {}
    if merge and path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                existing = loaded
        except (OSError, json.JSONDecodeError):
            # A corrupt settings file is replaced with the explicitly saved values.
            existing = {}
    existing.update(values)
    temporary_name: str | None = None
    try:
        # Use a unique file in the same directory to avoid following a pre-created .tmp
        # symlink and preserve atomic replacement on the same filesystem.
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

    def require_model(self) -> Path:
        """Return an existing model path or explain how to configure one."""
        if self.model_path is None or not self.model_path.is_file():
            raise ConfigError(
                "A local GGUF model is required for LLM extraction. Set MODEL_PATH in your "
                ".env file or user settings to the full path of a llama.cpp-compatible .gguf file."
            )
        if self.model_path.suffix.lower() != ".gguf":
            raise ConfigError("MODEL_PATH must point to a local .gguf model file.")
        return self.model_path


def load_settings() -> Settings:
    """Load settings from the environment, reading .env if present."""
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

    def value(key: str, default: object) -> str:
        return os.getenv(key, str(config_values.get(key, default)))

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

    model = value("MODEL_PATH", "").strip()
    temperature = number("TEMPERATURE", 0.1)
    if not math.isfinite(temperature):
        raise ConfigError("TEMPERATURE must be a finite number")
    temperature = max(0.0, min(0.1, temperature))
    return Settings(
        model_path=Path(model).expanduser() if model else None,
        n_ctx=integer("N_CTX", 8192), n_gpu_layers=integer("N_GPU_LAYERS", 0),
        n_threads=integer("N_THREADS", 0), max_input_chars=integer("MAX_INPUT_CHARS", 24000),
        temperature=temperature,
        request_delay_seconds=number("REQUEST_DELAY_SECONDS", 1.0),
        output_dir=Path(value("OUTPUT_DIR", "output")),
        rea_command=value("REA_COMMAND", "").strip() or None,
        rea_cdp_endpoint=value("REA_CDP_ENDPOINT", "http://127.0.0.1:9222").strip(),
        fetch_timeout=number("FETCH_TIMEOUT", 30.0),
    )


# Compatibility alias for older callers.
get_settings = load_settings
