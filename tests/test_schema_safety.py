from pathlib import Path

import pytest

from peke.schemas import get_schema


def test_rejects_unsafe_schema_import(tmp_path: Path):
    path = tmp_path / "bad.py"
    path.write_text("import os\nfrom pydantic import BaseModel\nclass Bad(BaseModel):\n x: str\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Unsafe schema import"):
        get_schema(f"{path}:Bad")


def test_rejects_dynamic_execution(tmp_path: Path):
    path = tmp_path / "bad.py"
    path.write_text("from pydantic import BaseModel\nexec('print(1)')\nclass Bad(BaseModel):\n x: str\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Unsafe schema expression"):
        get_schema(f"{path}:Bad")


def test_rejects_schema_decorators(tmp_path: Path):
    path = tmp_path / "decorated.py"
    path.write_text(
        "from pydantic import BaseModel\n@staticmethod\nclass Bad(BaseModel):\n x: str\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="decorators"):
        get_schema(f"{path}:Bad")


def test_rejects_top_level_executable_statements(tmp_path: Path):
    path = tmp_path / "top_level.py"
    path.write_text(
        "from pydantic import BaseModel\nprint('not allowed')\nclass Bad(BaseModel):\n x: str\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Unsafe schema expression"):
        get_schema(f"{path}:Bad")


def test_rejects_class_metaclass_keyword(tmp_path: Path):
    path = tmp_path / "metaclass.py"
    path.write_text(
        "from pydantic import BaseModel\nclass Bad(BaseModel, metaclass=type):\n x: str\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="class keywords"):
        get_schema(f"{path}:Bad")
