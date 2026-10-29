"""Simulated Edge Microservice Cluster coordinator."""

import time
from typing import Dict, Any, Optional
from ..types import ServiceHealth
from .services import (
    BaseSimulatedService,
    PaymentGatewayService,
    IoTBrokerService,
    InferenceWorkerService,
    CacheSyncService,
    DeviceRegistryService,
)


class EdgeMicroserviceCluster:
    """Manages simulated microservices on the edge node."""

    def __init__(self):
        self.payment_gateway = PaymentGatewayService()
        self.iot_broker = IoTBrokerService()
        self.inference_worker = InferenceWorkerService()
        self.cache_sync = CacheSyncService()
        self.device_registry = DeviceRegistryService()

        self._services: Dict[str, BaseSimulatedService] = {
            "payment-gateway": self.payment_gateway,
            "iot-telemetry-broker": self.iot_broker,
            "inference-worker": self.inference_worker,
            "cache-sync": self.cache_sync,
            "device-registry": self.device_registry,
        }

    def get_service(self, name: str) -> Optional[BaseSimulatedService]:
        """Look up service by name."""
        return self._services.get(name)

    def get_services_status(self) -> Dict[str, ServiceHealth]:
        """Return dictionary of service health states."""
        return {name: svc.health for name, svc in self._services.items()}

    def get_cluster_status_summary(self) -> Dict[str, Any]:
        """Detailed status dictionary for all services."""
        return {name: svc.get_status() for name, svc in self._services.items()}

    def compute_ipc_latency_ms(self) -> float:
        """Compute cluster-wide IPC latency. Spikes if broker or services are deadlocked."""
        base_latency = 2.4
        if self.iot_broker.deadlocked:
            return 320.0  # Spikes to 320ms on deadlock
        if self.payment_gateway.memory_overhead_mb > 500:
            return 58.0
        if self.inference_worker.starved:
            return 85.0
        return round(base_latency, 2)

    def compute_queue_backlog(self) -> int:
        """Compute aggregate message queue depth."""
        backlog = 0
        if self.inference_worker.starved:
            backlog += self.inference_worker.backlog_count
        if self.cache_sync.queue_poisoned:
            backlog += 88
        if self.iot_broker.deadlocked:
            backlog += 25
        return backlog

    def compute_error_rate(self) -> float:
        """Compute aggregate error rate in errors/sec."""
        rate = 0.05
        if self.cache_sync.corrupted or self.cache_sync.queue_poisoned:
            rate += self.cache_sync.error_rate
        if self.iot_broker.deadlocked:
            rate += 6.5
        if self.payment_gateway.memory_overhead_mb > 400:
            rate += 3.2
        return round(rate, 2)

    def compute_memory_overhead_mb(self) -> float:
        """Compute additional memory overhead from simulated leaks."""
        return self.payment_gateway.memory_overhead_mb

    def compute_thread_overhead(self) -> int:
        """Compute thread overhead from worker scaling or starvation."""
        return self.inference_worker.worker_threads - 4

    def compute_handle_overhead(self) -> int:
        """Compute leaked file handle count from zombie processes."""
        return self.device_registry.leaked_descriptors
