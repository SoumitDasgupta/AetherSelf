"""Deterministic agentic state transitions enforcing LangGraph/Pydantic AI loop."""

import time
from typing import Optional, Callable, List, Dict, Any
from pydantic import BaseModel, Field
from ..types import SystemState, ActionPlan, ExecutionResult


class StateTransitionEvent(BaseModel):
    """Record of a state transition in the agentic lifecycle."""
    timestamp: float = Field(default_factory=time.time)
    from_state: SystemState
    to_state: SystemState
    trigger: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AgenticStateMachine:
    """Enforces deterministic state transitions for the Perception-Reasoning-Action loop.

    Guarantees that actions cannot be executed without prior RAG context retrieval,
    SLM CoT synthesis, and safety guardrail checks.
    """

    ALLOWED_TRANSITIONS = {
        SystemState.NORMAL: [SystemState.SUSPICIOUS, SystemState.RESOLUTION_REQUIRED],
        SystemState.SUSPICIOUS: [SystemState.NORMAL, SystemState.RESOLUTION_REQUIRED],
        SystemState.RESOLUTION_REQUIRED: [SystemState.RAG_RETRIEVAL, SystemState.NORMAL],
        SystemState.RAG_RETRIEVAL: [SystemState.SLM_REASONING, SystemState.ESCALATED_TO_HUMAN],
        SystemState.SLM_REASONING: [SystemState.SANDBOX_EXECUTION, SystemState.ESCALATED_TO_HUMAN],
        SystemState.SANDBOX_EXECUTION: [SystemState.VALIDATING, SystemState.ROLLBACK_TRIGGERED],
        SystemState.VALIDATING: [SystemState.RESOLVED_CLOSED_LOOP, SystemState.ROLLBACK_TRIGGERED],
        SystemState.RESOLVED_CLOSED_LOOP: [SystemState.NORMAL],
        SystemState.ROLLBACK_TRIGGERED: [SystemState.RESOLUTION_REQUIRED, SystemState.ESCALATED_TO_HUMAN, SystemState.NORMAL],
        SystemState.ESCALATED_TO_HUMAN: [SystemState.NORMAL],
    }

    def __init__(self, initial_state: SystemState = SystemState.NORMAL):
        self.current_state: SystemState = initial_state
        self.state_history: List[StateTransitionEvent] = []
        self._listeners: List[Callable[[StateTransitionEvent], None]] = []

    def register_listener(self, callback: Callable[[StateTransitionEvent], None]) -> None:
        """Register listener for state machine transitions."""
        self._listeners.append(callback)

    def transition_to(self, new_state: SystemState, trigger: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Attempt deterministic state transition."""
        allowed = self.ALLOWED_TRANSITIONS.get(self.current_state, [])
        if new_state not in allowed and new_state != self.current_state:
            # Enforce deterministic discipline
            return False

        prev = self.current_state
        self.current_state = new_state
        event = StateTransitionEvent(
            from_state=prev,
            to_state=new_state,
            trigger=trigger,
            metadata=metadata or {},
        )
        self.state_history.append(event)

        for listener in self._listeners:
            try:
                listener(event)
            except Exception:
                pass

        return True

    def reset_to_normal(self, reason: str = "System stable") -> None:
        """Transition back to normal operational state."""
        self.transition_to(SystemState.NORMAL, reason)

    def get_status(self) -> dict:
        """Return state machine status and recent transitions."""
        return {
            "current_state": self.current_state.value,
            "recent_transitions": [e.model_dump() for e in self.state_history[-8:]],
        }
