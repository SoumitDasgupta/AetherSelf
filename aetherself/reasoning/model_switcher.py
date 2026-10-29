"""Dynamic local model-switching engine between 1B routine and 3.8B diagnostic tiers."""

import time
from typing import Optional, Callable, List
from pydantic import BaseModel, Field
from ..types import ModelTier
from ..config import ReasoningConfig


class ModelSwitchEvent(BaseModel):
    """Event emitted whenever the system switches SLM execution tiers."""
    timestamp: float = Field(default_factory=time.time)
    from_tier: ModelTier
    to_tier: ModelTier
    reason: str
    anomaly_score: float
    estimated_memory_mb: float
    estimated_power_watts: float


class DynamicModelSwitcher:
    """Orchestrates dynamic model-switching between edge SLM tiers.

    Normal Operational State: Tier 1 (1B Routine model) at minimal power (< 2W, < 500MB RAM).
    Anomaly Escalation: Tier 2 (3.8B Phi-3.5/Llama-3.2 CoT) with contextual RAG (< 8W, < 1.8GB RAM).
    """

    def __init__(self, config: Optional[ReasoningConfig] = None):
        self.config = config or ReasoningConfig()
        self.active_tier: ModelTier = ModelTier.TIER_1_ROUTINE
        self.history: List[ModelSwitchEvent] = []
        self._listeners: List[Callable[[ModelSwitchEvent], None]] = []

    def register_listener(self, callback: Callable[[ModelSwitchEvent], None]) -> None:
        """Register listener for model switch events."""
        self._listeners.append(callback)

    def evaluate_tier(self, anomaly_score: float, is_anomaly: bool, system_cpu_pct: float = 20.0) -> ModelTier:
        """Evaluate whether to stay in Tier 1 or escalate/de-escalate to Tier 2.

        Takes into account anomaly severity, adaptive threshold, and host CPU load.
        """
        target_tier = self.active_tier

        # High CPU spike fallback protection (Risk Mitigation Strategy 13:
        # "Pre-load model weights in RAM; use smaller 1B fallback model for high-CPU spikes")
        if system_cpu_pct > 92.0 and self.active_tier == ModelTier.TIER_2_DIAGNOSTIC:
            target_tier = ModelTier.TIER_1_ROUTINE
            reason = f"High CPU load ({system_cpu_pct:.1f}%) forced Tier 1 fallback to prevent compute starvation"
            self._switch_to(target_tier, reason, anomaly_score)
            return target_tier

        if is_anomaly or anomaly_score >= self.config.escalation_anomaly_score_threshold:
            if self.active_tier != ModelTier.TIER_2_DIAGNOSTIC:
                target_tier = ModelTier.TIER_2_DIAGNOSTIC
                reason = f"Anomaly score ({anomaly_score:.2f}) crossed escalation threshold ({self.config.escalation_anomaly_score_threshold}). Escalating to 3.8B CoT SLM."
                self._switch_to(target_tier, reason, anomaly_score)
        else:
            if self.active_tier != ModelTier.TIER_1_ROUTINE:
                target_tier = ModelTier.TIER_1_ROUTINE
                reason = f"System normalized (anomaly score {anomaly_score:.2f}). De-escalating to low-power 1B routine tier."
                self._switch_to(target_tier, reason, anomaly_score)

        return target_tier

    def force_tier(self, tier: ModelTier, reason: str = "Manual override") -> None:
        """Manually force execution tier."""
        self._switch_to(tier, reason, anomaly_score=0.0)

    def _switch_to(self, target_tier: ModelTier, reason: str, anomaly_score: float) -> None:
        """Execute internal tier switch and notify listeners."""
        prev_tier = self.active_tier
        self.active_tier = target_tier

        # Resource profiles for single-board computers (Raspberry Pi 5 / Jetson)
        if target_tier == ModelTier.TIER_1_ROUTINE:
            mem_mb = 450.0
            power_w = 2.2
        else:
            mem_mb = 1750.0
            power_w = 7.5

        event = ModelSwitchEvent(
            from_tier=prev_tier,
            to_tier=target_tier,
            reason=reason,
            anomaly_score=anomaly_score,
            estimated_memory_mb=mem_mb,
            estimated_power_watts=power_w,
        )
        self.history.append(event)

        for listener in self._listeners:
            try:
                listener(event)
            except Exception:
                pass

    def get_status(self) -> dict:
        """Return current model switcher status."""
        return {
            "active_tier": self.active_tier.value,
            "is_escalated": self.active_tier == ModelTier.TIER_2_DIAGNOSTIC,
            "tier_name": (
                "Tier 2: 3.8B Diagnostic SLM (Phi-3.5-mini CoT)"
                if self.active_tier == ModelTier.TIER_2_DIAGNOSTIC
                else "Tier 1: 1B Routine Classifier (Low Power)"
            ),
            "estimated_memory_mb": 1750.0 if self.active_tier == ModelTier.TIER_2_DIAGNOSTIC else 450.0,
            "estimated_power_w": 7.5 if self.active_tier == ModelTier.TIER_2_DIAGNOSTIC else 2.2,
            "recent_switches": [e.model_dump() for e in self.history[-5:]],
        }
