# Third-Party Notices and License Attributions

Peke is distributed under the Apache License 2.0. Third-party dependencies and components distributed alongside or utilized by Peke retain their own respective software licenses.

---

## Direct Dependencies

### 1. PySide6
- **License:** GNU Lesser General Public License (LGPL) v3 / Commercial
- **Repository:** https://code.qt.io/cgit/pyside/pyside-setup.git/
- **LGPL Compliance & Relinking Obligations:**
  - PySide6 provides Python bindings for the Qt library under LGPLv3.
  - Peke dynamically imports PySide6 as an external Python package library. Peke does not modify or statically link PySide6.
  - Users and downstream distributors have the right to modify or replace the PySide6 package in their virtual environment or installation without modifying Peke's core codebase.

### 2. Scrapling
- **License:** BSD-3-Clause / MIT
- **Repository:** https://github.com/D4V1303/Scrapling

### 3. llama-cpp-python
- **License:** MIT
- **Repository:** https://github.com/abetlen/llama-cpp-python

### 4. Model Context Protocol (MCP) Python SDK
- **License:** MIT
- **Repository:** https://github.com/modelcontextprotocol/python-sdk

### 5. Hugging Face Hub (`huggingface_hub`)
- **License:** Apache License 2.0
- **Repository:** https://github.com/huggingface/huggingface_hub

### 6. Keyring (`keyring`)
- **License:** MIT
- **Repository:** https://github.com/jaraco/keyring

### 7. Pydantic
- **License:** MIT
- **Repository:** https://github.com/pydantic/pydantic

### 8. Typer & Rich
- **License:** MIT
- **Repositories:** https://github.com/fastapi/typer, https://github.com/Textualize/rich

### 9. httpx
- **License:** BSD-3-Clause
- **Repository:** https://github.com/encode/httpx

### 10. Platformdirs & Filelock
- **License:** MIT
- **Repositories:** https://github.com/platformdirs/platformdirs, https://github.com/tox-dev/filelock

---

## External & Optional Tooling

- **REA (Reverse Engineering Assistant):** External tool governed by its own project license.
