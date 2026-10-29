"""Core types, enums, and data definitions for the AetherSelf framework."""

from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
import time


class SystemState(str, Enum):
    """Deterministic states of the AetherSelf agentic lifecycle."""
    NORMAL = "NORMAL"
    SUSPICIOUS = "SUSPICIOUS"
    RESOLUTION_REQUIRED = "RESOLUTION_REQUIRED"
    RAG_RETRIEVAL = "RAG_RETRIEVAL"
    SLM_REASONING = "SLM_REASONING"
    SANDBOX_EXECUTION = "SANDBOX_EXECUTION"
    VALIDATING = "VALIDATING"
    RESOLVED_CLOSED_LOOP = "RESOLVED_CLOSED_LOOP"
    ROLLBACK_TRIGGERED = "ROLLBACK_TRIGGERED"
    ESCALATED_TO_HUMAN = "ESCALATED_TO_HUMAN"


class ModelTier(str, Enum):
    """Dynamic model switching tiers."""
    TIER_1_ROUTINE = "TIER_1_ROUTINE_1B"       # ~1B param low-power routine log classifier
    TIER_2_DIAGNOSTIC = "TIER_2_DIAGNOSTIC_3_8B"  # 3.8B quantized Phi-3.5/Llama-3.2 CoT model


class SafetyPrimitive(str, Enum):
    """Pre-approved deterministic self-healing actions.

    Free-form shell commands are strictly blocked by guardrails.
    """
    RESTART_SERVICE = "RESTART_SERVICE"
    FLUSH_CACHE = "FLUSH_CACHE"
    REALLOCATE_RAM = "REALLOCATE_RAM"
    SCALE_WORKER = "SCALE_WORKER"
    CLEAR_LOCKFILE = "CLEAR_LOCKFILE"
    KILL_ZOMBIE = "KILL_ZOMBIE"
    PURGE_QUEUE = "PURGE_QUEUE"


class ServiceHealth(str, Enum):
    """Health status of an individual monitored edge microservice."""
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    CRITICAL = "CRITICAL"
    RECOVERING = "RECOVERING"
    DEAD = "DEAD"


class TelemetrySnapshot(BaseModel):
    """Point-in-time telemetry snapshot gathered by the Perception probe."""
    timestamp: float = Field(default_factory=time.time)
    cpu_percent: float
    memory_percent: float
    memory_mb: float
    disk_percent: float
    ipc_latency_ms: float
    thread_count: int
    open_file_handles: int
    queue_backlog: int
    error_log_rate: float  # errors per second
    services_status: Dict[str, ServiceHealth] = Field(default_factory=dict)
    active_anomaly: bool = False
    anomaly_score: float = 0.0


class HistoricalIncident(BaseModel):
    """Structured historical incident trace stored in Vector RAG DB."""
    incident_id: str
    title: str
    symptoms: str
    telemetry_signature: Dict[str, float]
    root_cause: str
    recommended_action: SafetyPrimitive
    target_service: str
    action_parameters: Dict[str, Any] = Field(default_factory=dict)
    rollback_primitive: SafetyPrimitive = SafetyPrimitive.RESTART_SERVICE
    rollback_parameters: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.95
    timestamp: float = Field(default_factory=time.time)
    verified_resolutions_count: int = 1
    mean_resolution_time_s: float = 2.4


class RAGRetrievalResult(BaseModel):
    """Ranked RAG retrieval match with freshness decay scoring."""
    incident: HistoricalIncident
    vector_similarity: float
    freshness_decay_factor: float
    final_score: float
    rank: int


class ActionPlan(BaseModel):
    """Structured Pydantic action plan synthesized by CoT reasoning engine."""
    plan_id: str
    target_service: str
    action: SafetyPrimitive
    parameters: Dict[str, Any] = Field(default_factory=dict)
    chain_of_thought: List[str] = Field(default_factory=list)
    root_cause_diagnosis: str
    confidence: float = Field(ge=0.0, le=1.0)
    rollback_action: SafetyPrimitive
    rollback_parameters: Dict[str, Any] = Field(default_factory=dict)
    model_used: ModelTier
    synthesis_latency_s: float
    expected_normalization_window_s: float = 3.0


class ExecutionResult(BaseModel):
    """Result of sandboxed action execution."""
    success: bool
    action: SafetyPrimitive
    target_service: str
    message: str
    pre_checkpoint_id: Optional[str] = None
    execution_time_s: float
    rolled_back: bool = False
    rollback_reason: Optional[str] = None
