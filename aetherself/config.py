"""Configuration settings and tuning parameters for the AetherSelf daemon."""

from pydantic import BaseModel, Field
from typing import Optional
import os


class PerceptionConfig(BaseModel):
    """Telemetry collection & anomaly detection tuning."""
    sampling_interval_ms: int = 500  # 500 ms sub-second sampling
    rolling_window_size: int = 30    # Keep last 30 snapshots in memory buffer
    isolation_forest_contamination: float = 0.05
    isolation_forest_n_estimators: int = 100
    anomaly_threshold: float = -0.12  # Decision function cutoff for anomaly trigger
    hysteresis_count: int = 2         # Consecutive anomaly frames before escalating


class RAGConfig(BaseModel):
    """Contextual Vector RAG configuration."""
    persist_directory: str = os.path.join(os.path.expanduser("~"), ".aetherself", "rag_db")
    collection_name: str = "aetherself_incident_memory"
    top_k: int = 3
    embedding_dimension: int = 768    # Nomic-Embed-Text-v1.5 INT8 dimension
    freshness_half_life_days: float = 7.0  # Context decay parameter (lambda)
    similarity_threshold: float = 0.60
    max_retrieval_latency_ms: float = 150.0  # < 150ms constraint


class ReasoningConfig(BaseModel):
    """Dynamic model switching & diagnostic synthesis settings."""
    tier_1_model_name: str = "phi-1b-routine-classifier"
    tier_2_model_name: str = "phi-3.5-mini-3.8b-instruct"
    max_reasoning_time_s: float = 2.5       # < 2.5s constraint
    escalation_anomaly_score_threshold: float = 0.65
    ollama_base_url: Optional[str] = "http://localhost:11434"
    enable_cot_chain: bool = True
    temperature: float = 0.1                # Low temp for deterministic logic


class SandboxConfig(BaseModel):
    """Execution sandbox, safety boundaries, and anti-flapping guardrails."""
    validation_window_s: float = 3.0        # Time window to verify post-action normalization
    max_retries: int = 3                    # Max retry attempts before alerting human
    exponential_backoff_base_s: float = 1.0 # 1s, 2s, 4s backoff
    flapping_window_s: float = 60.0         # Time window to detect cyclic oscillations
    max_flapping_triggers: int = 4
    atomic_rollback_enabled: bool = True
    dry_run_first: bool = True


class SystemConfig(BaseModel):
    """Master AetherSelf framework configuration."""
    perception: PerceptionConfig = Field(default_factory=PerceptionConfig)
    rag: RAGConfig = Field(default_factory=RAGConfig)
    reasoning: ReasoningConfig = Field(default_factory=ReasoningConfig)
    sandbox: SandboxConfig = Field(default_factory=SandboxConfig)
    dashboard_host: str = "127.0.0.1"
    dashboard_port: int = 8765
    memory_limit_mb: float = 1800.0         # 1.8 GB RAM footprint target
    debug: bool = False


# Global default configuration instance
DEFAULT_CONFIG = SystemConfig()
