# Third-party notices

Peke depends on third-party projects. Their licenses apply to those components and are not replaced by Peke's MIT license. Consult the installed distribution and upstream project for the exact license text and version shipped with your environment.

- **Scrapling** — fetch and parsing library; consult its upstream repository and package license.
- **llama-cpp-python / llama.cpp** — Python bindings and native inference runtime; consult each upstream license and the model's separate license.
- **PySide6 / Qt** — optional GUI toolkit; review Qt licensing terms for the selected distribution and use.
- **Pydantic** — data validation.
- **Typer** and **Rich** — CLI and terminal rendering.
- **PyYAML**, **python-dotenv**, **platformdirs**, **pytest**, **pytest-qt**, and **Ruff** — configuration, testing, and development utilities.

Font binaries are not currently bundled in this source archive. When DM Sans, Fraunces, or IBM Plex Mono are added, include each font's upstream OFL license in `src/peke/gui/assets/fonts/LICENSES/` and update this notice. The GUI uses system-font fallbacks in the meantime.
