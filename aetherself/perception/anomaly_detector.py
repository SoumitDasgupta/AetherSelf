"""Isolation Forest Anomaly Detector with adaptive metric variance analysis."""

import numpy as np
from sklearn.ensemble import IsolationForest
from typing import List, Dict, Optional, Tuple
from ..types import TelemetrySnapshot, ModelTier
from ..config import PerceptionConfig
from .models import AnomalyReport, MetricVariance


class IsolationForestAnomalyDetector:
    """Detects multi-variate anomalies in edge telemetry using Isolation Forest.

    Enforces adaptive thresholding and hysteresis to distinguish transient jitter
    from true edge microservice anomalies (e.g., memory leaks, thread starvation,
    deadlocks, queue backlogs).
    """

    FEATURE_NAMES = [
        "cpu_percent",
        "memory_percent",
        "ipc_latency_ms",
        "thread_count",
        "open_file_handles",
        "queue_backlog",
        "error_log_rate",
    ]

    def __init__(self, config: Optional[PerceptionConfig] = None):
        self.config = config or PerceptionConfig()
        self.model = IsolationForest(
            contamination=self.config.isolation_forest_contamination,
            n_estimators=self.config.isolation_forest_n_estimators,
            random_state=42,
        )
        self.is_fitted: bool = False
        self.consecutive_anomalies: int = 0
        self.baseline_mean: np.ndarray = np.zeros(len(self.FEATURE_NAMES))
        self.baseline_std: np.ndarray = np.ones(len(self.FEATURE_NAMES))
        self._fit_default_baseline()

    def _extract_features(self, snapshot: TelemetrySnapshot) -> np.ndarray:
        """Extract numeric feature vector from a snapshot."""
        return np.array([
            snapshot.cpu_percent,
            snapshot.memory_percent,
            snapshot.ipc_latency_ms,
            float(snapshot.thread_count),
            float(snapshot.open_file_handles),
            float(snapshot.queue_backlog),
            snapshot.error_log_rate,
        ], dtype=np.float32)

    def _fit_default_baseline(self) -> None:
        """Seed the detector with synthetic normal operational distributions.

        Ensures zero-cold-start capability on standard developer workstations,
        Raspberry Pi 5, or Jetson Nano without requiring hours of manual baseline capture.
        """
        np.random.seed(42)
        n_samples = 400

        # Normal distributions representing stable edge microservices
        normal_cpu = np.random.normal(loc=18.0, scale=6.0, size=n_samples).clip(1.0, 45.0)
        normal_mem = np.random.normal(loc=32.0, scale=4.0, size=n_samples).clip(10.0, 50.0)
        normal_ipc = np.random.normal(loc=2.5, scale=1.0, size=n_samples).clip(0.5, 10.0)
        normal_threads = np.random.normal(loc=16.0, scale=2.0, size=n_samples).clip(8.0, 32.0)
        normal_handles = np.random.normal(loc=35.0, scale=5.0, size=n_samples).clip(15.0, 70.0)
        normal_queue = np.random.poisson(lam=1.2, size=n_samples).clip(0, 10)
        normal_errors = np.random.exponential(scale=0.05, size=n_samples).clip(0.0, 0.4)

        X_train = np.column_stack([
            normal_cpu,
            normal_mem,
            normal_ipc,
            normal_threads,
            normal_handles,
            normal_queue,
            normal_errors,
        ])

        self.baseline_mean = np.mean(X_train, axis=0)
        self.baseline_std = np.std(X_train, axis=0) + 1e-5
        self.model.fit(X_train)
        self.is_fitted = True

    def fit_custom_baseline(self, snapshots: List[TelemetrySnapshot]) -> None:
        """Fit detector on captured real-world telemetry snapshots."""
        if len(snapshots) < 20:
            return
        X = np.array([self._extract_features(s) for s in snapshots])
        self.baseline_mean = np.mean(X, axis=0)
        self.baseline_std = np.std(X, axis=0) + 1e-5
        self.model.fit(X)
        self.is_fitted = True

    def analyze(self, snapshot: TelemetrySnapshot) -> AnomalyReport:
        """Evaluate a telemetry snapshot for anomalies and calculate variance."""
        features = self._extract_features(snapshot)
        X = features.reshape(1, -1)

        # Raw decision score: lower values indicate higher anomaly likelihood
        raw_score = float(self.model.decision_function(X)[0])

        # Normalize score into [0.0, 1.0] where 1.0 is extremely anomalous
        # Typical decision_function values range from -0.35 (severe anomaly) to +0.25 (typical)
        normalized_score = float(np.clip(1.0 - (raw_score + 0.35) / 0.60, 0.0, 1.0))

        # Check for service-level explicit degraded indicators
        service_critical = any(
            status in ("DEGRADED", "CRITICAL", "DEAD")
            for status in snapshot.services_status.values()
        )

        is_raw_anomaly = (raw_score < self.config.anomaly_threshold) or service_critical

        # Compute metric variances relative to baseline
        deviant_metrics: List[MetricVariance] = []
        for i, name in enumerate(self.FEATURE_NAMES):
            cur = float(features[i])
            base = float(self.baseline_mean[i])
            sigma = (cur - base) / float(self.baseline_std[i])
            is_deviant = abs(sigma) >= 2.5
            if is_deviant or (name == "queue_backlog" and cur > 15) or (name == "error_log_rate" and cur > 1.0):
                deviant_metrics.append(
                    MetricVariance(
                        metric_name=name,
                        baseline_value=round(base, 2),
                        current_value=round(cur, 2),
                        deviation_sigma=round(sigma, 2),
                        is_deviant=True,
                    )
                )

        # Hysteresis filtering: require consecutive flags to elevate to RESOLUTION_REQUIRED
        if is_raw_anomaly or len(deviant_metrics) >= 1:
            self.consecutive_anomalies += 1
        else:
            self.consecutive_anomalies = max(0, self.consecutive_anomalies - 1)

        elevate = self.consecutive_anomalies >= self.config.hysteresis_count

        # Formulate human-readable context summary
        summary_parts = []
        for dev in deviant_metrics:
            summary_parts.append(f"{dev.metric_name}={dev.current_value} (sigma={dev.deviation_sigma:+.1f})")
        if not summary_parts and is_raw_anomaly:
            summary_parts.append("multi-metric isolation forest variance")
        context_str = ", ".join(summary_parts) if summary_parts else "All metrics nominal"

        rec_tier = (
            ModelTier.TIER_2_DIAGNOSTIC.value
            if elevate or normalized_score > 0.65
            else ModelTier.TIER_1_ROUTINE.value
        )

        # Update snapshot flags
        snapshot.active_anomaly = elevate
        snapshot.anomaly_score = round(normalized_score, 3)

        return AnomalyReport(
            is_anomaly=is_raw_anomaly,
            anomaly_score=round(normalized_score, 3),
            raw_decision_score=round(raw_score, 4),
            primary_deviant_metrics=deviant_metrics,
            elevate_to_resolution=elevate,
            consecutive_trigger_count=self.consecutive_anomalies,
            recommended_tier=rec_tier,
            context_summary=context_str,
        )

    def reset_hysteresis(self) -> None:
        """Reset hysteresis trigger counter after successful self-healing."""
        self.consecutive_anomalies = 0
