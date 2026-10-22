"""Target profile models and YAML loader for Peke."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class ProfileError(Exception):
    """Raised when profile parsing or loading fails."""



class TargetProfile(BaseModel):
    """Model representing a target scraping/extraction profile."""

    name: str | None = Field(default=None, description="Human-readable name of target")
    url: str = Field(..., description="Target URL to fetch")
    fetcher: str = Field(
        default="Fetcher",
        description="Scrapling fetcher class to use ('Fetcher' or 'StealthyFetcher')",
    )
    headers: dict[str, str] = Field(
        default_factory=dict, description="Custom HTTP headers to send with requests"
    )
    params: dict[str, Any] = Field(
        default_factory=dict, description="Custom query parameters or payload parameters"
    )
    endpoint_hints: list[dict[str, Any]] = Field(
        default_factory=list, description="Discovered endpoints or API hints"
    )
    schema_name: str = Field(
        default="Article",
        description="Name of registered Pydantic schema model to format payload into",
    )


def load_profile(path_or_dict: str | Path | dict[str, Any]) -> TargetProfile:
    """Load a TargetProfile from a YAML file path or dictionary.

    :param path_or_dict: Path to YAML file or dictionary containing profile fields.
    :return: TargetProfile instance.
    :raises ProfileError: If file is not found, invalid YAML, or fails validation.
    """
    if isinstance(path_or_dict, (str, Path)):
        file_path = Path(path_or_dict)
        if not file_path.exists():
            raise ProfileError(f"Target profile file not found at: '{file_path}'")
        try:
            with open(file_path, encoding="utf-8") as f:
                content = yaml.safe_load(f)
        except Exception as e:
            raise ProfileError(f"Failed to read or parse YAML file '{file_path}': {e}")
    elif isinstance(path_or_dict, dict):
        content = path_or_dict
    else:
        raise ProfileError(f"Invalid argument type for profile loader: {type(path_or_dict)}")

    if not isinstance(content, dict):
        raise ProfileError("Profile content must be a dictionary or valid YAML object.")

    try:
        return TargetProfile(**content)
    except Exception as e:
        raise ProfileError(f"Invalid profile configuration: {e}")
