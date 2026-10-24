"""Hardware capability detection and capability-aware provider routing."""
import importlib.util
import logging
from dataclasses import dataclass

from peke.config import Settings

logger = logging.getLogger(__name__)


@dataclass
class HardwareCapability:
    total_ram_bytes: int
    available_ram_bytes: int
    gpu_type: str | None
    total_vram_bytes: int | None
    available_vram_bytes: int | None

    def can_run_concurrent_local(self, model_size_bytes: int) -> bool:
        """Estimate if hardware can support multiple concurrent local model instances."""
        estimated_needed = int(model_size_bytes * 2.4)
        if self.available_vram_bytes and self.available_vram_bytes >= estimated_needed:
            return True
        if self.available_ram_bytes >= estimated_needed:
            return True
        return False

    def can_run_single_local(self, model_size_bytes: int) -> bool:
        """Estimate if hardware can support a single local model instance."""
        estimated_needed = int(model_size_bytes * 1.2)
        if self.available_vram_bytes and self.available_vram_bytes >= estimated_needed:
            return True
        if self.available_ram_bytes >= estimated_needed:
            return True
        return False


def detect_capabilities() -> HardwareCapability:
    """Detect current system RAM, available RAM, GPU, and VRAM."""
    total_ram = 8 * 1024 * 1024 * 1024
    avail_ram = 4 * 1024 * 1024 * 1024

    if importlib.util.find_spec("psutil") is not None:
        try:
            import psutil

            mem = psutil.virtual_memory()
            total_ram = mem.total
            avail_ram = mem.available
        except Exception as exc:
            logger.debug("psutil memory detection failed: %s", exc)

    gpu_type = None
    total_vram = None
    avail_vram = None

    if importlib.util.find_spec("pynvml") is not None or importlib.util.find_spec("nvidia_ml_py") is not None:
        try:
            import pynvml

            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            gpu_type = pynvml.nvmlDeviceGetName(handle)
            if isinstance(gpu_type, bytes):
                gpu_type = gpu_type.decode("utf-8")
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            total_vram = mem_info.total
            avail_vram = mem_info.free
        except Exception as exc:
            logger.debug("NVIDIA NVML GPU detection failed: %s", exc)

    return HardwareCapability(
        total_ram_bytes=total_ram,
        available_ram_bytes=avail_ram,
        gpu_type=gpu_type,
        total_vram_bytes=total_vram,
        available_vram_bytes=avail_vram,
    )


@dataclass
class RoutingPlan:
    main_provider_kind: str
    subagent_provider_kind: str
    subagent_execution_mode: str
    notice: str
    cloud_consent_required: bool = False


def determine_routing_plan(
    settings: Settings,
    capability: HardwareCapability | None = None,
    active_model_size_bytes: int = 4 * 1024 * 1024 * 1024,
) -> RoutingPlan:
    """Determine optimal provider routing plan based on configuration and hardware."""
    cap = capability or detect_capabilities()
    main_kind = settings.provider_main_kind

    if settings.provider_subagents_mode == "per_role":
        return RoutingPlan(
            main_provider_kind=main_kind,
            subagent_provider_kind="per_role",
            subagent_execution_mode="parallel_cloud" if main_kind != "local_builtin" else "sequential_local",
            notice="Sub-agent provider routing in per_role mode.",
            cloud_consent_required=main_kind in {"openrouter", "custom_openai"},
        )

    if main_kind in {"ollama", "openrouter", "custom_openai"}:
        return RoutingPlan(
            main_provider_kind=main_kind,
            subagent_provider_kind=main_kind,
            subagent_execution_mode="parallel_cloud",
            notice=f"Running sub-agents using {main_kind} (parallel cloud/external execution).",
            cloud_consent_required=main_kind in {"openrouter", "custom_openai"},
        )

    can_single = cap.can_run_single_local(active_model_size_bytes)
    if can_single:
        return RoutingPlan(
            main_provider_kind="local_builtin",
            subagent_provider_kind="local_builtin",
            subagent_execution_mode="sequential_local",
            notice="Running sub-agents locally using shared model (sequential local execution).",
            cloud_consent_required=False,
        )

    return RoutingPlan(
        main_provider_kind="local_builtin",
        subagent_provider_kind="disabled",
        subagent_execution_mode="disabled",
        notice="Local hardware resources insufficient for sub-agent execution. Configure a cloud provider or free system memory.",
        cloud_consent_required=False,
    )
