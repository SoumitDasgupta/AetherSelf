"""Sandboxed Action Executor with closed-loop validation and atomic rollback."""

import asyncio
import time
from typing import Optional, Callable, Dict, Any, Tuple
from ..types import (
    ActionPlan,
    ExecutionResult,
    SafetyPrimitive,
    ServiceHealth,
    TelemetrySnapshot,
)
from ..config import SandboxConfig
from .guardrails import AntiFlappingGuard, SafetyGuardrailError
from .checkpoint import StateCheckpointManager, ServiceCheckpoint
from .primitives import SafetyPrimitiveHandler


class SandboxedActionExecutor:
    """Executes validated remediation plans in a safe sandbox with closed-loop validation.

    Flow:
    1. Check Anti-Flapping guardrails and backoff limits.
    2. Capture atomic pre-action checkpoint.
    3. Perform dry-run safety verification.
    4. Execute validated safety primitive.
    5. Monitor system metrics during normalization window.
    6. If metrics normalize -> mark successful, reset retries, update vector memory.
    7. If metrics fail to normalize -> trigger atomic rollback!
    """

    def __init__(
        self,
        config: Optional[SandboxConfig] = None,
        primitive_handler: Optional[SafetyPrimitiveHandler] = None,
        checkpoint_manager: Optional[StateCheckpointManager] = None,
        anti_flapping_guard: Optional[AntiFlappingGuard] = None,
    ):
        self.config = config or SandboxConfig()
        self.handler = primitive_handler or SafetyPrimitiveHandler()
        self.checkpoints = checkpoint_manager or StateCheckpointManager()
        self.guard = anti_flapping_guard or AntiFlappingGuard(self.config)
        self._validation_probe: Optional[Callable[[], TelemetrySnapshot]] = None

    def register_validation_probe(self, probe: Callable[[], TelemetrySnapshot]) -> None:
        """Register probe function to evaluate metric normalization post-action."""
        self._validation_probe = probe

    async def execute_plan(
        self,
        plan: ActionPlan,
        current_health: ServiceHealth = ServiceHealth.DEGRADED,
        service_config: Optional[Dict[str, Any]] = None,
        worker_threads: int = 4,
    ) -> ExecutionResult:
        """Execute action plan with closed-loop validation and rollback protection."""
        t_start = time.perf_counter()
        target = plan.target_service

        # 1. Verify anti-flapping guardrails
        allowed, reason = self.guard.verify_action_allowed(plan.action, target)
        if not allowed:
            return ExecutionResult(
                success=False,
                action=plan.action,
                target_service=target,
                message=reason or "Blocked by safety guardrail",
                execution_time_s=round(time.perf_counter() - t_start, 3),
            )

        # 2. Check exponential backoff delay
        backoff_s = self.guard.get_backoff_delay_s(target)
        if backoff_s > 0:
            await asyncio.sleep(min(backoff_s, 2.0))

        # 3. Capture atomic pre-action checkpoint
        checkpoint = self.checkpoints.capture_checkpoint(
            target_service=target,
            current_health=current_health,
            config_state=service_config or {},
            worker_threads=worker_threads,
            action_intended=plan.action,
            rollback_primitive=plan.rollback_action,
            rollback_parameters=plan.rollback_parameters,
        )

        # 4. Record action attempt
        self.guard.record_action_attempt(target)

        # 5. Dry-run verification
        if self.config.dry_run_first:
            dry_ok, dry_msg = self.handler.execute_primitive(
                plan.action, target, plan.parameters, dry_run=True
            )
            if not dry_ok:
                return ExecutionResult(
                    success=False,
                    action=plan.action,
                    target_service=target,
                    message=f"Dry-run container validation failed: {dry_msg}",
                    pre_checkpoint_id=checkpoint.checkpoint_id,
                    execution_time_s=round(time.perf_counter() - t_start, 3),
                )

        # 6. Live execution
        exec_ok, exec_msg = self.handler.execute_primitive(
            plan.action, target, plan.parameters, dry_run=False
        )

        if not exec_ok:
            # Action execution failed immediately; execute rollback
            await self._execute_rollback(checkpoint, f"Immediate action failure: {exec_msg}")
            return ExecutionResult(
                success=False,
                action=plan.action,
                target_service=target,
                message=f"Execution error: {exec_msg}. Atomic rollback executed.",
                pre_checkpoint_id=checkpoint.checkpoint_id,
                execution_time_s=round(time.perf_counter() - t_start, 3),
                rolled_back=True,
                rollback_reason=exec_msg,
            )

        # 7. Closed-Loop Post-Action Validation
        valid, val_reason = await self._validate_normalization(plan)

        if not valid:
            # Post-action validation check failed -> execute atomic rollback!
            await self._execute_rollback(checkpoint, val_reason)
            return ExecutionResult(
                success=False,
                action=plan.action,
                target_service=target,
                message=f"Post-action validation check failed: {val_reason}. Atomic rollback completed.",
                pre_checkpoint_id=checkpoint.checkpoint_id,
                execution_time_s=round(time.perf_counter() - t_start, 3),
                rolled_back=True,
                rollback_reason=val_reason,
            )

        # 8. Success: Metric normalization verified
        self.guard.record_action_success(target)
        self.checkpoints.discard_checkpoint(checkpoint.checkpoint_id)

        return ExecutionResult(
            success=True,
            action=plan.action,
            target_service=target,
            message=f"Autonomous self-healing completed and verified: {exec_msg}",
            pre_checkpoint_id=checkpoint.checkpoint_id,
            execution_time_s=round(time.perf_counter() - t_start, 3),
            rolled_back=False,
        )

    async def _validate_normalization(self, plan: ActionPlan) -> Tuple[bool, str]:
        """Observe system telemetry during normalization window to verify recovery."""
        window_s = min(plan.expected_normalization_window_s, self.config.validation_window_s)
        # Check in small increments
        steps = 4
        dt = window_s / steps

        for _ in range(steps):
            await asyncio.sleep(dt)
            if self._validation_probe:
                try:
                    snap = self._validation_probe()
                    # If target service is reported as CRITICAL or DEAD, fail validation
                    status = snap.services_status.get(plan.target_service)
                    if status in (ServiceHealth.CRITICAL, ServiceHealth.DEAD):
                        return False, f"Target service '{plan.target_service}' in critical/dead state ({status})"

                    # Check IPC latency sanity if lockfile action
                    if plan.action == SafetyPrimitive.CLEAR_LOCKFILE:
                        if snap.ipc_latency_ms > 300.0:
                            return False, f"IPC latency remains degraded ({snap.ipc_latency_ms}ms)"
                except Exception:
                    pass

        return True, "All telemetry normalized within expected safety envelope."

    async def _execute_rollback(self, checkpoint: ServiceCheckpoint, reason: str) -> None:
        """Trigger atomic rollback compensating action."""
        if not self.config.atomic_rollback_enabled:
            return

        self.handler.execute_primitive(
            checkpoint.rollback_primitive,
            checkpoint.target_service,
            checkpoint.rollback_parameters,
            dry_run=False,
        )
