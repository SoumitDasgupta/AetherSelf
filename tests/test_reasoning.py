"""Unit tests for the Agentic Reasoning Engine & Safety Guardrails."""

import pytest
from aetherself.types import ModelTier, SafetyPrimitive, TelemetrySnapshot
from aetherself.reasoning import DynamicModelSwitcher, ChainOfThoughtEngine, DiagnosticContext, ActionPlanOutput
from aetherself.rag import ContextualVectorRAG


def test_dynamic_model_switcher_escalation_and_deescalation():
    switcher = DynamicModelSwitcher()
    assert switcher.active_tier == ModelTier.TIER_1_ROUTINE

    # Anomaly triggers escalation to Tier 2
    tier = switcher.evaluate_tier(anomaly_score=0.85, is_anomaly=True, system_cpu_pct=25.0)
    assert tier == ModelTier.TIER_2_DIAGNOSTIC
    assert switcher.active_tier == ModelTier.TIER_2_DIAGNOSTIC

    # High CPU fallback to Tier 1 to protect edge compute resources
    tier_fallback = switcher.evaluate_tier(anomaly_score=0.85, is_anomaly=True, system_cpu_pct=96.0)
    assert tier_fallback == ModelTier.TIER_1_ROUTINE

    # Normalization returns to Tier 1
    tier_norm = switcher.evaluate_tier(anomaly_score=0.10, is_anomaly=False, system_cpu_pct=20.0)
    assert tier_norm == ModelTier.TIER_1_ROUTINE


def test_cot_engine_diagnostic_synthesis():
    rag = ContextualVectorRAG()
    cot = ChainOfThoughtEngine()

    snap = TelemetrySnapshot(
        cpu_percent=30.0,
        memory_percent=88.0,
        memory_mb=1750.0,
        disk_percent=40.0,
        ipc_latency_ms=45.0,
        thread_count=22,
        open_file_handles=60,
        queue_backlog=15,
        error_log_rate=2.0,
    )
    matches = rag.retrieve("Memory leak in payment gateway", top_k=3)
    ctx = DiagnosticContext(
        telemetry=snap,
        deviant_summary="memory_percent=88.0% (sigma=+4.2)",
        rag_matches=matches,
        active_tier=ModelTier.TIER_2_DIAGNOSTIC,
    )

    plan = cot.synthesize(ctx)
    assert plan.target_service == "payment-gateway"
    assert plan.action == SafetyPrimitive.RESTART_SERVICE
    assert plan.confidence >= 0.90
    assert len(plan.chain_of_thought) >= 4
    assert plan.synthesis_latency_s < 2.5


def test_pydantic_schema_blocks_shell_injection():
    # Attempting to pass shell commands should be rejected by Pydantic validator
    with pytest.raises(ValueError, match="Potential shell injection token detected"):
        ActionPlanOutput(
            root_cause_diagnosis="Malicious attack",
            confidence=0.9,
            target_service="test",
            action=SafetyPrimitive.RESTART_SERVICE,
            parameters={"cmd": "rm -rf / && reboot"},
        )
