"""Lifecycle manager for the standalone llama.cpp OpenAI-compatible server."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen


class LlamaServerError(RuntimeError):
    """A server executable, startup, or API operation failed."""


class LlamaServer:
    def __init__(self, executable: str | Path | None = None, model: str | Path | None = None,
                 host: str = "127.0.0.1", port: int = 8081, context: int = 4096) -> None:
        self.executable = self._resolve_executable(executable)
        self.model = Path(model or os.environ.get("MODEL_PATH", "")).expanduser() if (model or os.environ.get("MODEL_PATH")) else None
        self.host, self.port, self.context = host, int(port), int(context)
        self.process: subprocess.Popen | None = None
        self._log_handle = None
        self.base_url = f"http://{self.host}:{self.port}"

    @staticmethod
    def _resolve_executable(executable: str | Path | None) -> Path | None:
        """Find an explicitly configured, PATH, or app-managed runtime executable."""
        configured = str(executable or os.environ.get("LLAMA_SERVER_PATH", "")).strip()
        if configured:
            candidate = Path(configured).expanduser()
            found = str(candidate) if candidate.is_file() else shutil.which(configured)
            return Path(found).resolve() if found else None

        names = ["llama-server.exe", "llama-server"] if os.name == "nt" else ["llama-server"]
        on_path = shutil.which("llama-server")
        if on_path:
            return Path(on_path).resolve()

        candidates: list[Path] = []
        try:
            from platformdirs import user_data_path
            root = Path(user_data_path("Peke", appauthor=False))
            candidates.extend(root / "runtime" / name for name in names)
            candidates.extend(root / "runtimes" / "llama.cpp" / name for name in names)
        except ImportError:
            pass
        candidates.extend(Path(sys.prefix) / "bin" / name for name in names)
        candidates.extend(Path(__file__).resolve().parent / "runtime" / name for name in names)
        for candidate in candidates:
            if candidate.is_file():
                return candidate.resolve()
        return None

    def version(self) -> str:
        if not self.executable or not self.executable.is_file():
            raise LlamaServerError("llama-server executable was not found; set LLAMA_SERVER_PATH.")
        try:
            result = subprocess.run([str(self.executable), "--version"], capture_output=True, text=True, timeout=5)
        except (OSError, subprocess.SubprocessError) as exc:
            raise LlamaServerError(f"Could not inspect llama-server: {exc}") from exc
        if result.returncode:
            raise LlamaServerError((result.stderr or result.stdout or "llama-server --version failed").strip())
        return (result.stdout or result.stderr).strip()

    def start(self, timeout: float = 90.0) -> None:
        if self.process and self.process.poll() is None:
            return
        if not self.executable or not self.executable.is_file():
            raise LlamaServerError("llama-server executable not found; set LLAMA_SERVER_PATH or put it on PATH.")
        if not self.model or not self.model.is_file() or self.model.suffix.lower() != ".gguf":
            raise LlamaServerError("Set MODEL_PATH to an existing GGUF model before starting llama-server.")
        if not 1 <= self.port <= 65535 or not 256 <= self.context <= 1_048_576:
            raise LlamaServerError("Invalid server port or context length.")
        if self.host not in {"127.0.0.1", "localhost", "::1"}:
            raise LlamaServerError("Refusing to bind llama-server beyond loopback without an explicit future security review.")
        args = [str(self.executable), "--model", str(self.model.resolve()), "--host", self.host,
                "--port", str(self.port), "--ctx-size", str(self.context)]
        try:
            log_dir = Path.home() / ".peke" / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            self._log_handle = (log_dir / "llama-server.log").open("ab")
            self.process = subprocess.Popen(args, stdout=self._log_handle, stderr=subprocess.STDOUT,
                                            stdin=subprocess.DEVNULL, shell=False)
        except OSError as exc:
            raise LlamaServerError(f"Failed to launch llama-server: {exc}") from exc
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise LlamaServerError(f"llama-server exited during startup (code {self.process.returncode}).")
            try:
                with urlopen(f"{self.base_url}/health", timeout=1) as response:
                    if response.status == 200:
                        return
            except (OSError, URLError, TimeoutError):
                time.sleep(0.25)
        return_code = self.process.poll() if self.process else None
        self.stop()
        if return_code is not None:
            raise LlamaServerError(
                f"llama-server exited during startup (code {return_code}); inspect ~/.peke/logs/llama-server.log."
            )
        raise LlamaServerError(
            f"llama-server did not become healthy within {timeout:g} seconds; "
            "check port conflicts and ~/.peke/logs/llama-server.log."
        )

    def stop(self) -> None:
        process, self.process = self.process, None
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
        if self._log_handle:
            self._log_handle.close()
            self._log_handle = None

    def complete(self, system: str, user: str, schema: dict, temperature: float = 0.1,
                 max_tokens: int = 4096, timeout: float = 120.0) -> dict:
        import json
        payload = json.dumps({"model": "local-model", "messages": [
            {"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": temperature, "max_tokens": max_tokens,
            "response_format": {"type": "json_object", "schema": schema}}).encode()
        request = Request(f"{self.base_url}/v1/chat/completions", data=payload,
                          headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urlopen(request, timeout=timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (OSError, URLError, TimeoutError, ValueError) as exc:
            raise LlamaServerError(f"llama-server inference request failed: {exc}") from exc
        if not isinstance(data, dict) or not isinstance(data.get("choices"), list) or not data["choices"]:
            raise LlamaServerError("llama-server returned an unexpected completion response.")
        return data
