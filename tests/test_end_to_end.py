"""End-to-End closed-loop autonomous self-healing tests."""

import pytest
import asyncio
import time
from aetherself.daemon import AetherSelfDaemon
from aetherself.types import ModelTier, SystemState


@pytest.mark.asyncio
async def test_end_to_end_memory_leak_self_healing():
    daemon = AetherSelfDaemon()
    # Inject memory leak
    daemon.fault_injector.inject("memory_leak")
    assert daemon.cluster.payment_gateway.active_fault

    # Simulate anomalous perception frame
    snap = daemon.collector.sample_now()
    snap.memory_percent = 91.0
    snap.memory_mb += 680

    daemon.anomaly_detector.analyze(snap)
    report = daemon.anomaly_detector.analyze(snap)
    assert report.elevate_to_resolution

    # Execute healing cycle
    await daemon._execute_self_healing_cycle(snap, report, ModelTier.TIER_2_DIAGNOSTIC)

    # Verify closed-loop recovery
    assert not daemon.cluster.payment_gateway.active_fault
    assert daemon.successful_recoveries >= 1
    assert daemon.state_machine.current_state == SystemState.NORMAL


@pytest.mark.asyncio
async def test_end_to_end_lockfile_deadlock_self_healing():
    daemon = AetherSelfDaemon()
    daemon.fault_injector.inject("lockfile_deadlock")
    assert daemon.cluster.iot_broker.deadlocked

    snap = daemon.collector.sample_now()
    snap.ipc_latency_ms = 320.0
    daemon.anomaly_detector.analyze(snap)
    report = daemon.anomaly_detector.analyze(snap)

    await daemon._execute_self_healing_cycle(snap, report, ModelTier.TIER_2_DIAGNOSTIC)

    assert not daemon.cluster.iot_broker.deadlocked
    assert daemon.successful_recoveries >= 1


@pytest.mark.asyncio
async def test_end_to_end_thread_starvation_self_healing():
    daemon = AetherSelfDaemon()
    daemon.fault_injector.inject("thread_starvation")
    assert daemon.cluster.inference_worker.starved

    snap = daemon.collector.sample_now()
    snap.cpu_percent = 94.0
    snap.queue_backlog = 65
    daemon.anomaly_detector.analyze(snap)
    report = daemon.anomaly_detector.analyze(snap)

    await daemon._execute_self_healing_cycle(snap, report, ModelTier.TIER_2_DIAGNOSTIC)

    assert not daemon.cluster.inference_worker.starved
    assert daemon.cluster.inference_worker.worker_threads >= 8
