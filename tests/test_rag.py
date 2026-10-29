"""Unit tests for Contextual Vector RAG Core."""

import time
import pytest
from aetherself.rag import ContextualVectorRAG, QuantizedNomicEmbedding, FreshnessDecayScorer
from aetherself.types import HistoricalIncident, SafetyPrimitive


def test_quantized_nomic_embeddings():
    embedder = QuantizedNomicEmbedding(dimension=768)
    vec = embedder.embed_text("High memory leak in transaction processing service")
    assert vec.shape == (768,)
    # Norm should be approximately 1.0
    import numpy as np
    norm = np.linalg.norm(vec)
    assert 0.95 <= norm <= 1.05


def test_freshness_decay_scoring():
    scorer = FreshnessDecayScorer(half_life_days=7.0)
    now = time.time()
    # Brand new incident -> decay factor near 1.0
    decay_recent = scorer.compute_decay_factor(now)
    assert 0.98 <= decay_recent <= 1.0

    # Old incident (14 days ago) -> decay factor lower
    two_weeks_ago = now - (14 * 86400)
    decay_old = scorer.compute_decay_factor(two_weeks_ago)
    assert decay_old < decay_recent
    assert decay_old >= 0.60  # Minimum floor


def test_vector_rag_retrieval_and_closed_loop_storage(tmp_path):
    from aetherself.config import RAGConfig
    cfg = RAGConfig(persist_directory=str(tmp_path / "rag_test"))
    rag = ContextualVectorRAG(cfg)

    # Retrieval over seed incidents
    results = rag.retrieve("memory leak unbounded heap", top_k=3)
    assert len(results) >= 1
    assert results[0].incident.target_service == "payment-gateway"
    assert results[0].incident.recommended_action == SafetyPrimitive.RESTART_SERVICE

    # Closed-loop indexing test
    from aetherself.types import TelemetrySnapshot
    snap = TelemetrySnapshot(
        cpu_percent=20.0,
        memory_percent=30.0,
        memory_mb=400.0,
        disk_percent=20.0,
        ipc_latency_ms=2.0,
        thread_count=10,
        open_file_handles=20,
        queue_backlog=0,
        error_log_rate=0.0,
    )
    new_inc = rag.record_successful_resolution(
        title="Custom Test Incident",
        symptoms="Test symptoms",
        telemetry=snap,
        root_cause="Test root cause",
        action=SafetyPrimitive.FLUSH_CACHE,
        target_service="test-service",
        action_params={"key": "val"},
        resolution_time_s=1.5,
    )

    # Verify newly added incident is retrievable
    res2 = rag.retrieve("Test root cause", top_k=1)
    assert res2[0].incident.incident_id == new_inc.incident_id
