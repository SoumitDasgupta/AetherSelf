"""Safety guardrails, command whitelist enforcer, and anti-flapping monitor."""

import time
from collections import defaultdict, deque
from typing import Dict, Deque, Tuple, Optional
from ..types import SafetyPrimitive
from ..config import SandboxConfig


class SafetyGuardrailError(Exception):
    """Raised when an action or parameter violates safety boundaries."""
    pass


class AntiFlappingGuard:
    """Prevents cyclic oscillating restarts and infinite action loops.

    Implements exponential backoff and max-retry limits (3 attempts before alerting human)
    as specified in Risk Mitigation Strategy 13.
    """

    def __init__(self, config: Optional[SandboxConfig] = None):
        self.config = config or SandboxConfig()
        # Track action execution timestamps per service: target_service -> deque of timestamps
        self.action_timestamps: Dict[str, Deque[float]] = defaultdict(
            lambda: deque(maxlen=self.config.max_flapping_triggers * 2)
        )
        # Track consecutive retry counts per target service
        self.retry_counts: Dict[str, int] = defaultdict(int)

    def verify_action_allowed(self, action: SafetyPrimitive, target_service: str) -> Tuple[bool, Optional[str]]:
        """Verify action does not violate whitelist or anti-flapping limits."""
        # 1. Strict whitelist check
        if not isinstance(action, SafetyPrimitive):
            raise SafetyGuardrailError(f"Action '{action}' is not in approved safety primitives whitelist.")

        now = time.time()
        # 2. Check retry count ceiling (max 3 attempts)
        retries = self.retry_counts[target_service]
        if retries >= self.config.max_retries:
            return False, (
                f"Max retry limit ({self.config.max_retries}) reached for service '{target_service}'. "
                f"Halting autonomous loop and escalating to human operator."
            )

        # 3. Flapping oscillation detection (e.g. 4+ executions within 60s)
        history = self.action_timestamps[target_service]
        recent_triggers = [t for t in history if (now - t) <= self.config.flapping_window_s]
        if len(recent_triggers) >= self.config.max_flapping_triggers:
            return False, (
                f"Action flapping detected on '{target_service}': {len(recent_triggers)} actions "
                f"within {self.config.flapping_window_s}s. Halting autonomous cycle to prevent system thrashing."
            )

        return True, None

    def get_backoff_delay_s(self, target_service: str) -> float:
        """Calculate exponential backoff delay before executing retry."""
        attempt = self.retry_counts[target_service]
        if attempt <= 0:
            return 0.0
        # 1s, 2s, 4s backoff
        return self.config.exponential_backoff_base_s * (2 ** (attempt - 1))

    def record_action_attempt(self, target_service: str) -> None:
        """Record an action attempt."""
        now = time.time()
        self.action_timestamps[target_service].append(now)
        self.retry_counts[target_service] += 1

    def record_action_success(self, target_service: str) -> None:
        """Reset retry count on verified successful recovery."""
        self.retry_counts[target_service] = 0

    def reset_service(self, target_service: str) -> None:
        """Manually reset guardrail tracking for a service."""
        self.retry_counts[target_service] = 0
        self.action_timestamps[target_service].clear()
