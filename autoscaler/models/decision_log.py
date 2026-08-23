from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

@dataclass
class DecisionLog:
    decisionId: str
    inputSummary: Dict[str, Any]    # JSON input given to LLM / Decision engine
    decision: str                   # Chosen action/recommendation
    reasoning: str                  # AI reasoning / chain of thought
    confidence: float               # Confidence score (0.0 to 1.0)
    actionId: Optional[str] = None  # Reference to executed ScalingAction ID if any
    decisionTime: datetime = field(default_factory=datetime.utcnow)

    def recordDecision(self, action_id: Optional[str] = None) -> None:
        """Records final action relationship and updates decision timestamp."""
        self.actionId = action_id
        self.decisionTime = datetime.utcnow()

    def getDecisionDetails(self) -> Dict[str, Any]:
        return {
            "decisionId": self.decisionId,
            "decisionTime": self.decisionTime.isoformat(),
            "inputSummary": self.inputSummary,
            "decision": self.decision,
            "reasoning": self.reasoning,
            "confidence": self.confidence,
            "actionId": self.actionId
        }

    def to_dict(self) -> Dict[str, Any]:
        return self.getDecisionDetails()
