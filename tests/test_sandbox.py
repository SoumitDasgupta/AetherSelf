"""Unit tests for Sandbox Action Executor & Safety Boundaries."""

import pytest
import asyncio
from aetherself.types import SafetyPrimitive, ServiceHealth, ActionPlan, ModelTier
from aetherself.sandbox import (
    SandboxedActionExecutor,
    SafetyPrimitiveHandler,
    StateCheckpointManager,
    AntiFlappingGuard,
)
from aetherself.simulation import EdgeMicroserviceCluster


@pytest.mark.asyncio
async def test_sandbox_execution_and_checkpoint():
    cluster = EdgeMicroserviceCluster()
    cluster.payment_gateway.inject_memory_leak()
    assert cluster.payment_gateway.health == ServiceHealth.CRITICAL

    handler = SafetyPrimitiveHandler(cluster)
    executor = SandboxedActionExecutor(primitive_handler=handler)

    plan = ActionPlan(
        plan_id="TEST-001",
        target_service="payment-gateway",
        action=SafetyPrimitive.RESTART_SERVICE,
        parameters={"graceful_timeout_s": 1},
        root_cause_diagnosis="Test memory leak",
        confidence=0.99,
        rollback_action=SafetyPrimitive.REALLOCATE_RAM,
        rollback_parameters={"additional_mb": 256},
        model_used=ModelTier.TIER_2_DIAGNOSTIC,
        synthesis_latency_s=0.2,
    )

    result = await executor.execute_plan(plan)
    assert result.success
    assert not result.rolled_back
    assert cluster.payment_gateway.health == ServiceHealth.HEALTHY


@pytest.mark.asyncio
async def test_anti_flapping_guardrails():
    guard = AntiFlappingGuard()
    target = "flapping-service"

    # Attempt 1, 2, 3 allowed
    for _ in range(3):
        allowed, reason = guard.verify_action_allowed(SafetyPrimitive.RESTART_SERVICE, target)
        assert allowed
        guard.record_action_attempt(target)

    # 4th attempt should be blocked by max retry limit (3 retries max)
    allowed, reason = guard.verify_action_allowed(SafetyPrimitive.RESTART_SERVICE, target)
    assert not allowed
    assert "Max retry limit" in reason


@pytest.mark.asyncio
async def test_atomic_rollback_on_failed_validation():
    cluster = EdgeMicroserviceCluster()
    cluster.payment_gateway.inject_memory_leak()
    handler = SafetyPrimitiveHandler(cluster)
    executor = SandboxedActionExecutor(primitive_handler=handler)

    # Fake validation probe that reports critical status to trigger rollback
    from aetherself.types import TelemetrySnapshot
    def bad_probe():
        return TelemetrySnapshot(
            cpu_percent=50.0,
            memory_percent=95.0,  # Fails memory normalization!
            memory_mb=1900.0,
            disk_percent=30.0,
            ipc_latency_ms=10.0,
            thread_count=10,
            open_file_handles=10,
            queue_backlog=0,
            error_log_rate=0.0,
            services_status={"payment-gateway": ServiceHealth.CRITICAL},
        )
    executor.register_validation_probe(bad_probe)

    plan = ActionPlan(
        plan_id="TEST-ROLLBACK",
        target_service="payment-gateway",
        action=SafetyPrimitive.RESTART_SERVICE,
        parameters={},
        root_cause_diagnosis="Memory failure",
        confidence=0.95,
        rollback_action=SafetyPrimitive.REALLOCATE_RAM,
        rollback_parameters={"additional_mb": 128},
        model_used=ModelTier.TIER_2_DIAGNOSTIC,
        synthesis_latency_s=0.1,
    )

    res = await executor.execute_plan(plan)
    assert not res.success
    assert res.rolled_back
    assert "Atomic rollback" in res.message
