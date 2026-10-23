"""Configuration settings and environment variable management for Peke."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env file automatically if present
load_dotenv()


class ConfigError(Exception):
    """Raised when configuration values are missing or invalid."""



class Settings:
    """Settings class managing Peke configuration variables."""

    def __init__(self) -> None:
        self.model_path_str: str | None = os.getenv("MODEL_PATH")
        self.rea_server_url: str | None = os.getenv("REA_SERVER_URL")
        self.rea_command: str = os.getenv("REA_COMMAND", "rea")

        raw_timeout = os.getenv("FETCH_TIMEOUT", "30")
        try:
            self.fetch_timeout: int = int(raw_timeout)
        except ValueError:
            self.fetch_timeout = 30

        raw_temp = os.getenv("LLM_TEMPERATURE", "0.1")
        try:
            temp = float(raw_temp)
            # Ensure temperature stays strictly within 0.0 - 0.1 as per constraints
            self.llm_temperature: float = max(0.0, min(0.1, temp))
        except ValueError:
            self.llm_temperature = 0.1

    def get_model_path(self, require_exists: bool = True) -> Path:
        """Validates and returns the Path to the llama.cpp GGUF model file.

        :param require_exists: If True, asserts that the model file exists on disk.
        :return: Path object to the .gguf model file.
        :raises ConfigError: If MODEL_PATH is unset, empty, or points to a non-existent file.
        """
        if not self.model_path_str:
            raise ConfigError(
                "MODEL_PATH is not set in environment or .env file.\n"
                "Action required: Set MODEL_PATH=/path/to/your/model.gguf in your environment or .env file."
            )

        model_path = Path(self.model_path_str)
        if require_exists and not model_path.exists():
            raise ConfigError(
                f"GGUF model file not found at specified path: '{model_path}'.\n"
                "Action required: Verify that the file exists and MODEL_PATH points to a valid .gguf model."
            )

        return model_path


def get_settings() -> Settings:
    """Helper function to load settings."""
    return Settings()
