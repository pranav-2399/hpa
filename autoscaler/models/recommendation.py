from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

# Possible Scaling Actions
ACTION_SCALE_UP = "SCALE_UP"
ACTION_SCALE_DOWN = "SCALE_DOWN"
ACTION_MAINTAIN = "MAINTAIN"

@dataclass
class ScalingRecommendation:
    recommendationId: str
    recommendedAction: str          # SCALE_UP | SCALE_DOWN | MAINTAIN
    recommendedReplicaCount: int
    reason: str
    priority: str                   # HIGH | MEDIUM | LOW
    createdAt: datetime = field(default_factory=datetime.utcnow)

    def validateRecommendation(self, min_replicas: int = 1, max_replicas: int = 10) -> bool:
        """Validates action enum and bounds limits."""
        if self.recommendedAction not in (ACTION_SCALE_UP, ACTION_SCALE_DOWN, ACTION_MAINTAIN):
            return False
        if self.recommendedReplicaCount < min_replicas or self.recommendedReplicaCount > max_replicas:
            return False
        return True

    def getRecommendationSummary(self) -> Dict[str, Any]:
        return {
            "recommendationId": self.recommendationId,
            "action": self.recommendedAction,
            "targetReplicas": self.recommendedReplicaCount,
            "priority": self.priority,
            "reason": self.reason,
            "createdAt": self.createdAt.isoformat()
        }


@dataclass
class ScalingAction:
    actionId: str
    actionType: str                 # SCALE_UP | SCALE_DOWN | MAINTAIN
    previousReplicaCount: int
    newReplicaCount: int
    status: str                     # PENDING | IN_PROGRESS | SUCCESS | FAILED | ROLLED_BACK
    reason: str
    executedAt: datetime = field(default_factory=datetime.utcnow)
    executionDuration: float = 0.0  # Duration in seconds

    def execute(self) -> None:
        """Marks action as IN_PROGRESS."""
        self.status = "IN_PROGRESS"
        self.executedAt = datetime.utcnow()

    def markSuccessful(self, duration_seconds: float) -> None:
        """Marks action execution as SUCCESS."""
        self.status = "SUCCESS"
        self.executionDuration = round(duration_seconds, 3)

    def markFailed(self, reason: str) -> None:
        """Marks action execution as FAILED."""
        self.status = "FAILED"
        self.reason = f"{self.reason} | Error: {reason}"

    def rollback(self) -> Dict[str, Any]:
        """Triggers rollback payload info."""
        self.status = "ROLLED_BACK"
        return {
            "actionId": self.actionId,
            "status": self.status,
            "revertedToReplicaCount": self.previousReplicaCount
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "actionId": self.actionId,
            "actionType": self.actionType,
            "previousReplicaCount": self.previousReplicaCount,
            "newReplicaCount": self.newReplicaCount,
            "status": self.status,
            "reason": self.reason,
            "executedAt": self.executedAt.isoformat(),
            "executionDuration": self.executionDuration
        }
