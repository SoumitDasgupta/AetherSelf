"""Context freshness decay scoring algorithm to prevent stale RAG retrieval."""

import math
import time
from typing import Dict, Any


class FreshnessDecayScorer:
    """Calculates time-decay factor for historical incident traces.

    Mitigates stale context risk by prioritizing recent, verified resolutions
    while maintaining foundational failure mode knowledge.
    """

    def __init__(self, half_life_days: float = 7.0):
        self.half_life_seconds = half_life_days * 86400.0
        self.decay_constant = math.log(2.0) / self.half_life_seconds

    def compute_decay_factor(self, incident_timestamp: float, current_time: float = None) -> float:
        """Compute freshness factor in (0.0, 1.0].

        factor = exp(- lambda * dt)
        """
        now = current_time or time.time()
        dt = max(0.0, now - incident_timestamp)
        # Bounded decay: minimum floor of 0.60 so foundational fixes are never eliminated
        raw_decay = math.exp(-self.decay_constant * dt)
        return float(max(0.60, min(1.0, raw_decay)))

    def rank_score(
        self,
        vector_similarity: float,
        incident_timestamp: float,
        verified_count: int = 1,
        current_time: float = None,
    ) -> float:
        """Calculate composite rank score.

        Combines raw vector similarity, time freshness, and historical verification count.
        """
        freshness = self.compute_decay_factor(incident_timestamp, current_time)
        # Slight boost for repeatedly verified fixes (up to +10%)
        verification_boost = 1.0 + min(0.10, 0.02 * (verified_count - 1))
        # Weight similarity 75%, freshness 25%
        composite = (vector_similarity * 0.75 + (vector_similarity * freshness) * 0.25) * verification_boost
        return round(float(composite), 4)
