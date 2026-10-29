"""Strict Pydantic JSON schemas and guardrail validators for reasoning outputs."""

from pydantic import BaseModel, Field, field_validator
from typing import Dict, Any, List, Optional
from ..types import SafetyPrimitive, ModelTier, TelemetrySnapshot, RAGRetrievalResult


class DiagnosticContext(BaseModel):
    """Input payload fed into the diagnostic reasoning engine."""
    telemetry: TelemetrySnapshot
    deviant_summary: str
    rag_matches: List[RAGRetrievalResult]
    active_tier: ModelTier
    system_load_factor: float = 1.0


class ActionPlanOutput(BaseModel):
    """Deterministic Pydantic output schema produced by the SLM.

    Strictly validated to prevent hallucinated shell commands or dangerous operations.
    """
    root_cause_diagnosis: str = Field(
        ...,
        description="Concise diagnostic deduction of the underlying fault mechanism."
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score in diagnostic hypothesis."
    )
    target_service: str = Field(
        ...,
        description="Exact microservice name targeted for self-healing remediation."
    )
    action: SafetyPrimitive = Field(
        ...,
        description="Pre-approved deterministic safety primitive. Free-form commands blocked."
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Validated parameters specific to the safety primitive."
    )
    chain_of_thought: List[str] = Field(
        default_factory=list,
        description="Step-by-step diagnostic reasoning trace."
    )
    rollback_action: SafetyPrimitive = Field(
        default=SafetyPrimitive.RESTART_SERVICE,
        description="Compensating action if post-remediation validation fails."
    )
    rollback_parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters for rollback primitive."
    )
    expected_normalization_window_s: float = Field(
        default=3.0,
        ge=0.5,
        le=15.0,
        description="Time window in seconds to observe metric normalization."
    )

    @field_validator("action", "rollback_action")
    @classmethod
    def validate_safety_primitive(cls, v: SafetyPrimitive) -> SafetyPrimitive:
        """Enforce whitelist check against pre-approved safety primitives."""
        if not isinstance(v, SafetyPrimitive):
            raise ValueError(f"Action '{v}' violates safety guardrail. Must be an approved SafetyPrimitive enum.")
        return v

    @field_validator("parameters")
    @classmethod
    def block_shell_injection(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """Guard against shell injection patterns inside parameters."""
        disallowed_tokens = [";", "&&", "||", "`", "$(", "|", "rm -rf", "sudo", "/bin/sh", "/bin/bash"]
        for key, val in v.items():
            if isinstance(val, str):
                for token in disallowed_tokens:
                    if token in val:
                        raise ValueError(f"Potential shell injection token detected in parameter '{key}': '{val}'")
        return v
