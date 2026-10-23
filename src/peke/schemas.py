"""Built-in extraction schemas and user schema loading."""
import ast
import importlib.util
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SchemaBase(BaseModel):
    model_config = ConfigDict(extra="ignore")


class Article(SchemaBase):
    title: str | None = None
    author: str | None = None
    publication_date: str | None = None
    summary: str | None = None
    content: str | None = None
    tags: list[str] | None = None


class Product(SchemaBase):
    title: str | None = None
    price: str | None = None
    currency: str | None = None
    description: str | None = None
    in_stock: bool | None = None
    rating: float | None = None
    features: list[str] | None = None


class Listing(SchemaBase):
    title: str | None = None
    items: list[dict[str, Any]] | None = None
    total_count: int | None = None
    page_number: int | None = None


_REGISTRY: dict[str, type[BaseModel]] = {"Article": Article, "Product": Product, "Listing": Listing}


def list_schemas() -> list[str]:
    return sorted(_REGISTRY)


def _validate_schema_source(path: Path) -> None:
    """Accept only declarative Pydantic schema modules before importing them.

    This is a safety guard against accidental executable schema files, not a Python
    sandbox. Only load schema files from sources the user trusts.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError, UnicodeError) as exc:
        raise ValueError(f"Could not parse schema file {path}: {exc}") from exc

    allowed_modules = {"pydantic", "typing"}
    allowed_calls = {"Field", "ConfigDict"}
    # Report attempted dynamic calls explicitly, even when they occur as a module-level
    # expression which is also rejected by the declarative-only rule below.
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = node.func.id if isinstance(node.func, ast.Name) else None
            if name not in allowed_calls:
                raise ValueError(f"Unsafe schema expression: calls to {name or 'attribute/dynamic functions'} are not allowed")
    declared_classes: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.Import):
                if any(alias.name.split(".")[0] not in allowed_modules for alias in node.names):
                    raise ValueError("Unsafe schema import: only pydantic and typing imports are allowed")
            elif node.module not in allowed_modules or node.level:
                raise ValueError(f"Unsafe schema import from {node.module!r}; use pydantic or typing only")
        elif isinstance(node, ast.ClassDef):
            if node.decorator_list or node.keywords:
                raise ValueError("Unsafe schema class: decorators and class keywords are not allowed")
            if not node.bases or any(not isinstance(base, ast.Name) or base.id not in {"BaseModel", *declared_classes} for base in node.bases):
                raise ValueError("Unsafe schema class: only BaseModel-derived schema classes are allowed")
            declared_classes.add(node.name)
            for member in node.body:
                if isinstance(member, ast.Expr) and isinstance(member.value, ast.Constant) and isinstance(member.value.value, str):
                    continue  # class docstring
                if not isinstance(member, (ast.AnnAssign, ast.Assign, ast.Pass)):
                    raise ValueError(f"Unsafe schema class member: {type(member).__name__} is not allowed")
        else:
            raise ValueError(f"Unsafe schema module statement: {type(node).__name__} is not allowed")

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = node.func.id if isinstance(node.func, ast.Name) else None
            if name not in allowed_calls:
                raise ValueError(f"Unsafe schema expression: calls to {name or 'attribute/dynamic functions'} are not allowed")
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.With, ast.AsyncWith,
                             ast.Try, ast.Raise, ast.Delete, ast.Global, ast.Nonlocal, ast.While, ast.For,
                             ast.AsyncFor, ast.If, ast.Match, ast.NamedExpr, ast.Await, ast.Yield, ast.YieldFrom)):
            raise ValueError(f"Unsafe schema construct: {type(node).__name__} is not allowed")


def get_schema(name: str) -> type[BaseModel]:
    if ":" in name:
        file_name, class_name = name.rsplit(":", 1)
        path = Path(file_name).expanduser()
        if not path.is_file():
            raise ValueError(f"Schema file does not exist: {path}")
        _validate_schema_source(path)
        spec = importlib.util.spec_from_file_location("peke_user_schema", path)
        if spec is None or spec.loader is None:
            raise ValueError(f"Could not load schema module: {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        model = getattr(module, class_name, None)
        if not isinstance(model, type) or not issubclass(model, BaseModel):
            raise ValueError(f"{class_name} in {path} must be a Pydantic BaseModel subclass")
        return model
    for key, model in _REGISTRY.items():
        if key.lower() == name.lower():
            return model
    raise ValueError(f"Unknown schema '{name}'. Available schemas: {', '.join(list_schemas())}")
