"""Pre-action state checkpointing and atomic rollback engine."""

import time
import copy
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from ..types import SafetyPrimitive, ServiceHealth


class ServiceCheckpoint(BaseModel):
    """Snapshot of a service state prior to remediation."""
    checkpoint_id: str
    target_service: str
    timestamp: float = Field(default_factory=time.time)
    service_health: ServiceHealth
    config_state: Dict[str, Any] = Field(default_factory=dict)
    resource_limits: Dict[str, Any] = Field(default_factory=dict)
    worker_threads: int = 4
    queue_state: Dict[str, Any] = Field(default_factory=dict)
    action_intended: SafetyPrimitive
    rollback_primitive: SafetyPrimitive
    rollback_parameters: Dict[str, Any] = Field(default_factory=dict)


class StateCheckpointManager:
    """Manages pre-action checkpoints and executes atomic rollbacks."""

    def __init__(self):
        self._checkpoints: Dict[str, ServiceCheckpoint] = {}

    def capture_checkpoint(
        self,
        target_service: str,
        current_health: ServiceHealth,
        config_state: Dict[str, Any],
        worker_threads: int,
        action_intended: SafetyPrimitive,
        rollback_primitive: SafetyPrimitive,
        rollback_parameters: Dict[str, Any],
        resource_limits: Optional[Dict[str, Any]] = None,
    ) -> ServiceCheckpoint:
        """Capture an atomic pre-action checkpoint."""
        cid = f"CHK-{int(time.time()*1000)}-{target_service}"
        checkpoint = ServiceCheckpoint(
            checkpoint_id=cid,
            target_service=target_service,
            service_health=current_health,
            config_state=copy.deepcopy(config_state),
            resource_limits=copy.deepcopy(resource_limits or {}),
            worker_threads=worker_threads,
            action_intended=action_intended,
            rollback_primitive=rollback_primitive,
            rollback_parameters=copy.deepcopy(rollback_parameters),
        )
        self._checkpoints[cid] = checkpoint
        return checkpoint

    def get_checkpoint(self, checkpoint_id: str) -> Optional[ServiceCheckpoint]:
        """Retrieve stored checkpoint by ID."""
        return self._checkpoints.get(checkpoint_id)

    def discard_checkpoint(self, checkpoint_id: str) -> None:
        """Discard checkpoint after successful verified resolution."""
        self._checkpoints.pop(checkpoint_id, None)
