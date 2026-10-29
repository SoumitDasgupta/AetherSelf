"""Perception models and metric structures."""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional
import time
from ..types import ServiceHealth, TelemetrySnapshot


class MetricVariance(BaseModel):
    """Calculated metric variance relative to normal operational baseline."""
    metric_name: str
    baseline_value: float
    current_value: float
    deviation_sigma: float
    is_deviant: bool


class AnomalyReport(BaseModel):
    """Structured report produced by the Anomaly Detection probe."""
    timestamp: float = Field(default_factory=time.time)
    is_anomaly: bool
    anomaly_score: float  # Normalized 0.0 (normal) to 1.0 (severe)
    raw_decision_score: float
    primary_deviant_metrics: List[MetricVariance] = Field(default_factory=list)
    elevate_to_resolution: bool
    consecutive_trigger_count: int
    recommended_tier: str = "TIER_1_ROUTINE_1B"
    context_summary: str = ""
