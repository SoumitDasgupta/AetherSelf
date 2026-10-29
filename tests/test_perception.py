"""Unit tests for the Perception Layer."""

import pytest
import time
from aetherself.perception import TelemetryCollector, IsolationForestAnomalyDetector
from aetherself.types import TelemetrySnapshot, ServiceHealth


def test_telemetry_collector_sampling():
    collector = TelemetryCollector()
    snap = collector.sample_now()
    assert isinstance(snap, TelemetrySnapshot)
    assert snap.cpu_percent >= 0.0
    assert snap.memory_percent > 0.0
    assert snap.memory_mb > 0.0
    assert snap.ipc_latency_ms >= 0.0
    assert snap.thread_count >= 1
    assert snap.open_file_handles >= 1


def test_isolation_forest_nominal_state():
    detector = IsolationForestAnomalyDetector()
    snap = TelemetrySnapshot(
        cpu_percent=18.0,
        memory_percent=32.0,
        memory_mb=512.0,
        disk_percent=45.0,
        ipc_latency_ms=2.5,
        thread_count=16,
        open_file_handles=35,
        queue_backlog=1,
        error_log_rate=0.02,
    )
    rep = detector.analyze(snap)
    assert not rep.elevate_to_resolution
    assert rep.anomaly_score < 0.65
    assert rep.recommended_tier == "TIER_1_ROUTINE_1B"


def test_isolation_forest_anomaly_detection_and_hysteresis():
    detector = IsolationForestAnomalyDetector()
    anomalous_snap = TelemetrySnapshot(
        cpu_percent=95.0,
        memory_percent=91.0,
        memory_mb=1850.0,
        disk_percent=45.0,
        ipc_latency_ms=310.0,
        thread_count=48,
        open_file_handles=160,
        queue_backlog=75,
        error_log_rate=18.5,
    )
    # First frame increases hysteresis count
    rep1 = detector.analyze(anomalous_snap)
    assert rep1.is_anomaly
    assert rep1.anomaly_score > 0.65

    # Second frame exceeds hysteresis count -> elevates to resolution
    rep2 = detector.analyze(anomalous_snap)
    assert rep2.elevate_to_resolution
    assert rep2.recommended_tier == "TIER_2_DIAGNOSTIC_3_8B"
    assert len(rep2.primary_deviant_metrics) >= 1
