"""Fault injection testbed for chaos testing and autonomous healing validation."""

import time
from typing import Dict, Any, List, Optional
from .cluster import EdgeMicroserviceCluster


class FaultInjector:
    """Injects synthetic hardware and software anomalies into the edge microservice cluster.

    Enables deterministic testing of the closed-loop agentic healing cycle:
    Perception -> Anomaly Trigger -> RAG Search -> CoT Reasoning -> Action -> Validation.
    """

    SUPPORTED_FAULTS = [
        "memory_leak",
        "lockfile_deadlock",
        "thread_starvation",
        "cache_corruption",
        "queue_overflow",
        "zombie_leak",
        "unresolvable_fault",  # Triggers rollback verification
    ]

    def __init__(self, cluster: EdgeMicroserviceCluster):
        self.cluster = cluster
        self.active_injections: List[Dict[str, Any]] = []

    def inject(self, fault_type: str) -> Dict[str, Any]:
        """Inject a specific fault type into the cluster."""
        timestamp = time.time()
        record: Dict[str, Any] = {"fault_type": fault_type, "timestamp": timestamp}

        if fault_type == "memory_leak":
            self.cluster.payment_gateway.inject_memory_leak()
            record["target"] = "payment-gateway"
            record["description"] = "Injected 680MB heap memory buffer leak into payment stream gateway."

        elif fault_type == "lockfile_deadlock":
            self.cluster.iot_broker.inject_lockfile_deadlock()
            record["target"] = "iot-telemetry-broker"
            record["description"] = "Injected stale lockfile deadlock into IoT telemetry broker (/tmp/iot_broker.lock)."

        elif fault_type == "thread_starvation":
            self.cluster.inference_worker.inject_thread_starvation()
            record["target"] = "inference-worker"
            record["description"] = "Injected batch inference saturation; queue surged to 65 items."

        elif fault_type == "cache_corruption":
            self.cluster.cache_sync.inject_cache_corruption()
            record["target"] = "cache-sync"
            record["description"] = "Corrupted key-value cache namespace; error rate surged to 16.5 err/sec."

        elif fault_type == "queue_overflow":
            self.cluster.cache_sync.inject_queue_overflow()
            record["target"] = "cache-sync"
            record["description"] = "Injected poison pill packet into head of queue; backlog locked."

        elif fault_type == "zombie_leak":
            self.cluster.device_registry.inject_zombie_leak()
            record["target"] = "device-registry"
            record["description"] = "Spawned 14 zombie child processes; 120 leaked open file handles."

        elif fault_type == "unresolvable_fault":
            # Marks a service dead and hooks it so first remediation attempt fails to normalize,
            # triggering the Atomic Rollback mechanism!
            self.cluster.payment_gateway.inject_memory_leak()
            self.cluster.payment_gateway.health = "DEAD"  # Explicitly fail post-action check
            record["target"] = "payment-gateway"
            record["description"] = "Injected unresolvable hardware degradation to verify atomic rollback."

        else:
            raise ValueError(f"Unknown fault type '{fault_type}'. Supported: {self.SUPPORTED_FAULTS}")

        self.active_injections.append(record)
        return record

    def clear_all(self) -> None:
        """Clear all active faults and restore cluster to nominal health."""
        for svc in self.cluster._services.values():
            svc.restart({})
        self.active_injections.clear()
