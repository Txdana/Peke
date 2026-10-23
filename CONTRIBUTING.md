# Contributing to Peke

Thank you for your interest in contributing to Peke!

## Development Setup

1. Clone the repository:
```bash
git clone https://github.com/morluto/peke.git
cd peke
```

2. Create a virtual environment and install Peke in editable mode with development dependencies:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -e ".[gui,dev]"
```

3. Run tests and lint checks:
```bash
pytest -v
ruff check .
```

## Pull Request Guidelines
- Ensure code follows Python 3.10+ conventions, explicit type hints, and `src/` layout.
- Write tests for any new features or bug fixes.
- Run `ruff check .` and `pytest -v` before submitting your PR.
