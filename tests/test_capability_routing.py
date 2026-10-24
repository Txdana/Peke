"""Unit tests for capability detection and provider routing rules."""

from peke.capability import HardwareCapability, determine_routing_plan
from peke.config import Settings


def test_hardware_capability_feasibility():
    cap = HardwareCapability(
        total_ram_bytes=16 * 1024**3,
        available_ram_bytes=8 * 1024**3,
        gpu_type="NVIDIA RTX 4090",
        total_vram_bytes=24 * 1024**3,
        available_vram_bytes=20 * 1024**3,
    )

    model_size = 4 * 1024**3
    assert cap.can_run_single_local(model_size) is True
    assert cap.can_run_concurrent_local(model_size) is True


def test_routing_plan_local_main_provider():
    settings = Settings(model_path=None, provider_main_kind="local_builtin", provider_subagents_mode="auto")
    cap = HardwareCapability(
        total_ram_bytes=16 * 1024**3,
        available_ram_bytes=8 * 1024**3,
        gpu_type=None,
        total_vram_bytes=None,
        available_vram_bytes=None,
    )

    plan = determine_routing_plan(settings, capability=cap)
    assert plan.main_provider_kind == "local_builtin"
    assert plan.subagent_execution_mode == "sequential_local"
    assert plan.cloud_consent_required is False


def test_routing_plan_cloud_main_provider():
    settings = Settings(model_path=None, provider_main_kind="openrouter", provider_subagents_mode="auto")
    plan = determine_routing_plan(settings)
    assert plan.main_provider_kind == "openrouter"
    assert plan.subagent_execution_mode == "parallel_cloud"
    assert plan.cloud_consent_required is True


def test_routing_plan_insufficient_hardware():
    settings = Settings(model_path=None, provider_main_kind="local_builtin", provider_subagents_mode="auto")
    cap = HardwareCapability(
        total_ram_bytes=4 * 1024**3,
        available_ram_bytes=1 * 1024**3,
        gpu_type=None,
        total_vram_bytes=None,
        available_vram_bytes=None,
    )

    plan = determine_routing_plan(settings, capability=cap, active_model_size_bytes=4 * 1024**3)
    assert plan.subagent_execution_mode == "disabled"
    assert "insufficient" in plan.notice
