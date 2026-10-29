"""Realistic edge microservices with fault injection and remediation hooks."""

import os
import tempfile
import time
from typing import Dict, Any, Tuple
from ..types import ServiceHealth, SafetyPrimitive


class BaseSimulatedService:
    """Base interface for an edge microservice."""

    def __init__(self, name: str):
        self.name = name
        self.health = ServiceHealth.HEALTHY
        self.active_fault: bool = False
        self.fault_name: str = ""
        self.last_restart_time: float = time.time()

    def get_status(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "health": self.health.value,
            "active_fault": self.active_fault,
            "fault_name": self.fault_name,
            "uptime_s": round(time.time() - self.last_restart_time, 1),
        }

    def restart(self, params: Dict[str, Any]) -> Tuple[bool, str]:
        self.health = ServiceHealth.HEALTHY
        self.active_fault = False
        self.fault_name = ""
        self.last_restart_time = time.time()
        return True, f"Service '{self.name}' gracefully restarted."


class PaymentGatewayService(BaseSimulatedService):
    """Payment transaction stream gateway prone to heap buffer leaks."""

    def __init__(self):
        super().__init__("payment-gateway")
        self.memory_overhead_mb: float = 0.0
        self.allocated_buffers = []

    def inject_memory_leak(self) -> None:
        """Trigger rapid memory leak."""
        self.active_fault = True
        self.fault_name = "MEMORY_LEAK_SPIKE"
        self.health = ServiceHealth.CRITICAL
        self.memory_overhead_mb = 680.0

    def restart(self, params: Dict[str, Any]) -> Tuple[bool, str]:
        self.allocated_buffers.clear()
        self.memory_overhead_mb = 0.0
        return super().restart(params)

    def adjust_memory_limit(self, mb: float) -> Tuple[bool, str]:
        self.memory_overhead_mb = max(0.0, self.memory_overhead_mb - mb)
        if self.memory_overhead_mb < 100:
            self.health = ServiceHealth.HEALTHY
            self.active_fault = False
        return True, f"Memory quota increased by {mb}MB for {self.name}."


class IoTBrokerService(BaseSimulatedService):
    """MQTT/IPC telemetry broker prone to stale lockfile deadlocks."""

    def __init__(self):
        super().__init__("iot-telemetry-broker")
        self.lockfile_path = os.path.join(tempfile.gettempdir(), "iot_broker.lock")
        self.deadlocked: bool = False

    def inject_lockfile_deadlock(self) -> None:
        """Trigger stale lockfile deadlock."""
        self.active_fault = True
        self.fault_name = "LOCKFILE_DEADLOCK"
        self.health = ServiceHealth.CRITICAL
        self.deadlocked = True
        try:
            with open(self.lockfile_path, "w") as f:
                f.write(f"PID: 999999 (DEADLOCK) - {time.time()}\n")
        except Exception:
            pass

    def clear_lock(self, path: str) -> Tuple[bool, str]:
        """Clear stale lockfile."""
        target_path = path or self.lockfile_path
        if os.path.exists(target_path):
            try:
                os.remove(target_path)
            except Exception:
                pass
        self.deadlocked = False
        self.active_fault = False
        self.health = ServiceHealth.HEALTHY
        return True, f"Stale lockfile {target_path} removed, broker released."

    def restart(self, params: Dict[str, Any]) -> Tuple[bool, str]:
        self.clear_lock(self.lockfile_path)
        return super().restart(params)


class InferenceWorkerService(BaseSimulatedService):
    """Computer vision / sensor model worker prone to thread pool starvation."""

    def __init__(self):
        super().__init__("inference-worker")
        self.worker_threads: int = 4
        self.starved: bool = False
        self.backlog_count: int = 0

    def inject_thread_starvation(self) -> None:
        """Trigger batch inference thread saturation."""
        self.active_fault = True
        self.fault_name = "THREAD_POOL_STARVATION"
        self.health = ServiceHealth.DEGRADED
        self.starved = True
        self.backlog_count = 65

    def scale_workers(self, delta: int) -> Tuple[bool, str]:
        """Scale worker thread pool."""
        self.worker_threads = max(1, self.worker_threads + delta)
        if self.worker_threads >= 8:
            self.starved = False
            self.backlog_count = 2
            self.active_fault = False
            self.health = ServiceHealth.HEALTHY
        return True, f"Worker thread pool scaled to {self.worker_threads} threads."

    def restart(self, params: Dict[str, Any]) -> Tuple[bool, str]:
        self.worker_threads = 4
        self.starved = False
        self.backlog_count = 0
        return super().restart(params)


class CacheSyncService(BaseSimulatedService):
    """In-memory key-value cache prone to corrupted state and queue poison pills."""

    def __init__(self):
        super().__init__("cache-sync")
        self.corrupted: bool = False
        self.queue_poisoned: bool = False
        self.error_rate: float = 0.0

    def inject_cache_corruption(self) -> None:
        """Trigger cache poison state and deserialization failure."""
        self.active_fault = True
        self.fault_name = "CACHE_CORRUPTION_CASCADE"
        self.health = ServiceHealth.CRITICAL
        self.corrupted = True
        self.error_rate = 16.5

    def inject_queue_overflow(self) -> None:
        """Trigger poison message head-of-line blocking in queue."""
        self.active_fault = True
        self.fault_name = "QUEUE_POISON_OVERFLOW"
        self.health = ServiceHealth.CRITICAL
        self.queue_poisoned = True
        self.error_rate = 12.0

    def flush_cache(self, params: Dict[str, Any]) -> Tuple[bool, str]:
        """Flush corrupted cache namespace."""
        self.corrupted = False
        self.error_rate = 0.1
        self.active_fault = False
        self.health = ServiceHealth.HEALTHY
        return True, "Cache namespace flushed and re-indexed."

    def purge_queue(self, params: Dict[str, Any]) -> Tuple[bool, str]:
        """Purge poison messages to dead-letter queue."""
        self.queue_poisoned = False
        self.error_rate = 0.1
        self.active_fault = False
        self.health = ServiceHealth.HEALTHY
        return True, "Poison queue purged to dead-letter queue."

    def restart(self, params: Dict[str, Any]) -> Tuple[bool, str]:
        self.corrupted = False
        self.queue_poisoned = False
        self.error_rate = 0.0
        return super().restart(params)


class DeviceRegistryService(BaseSimulatedService):
    """Device connection registry prone to orphaned zombie processes."""

    def __init__(self):
        super().__init__("device-registry")
        self.zombie_count: int = 0
        self.leaked_descriptors: int = 0

    def inject_zombie_leak(self) -> None:
        """Trigger un-reaped child process descriptor leak."""
        self.active_fault = True
        self.fault_name = "ZOMBIE_PROCESS_LEAK"
        self.health = ServiceHealth.DEGRADED
        self.zombie_count = 14
        self.leaked_descriptors = 120

    def reap_zombies(self, params: Dict[str, Any]) -> Tuple[bool, str]:
        """Reap zombie subprocesses."""
        reaped = self.zombie_count
        self.zombie_count = 0
        self.leaked_descriptors = 0
        self.active_fault = False
        self.health = ServiceHealth.HEALTHY
        return True, f"Reaped {reaped} zombie child processes and closed descriptors."

    def restart(self, params: Dict[str, Any]) -> Tuple[bool, str]:
        self.reap_zombies({})
        return super().restart(params)
