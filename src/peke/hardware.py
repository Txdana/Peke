"""Best-effort, offline-capable host hardware profiling for local inference."""
from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class GPUInfo:
    name: str
    vendor: str = "unknown"
    vram_bytes: int | None = None
    kind: str = "unknown"
    source: str = "unknown"


@dataclass(frozen=True)
class HardwareProfile:
    operating_system: str
    os_version: str
    architecture: str
    cpu: str
    logical_cores: int | None
    ram_total_bytes: int | None
    ram_available_bytes: int | None
    gpus: list[GPUInfo] = field(default_factory=list)
    confidence: str = "partial"
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _command(args: list[str], timeout: float = 2.5) -> str | None:
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
        return result.stdout if result.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def _memory() -> tuple[int | None, int | None]:
    try:
        import psutil  # optional; does not provide GPU telemetry
        vm = psutil.virtual_memory()
        return int(vm.total), int(vm.available)
    except (ImportError, OSError, AttributeError):
        pass
    if sys_platform := platform.system() == "Linux":
        try:
            values = {}
            for line in Path("/proc/meminfo").read_text().splitlines():
                match = re.match(r"(MemTotal|MemAvailable):\s+(\d+)\s+kB", line)
                if match:
                    values[match.group(1)] = int(match.group(2)) * 1024
            return values.get("MemTotal"), values.get("MemAvailable")
        except OSError:
            return None, None
    return None, None


def _gpus() -> tuple[list[GPUInfo], list[str]]:
    gpus: list[GPUInfo] = []
    warnings: list[str] = []
    # NVIDIA telemetry is authoritative when the vendor utility is available.
    out = _command(["nvidia-smi", "--query-gpu=name,memory.total,memory.free", "--format=csv,noheader,nounits"])
    if out:
        for line in out.splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 3:
                try:
                    gpus.append(GPUInfo(parts[0], "nvidia", int(float(parts[1]) * 1024**2), "dedicated", "nvidia-smi"))
                except ValueError:
                    gpus.append(GPUInfo(parts[0], "nvidia", source="nvidia-smi"))
        if gpus:
            return gpus, warnings
    if platform.system() == "Linux":
        drm = Path("/sys/class/drm")
        try:
            for card in sorted(drm.glob("card[0-9]*")):
                device = card / "device"
                vendor = (device / "vendor").read_text().strip().lower()
                name = ""
                for key in ("product_name", "uevent"):
                    candidate = device / key
                    if candidate.is_file():
                        name = candidate.read_text(errors="replace").strip().splitlines()[0]
                        if name:
                            break
                if vendor in {"0x10de", "0x1002", "0x8086"}:
                    vendor_name = {"0x10de": "nvidia", "0x1002": "amd", "0x8086": "intel"}[vendor]
                    gpus.append(GPUInfo(name or f"{vendor_name.title()} display adapter", vendor_name, source="sysfs; compute capability unverified"))
        except OSError:
            warnings.append("Some Linux display-adapter details were inaccessible.")
    if not gpus:
        warnings.append("GPU compute capability and VRAM could not be verified; no GPU acceleration is assumed.")
    return gpus, warnings


def detect_hardware() -> HardwareProfile:
    """Return measured host information where available; unknown values remain None."""
    cpu = platform.processor() or platform.machine() or "Unknown CPU"
    cores = os.cpu_count()
    total, available = _memory()
    gpus, warnings = _gpus()
    if total is None:
        warnings.append("System RAM could not be measured; model sizing will be conservative.")
    confidence = "high" if total is not None and cores is not None and gpus and not warnings else "partial"
    return HardwareProfile(platform.system(), platform.version(), platform.machine(), cpu, cores, total, available, gpus, confidence, warnings)


def recommend_policy(profile: HardwareProfile, policy: str = "automatic") -> dict[str, str | int | None]:
    """Conservative baseline recommendation; this is a heuristic, not a fit guarantee."""
    policy = policy.lower()
    if policy not in {"automatic", "lightweight", "quality"}:
        raise ValueError("policy must be automatic, lightweight, or quality")
    ram = profile.ram_available_bytes or profile.ram_total_bytes
    if policy == "lightweight" or ram is None or ram < 6 * 1024**3:
        size, context = "1B–3B parameters, Q4 GGUF", 2048
    elif policy == "quality" and ram >= 20 * 1024**3:
        size, context = "7B–8B parameters, Q4 GGUF (verify memory requirements)", 4096
    elif ram >= 12 * 1024**3:
        size, context = "3B–4B parameters, Q4 GGUF", 4096
    else:
        size, context = "3B–4B parameters, Q4 GGUF; close other applications", 2048
    return {"policy": policy, "model_class": size, "context_length": context,
            "gpu_offload": "only after runtime/backend and VRAM compatibility are verified"}
