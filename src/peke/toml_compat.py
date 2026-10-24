"""TOML reader compatibility across supported Python versions."""
try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover - exercised on Python 3.10
    import tomli as tomllib

__all__ = ["tomllib"]
