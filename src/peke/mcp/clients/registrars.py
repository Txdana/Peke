"""Registrars for AI agent clients (Claude Code, Claude Desktop, Codex, Cursor, Gemini, VSCode, Windsurf)."""

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from peke.mcp.clients.base import ClientRegistrar, get_peke_launcher


def _run_quiet(cmd: list[str], timeout: float = 8.0) -> "subprocess.CompletedProcess[str] | None":
    """Run a CLI without flashing a console window and never block for long."""
    exe = shutil.which(cmd[0])
    if exe is None:
        return None
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    try:
        return subprocess.run([exe, *cmd[1:]], capture_output=True, text=True, check=False,
                              timeout=timeout, stdin=subprocess.DEVNULL, creationflags=flags)
    except (OSError, subprocess.SubprocessError):
        return None


def create_backup(path: Path) -> Path | None:
    """Create timestamped backup of config file before modifying."""
    if not path.is_file():
        return None
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_path = path.with_name(f"{path.name}.peke-backup-{ts}")
    try:
        shutil.copy2(path, backup_path)
        return backup_path
    except OSError:
        return None


def get_mcp_entry(transport: str = "stdio", port: int = 8765, is_win: bool = (sys.platform == "win32")) -> dict[str, Any]:
    """Build standard JSON object for Peke MCP server registration."""
    launcher = get_peke_launcher()
    if is_win:
        cmd = "cmd.exe"
        args = ["/d", "/c", launcher, "mcp", "serve"]
    else:
        cmd = launcher
        args = ["mcp", "serve"]

    if transport == "http":
        args.extend(["--http", "--port", str(port)])

    entry: dict[str, Any] = {
        "command": cmd,
        "args": args,
    }
    peke_home = os.getenv("PEKE_HOME")
    if peke_home:
        entry["env"] = {"PEKE_HOME": peke_home}
    return entry


class ClaudeCodeRegistrar(ClientRegistrar):
    client_id = "claude_code"
    display_name = "Claude Code"

    def detect_installed(self) -> bool:
        return shutil.which("claude") is not None or (Path.home() / ".claude.json").exists()

    def is_registered(self) -> bool:
        # Read the config file instead of running `claude mcp list`, which health-checks
        # every configured server (slow, and opens console windows from a GUI app).
        try:
            data = json.loads((Path.home() / ".claude.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        servers = data.get("mcpServers", {}) if isinstance(data, dict) else {}
        return isinstance(servers, dict) and "peke" in servers

    def plan_install(self, scope: str = "user", transport: str = "stdio", port: int = 8765) -> tuple[dict[str, Any] | None, str]:
        entry = get_mcp_entry(transport, port)
        cmd_str = f"claude mcp add --scope {scope} peke -- {entry['command']} " + " ".join(entry["args"])
        diff_text = f"+ Register Peke with Claude Code via CLI:\n  {cmd_str}"
        return entry, diff_text

    def install(self, scope: str = "user", transport: str = "stdio", port: int = 8765, dry_run: bool = False) -> bool:
        entry, diff_text = self.plan_install(scope, transport, port)
        if dry_run:
            return True

        if shutil.which("claude"):
            cmd = ["claude", "mcp", "add", "--scope", scope, "peke", "--", entry["command"]] + entry["args"]
            res = _run_quiet(cmd, timeout=30.0)
            return res is not None and res.returncode == 0
        return True


class ClaudeDesktopRegistrar(ClientRegistrar):
    client_id = "claude_desktop"
    display_name = "Claude Desktop"

    def get_config_path(self) -> Path | None:
        home = Path.home()
        if sys.platform == "darwin":
            return home / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
        elif sys.platform == "win32":
            appdata = os.getenv("APPDATA")
            if appdata:
                return Path(appdata) / "Claude" / "claude_desktop_config.json"
            return home / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json"
        else:
            return home / ".config" / "Claude" / "claude_desktop_config.json"

    def is_registered(self) -> bool:
        p = self.get_config_path()
        if not p or not p.is_file():
            return False
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            return "peke" in data.get("mcpServers", {})
        except Exception:
            return False

    def plan_install(self, scope: str = "user", transport: str = "stdio", port: int = 8765) -> tuple[dict[str, Any] | None, str]:
        p = self.get_config_path()
        if not p:
            return None, ""
        data: dict[str, Any] = {"mcpServers": {}}
        if p.is_file():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                pass
        servers = data.setdefault("mcpServers", {})
        entry = get_mcp_entry(transport, port)
        servers["peke"] = entry

        diff_text = f"File: {p}\n+ Add Peke to mcpServers in claude_desktop_config.json"
        return data, diff_text

    def install(self, scope: str = "user", transport: str = "stdio", port: int = 8765, dry_run: bool = False) -> bool:
        p = self.get_config_path()
        if not p:
            return False
        new_data, _ = self.plan_install(scope, transport, port)
        if not new_data:
            return False
        if dry_run:
            return True

        p.parent.mkdir(parents=True, exist_ok=True)
        create_backup(p)
        p.write_text(json.dumps(new_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return True

    def uninstall(self, dry_run: bool = False) -> bool:
        p = self.get_config_path()
        if not p or not p.is_file():
            return True
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if "peke" in data.get("mcpServers", {}):
                del data["mcpServers"]["peke"]
                if not dry_run:
                    create_backup(p)
                    p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            return True
        except Exception:
            return False


class JsonMcpRegistrar(ClientRegistrar):
    """Generic JSON config file registrar for Cursor, Gemini, VSCode, Windsurf."""

    def __init__(self, client_id: str, display_name: str, config_relative_path: str) -> None:
        self.client_id = client_id
        self.display_name = display_name
        self.config_relative_path = config_relative_path

    def get_config_path(self) -> Path | None:
        return Path.home() / self.config_relative_path

    def is_registered(self) -> bool:
        p = self.get_config_path()
        if not p or not p.is_file():
            return False
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            return "peke" in data.get("mcpServers", {})
        except Exception:
            return False

    def plan_install(self, scope: str = "user", transport: str = "stdio", port: int = 8765) -> tuple[dict[str, Any] | None, str]:
        p = self.get_config_path()
        if not p:
            return None, ""
        data: dict[str, Any] = {"mcpServers": {}}
        if p.is_file():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                pass
        servers = data.setdefault("mcpServers", {})
        entry = get_mcp_entry(transport, port)
        servers["peke"] = entry

        diff_text = f"File: {p}\n+ Add Peke server entry to mcpServers"
        return data, diff_text

    def install(self, scope: str = "user", transport: str = "stdio", port: int = 8765, dry_run: bool = False) -> bool:
        p = self.get_config_path()
        if not p:
            return False
        new_data, _ = self.plan_install(scope, transport, port)
        if not new_data:
            return False
        if dry_run:
            return True

        p.parent.mkdir(parents=True, exist_ok=True)
        create_backup(p)
        p.write_text(json.dumps(new_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return True

    def uninstall(self, dry_run: bool = False) -> bool:
        p = self.get_config_path()
        if not p or not p.is_file():
            return True
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if "peke" in data.get("mcpServers", {}):
                del data["mcpServers"]["peke"]
                if not dry_run:
                    create_backup(p)
                    p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            return True
        except Exception:
            return False


class CodexRegistrar(ClientRegistrar):
    client_id = "codex"
    display_name = "Codex"

    def get_config_path(self) -> Path | None:
        return Path.home() / ".codex" / "config.toml"

    def is_registered(self) -> bool:
        p = self.get_config_path()
        if not p or not p.is_file():
            return False
        return "[mcp_servers.peke]" in p.read_text(encoding="utf-8")

    def plan_install(self, scope: str = "user", transport: str = "stdio", port: int = 8765) -> tuple[dict[str, Any] | None, str]:
        p = self.get_config_path()
        entry = get_mcp_entry(transport, port)
        diff_text = f"File: {p}\n+ Append [mcp_servers.peke] block"
        return entry, diff_text

    def install(self, scope: str = "user", transport: str = "stdio", port: int = 8765, dry_run: bool = False) -> bool:
        p = self.get_config_path()
        if not p:
            return False
        entry = get_mcp_entry(transport, port)
        if dry_run:
            return True

        p.parent.mkdir(parents=True, exist_ok=True)
        content = p.read_text(encoding="utf-8") if p.is_file() else ""
        if "[mcp_servers.peke]" not in content:
            create_backup(p)
            block = (
                "\n[mcp_servers.peke]\n"
                f'command = "{entry["command"]}"\n'
                f'args = {json.dumps(entry["args"])}\n'
            )
            p.write_text(content + block, encoding="utf-8")
        return True

    def uninstall(self, dry_run: bool = False) -> bool:
        p = self.get_config_path()
        if not p or not p.is_file():
            return True
        content = p.read_text(encoding="utf-8")
        if "[mcp_servers.peke]" in content:
            # Basic block strip
            lines = content.splitlines()
            new_lines = []
            skipping = False
            for line in lines:
                if line.strip() == "[mcp_servers.peke]":
                    skipping = True
                    continue
                if skipping and line.startswith("["):
                    skipping = False
                if not skipping:
                    new_lines.append(line)
            if not dry_run:
                create_backup(p)
                p.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        return True


def get_all_registrars() -> list[ClientRegistrar]:
    """Return instances of all supported AI client registrars."""
    return [
        ClaudeCodeRegistrar(),
        ClaudeDesktopRegistrar(),
        CodexRegistrar(),
        JsonMcpRegistrar("cursor", "Cursor", ".cursor/mcp.json"),
        JsonMcpRegistrar("gemini_cli", "Gemini CLI", ".gemini/settings.json"),
        JsonMcpRegistrar("vscode", "VS Code", ".vscode/mcp.json"),
        JsonMcpRegistrar("windsurf", "Windsurf", ".codeium/windsurf/mcp_config.json"),
    ]
