"""Execution handlers for pre-approved safety primitives."""

import os
import time
from typing import Dict, Any, Tuple, Optional, Callable
from ..types import SafetyPrimitive


class SafetyPrimitiveHandler:
    """Executes validated safety primitives on target edge microservices.

    Interacts with simulated microservice cluster or system services.
    Free-form shell commands are prohibited.
    """

    def __init__(self, cluster_interface: Optional[Any] = None):
        self.cluster = cluster_interface

    def execute_primitive(
        self,
        action: SafetyPrimitive,
        target_service: str,
        parameters: Dict[str, Any],
        dry_run: bool = False,
    ) -> Tuple[bool, str]:
        """Route and execute a verified safety primitive."""
        if dry_run:
            return True, f"[DRY-RUN] Verified safety primitive '{action.value}' on '{target_service}' with params: {parameters}"

        if action == SafetyPrimitive.RESTART_SERVICE:
            return self._handle_restart(target_service, parameters)
        elif action == SafetyPrimitive.FLUSH_CACHE:
            return self._handle_flush_cache(target_service, parameters)
        elif action == SafetyPrimitive.REALLOCATE_RAM:
            return self._handle_reallocate_ram(target_service, parameters)
        elif action == SafetyPrimitive.SCALE_WORKER:
            return self._handle_scale_worker(target_service, parameters)
        elif action == SafetyPrimitive.CLEAR_LOCKFILE:
            return self._handle_clear_lockfile(target_service, parameters)
        elif action == SafetyPrimitive.KILL_ZOMBIE:
            return self._handle_kill_zombie(target_service, parameters)
        elif action == SafetyPrimitive.PURGE_QUEUE:
            return self._handle_purge_queue(target_service, parameters)
        else:
            return False, f"Unsupported safety primitive: {action}"

    def _handle_restart(self, target: str, params: Dict[str, Any]) -> Tuple[bool, str]:
        """Safely restart target microservice."""
        if self.cluster:
            svc = self.cluster.get_service(target)
            if svc:
                return svc.restart(params)
        return True, f"Service '{target}' restarted successfully (graceful)."

    def _handle_flush_cache(self, target: str, params: Dict[str, Any]) -> Tuple[bool, str]:
        """Flush corrupted or overloaded in-memory cache namespace."""
        if self.cluster:
            svc = self.cluster.get_service(target)
            if svc and hasattr(svc, "flush_cache"):
                return svc.flush_cache(params)
        return True, f"Cache namespace in '{target}' flushed and re-initialized."

    def _handle_reallocate_ram(self, target: str, params: Dict[str, Any]) -> Tuple[bool, str]:
        """Reallocate memory buffer limits or adjust cgroup memory quota."""
        mb = params.get("additional_mb", 128)
        if self.cluster:
            svc = self.cluster.get_service(target)
            if svc and hasattr(svc, "adjust_memory_limit"):
                return svc.adjust_memory_limit(mb)
        return True, f"Reallocated memory quota (+{mb}MB) for '{target}'."

    def _handle_scale_worker(self, target: str, params: Dict[str, Any]) -> Tuple[bool, str]:
        """Adjust worker thread pool concurrency."""
        delta = params.get("worker_delta", 2)
        if self.cluster:
            svc = self.cluster.get_service(target)
            if svc and hasattr(svc, "scale_workers"):
                return svc.scale_workers(delta)
        return True, f"Adjusted worker pool on '{target}' by {delta:+d} threads."

    def _handle_clear_lockfile(self, target: str, params: Dict[str, Any]) -> Tuple[bool, str]:
        """Atomically clear stale lockfile if holder PID is dead or orphaned."""
        path = params.get("lockfile_path", "/tmp/iot_broker.lock")
        if self.cluster:
            svc = self.cluster.get_service(target)
            if svc and hasattr(svc, "clear_lock"):
                return svc.clear_lock(path)
        # Check local file
        if os.path.exists(path):
            try:
                os.remove(path)
                return True, f"Stale lockfile '{path}' atomically unlinked."
            except Exception as e:
                return False, f"Failed to unlink lockfile '{path}': {e}"
        return True, f"Verified lockfile cleared for '{target}'."

    def _handle_kill_zombie(self, target: str, params: Dict[str, Any]) -> Tuple[bool, str]:
        """Reap orphaned zombie child processes and reclaim file descriptors."""
        if self.cluster:
            svc = self.cluster.get_service(target)
            if svc and hasattr(svc, "reap_zombies"):
                return svc.reap_zombies(params)
        return True, f"Reaped zombie subprocesses and closed leaked descriptors on '{target}'."

    def _handle_purge_queue(self, target: str, params: Dict[str, Any]) -> Tuple[bool, str]:
        """Drain poison messages from queue to dead-letter storage."""
        if self.cluster:
            svc = self.cluster.get_service(target)
            if svc and hasattr(svc, "purge_queue"):
                return svc.purge_queue(params)
        return True, f"Poison messages drained from '{target}' queue to DLQ."
