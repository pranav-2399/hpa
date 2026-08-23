from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, Any

@dataclass
class TrafficPrediction:
    predictionId: str
    predictedTraffic: float      # Projected RPS or load factor
    currentTraffic: float        # Baseline current RPS
    predictionWindow: int        # Prediction window horizon in minutes
    confidence: float            # Confidence score (0.0 to 1.0)
    modelUsed: str               # Model identifier (e.g. "LinearRegression", "ARIMA", "LLM-Forecast")
    createdAt: datetime = field(default_factory=datetime.utcnow)

    def getPredictedTraffic(self) -> float:
        return self.predictedTraffic

    def getConfidence(self) -> float:
        return self.confidence

    def isTrafficIncreaseExpected(self, percentage_threshold: float = 15.0) -> bool:
        """Checks if predicted traffic exceeds current traffic by threshold percentage."""
        if self.currentTraffic <= 0:
            return self.predictedTraffic > 0
        diff_percent = ((self.predictedTraffic - self.currentTraffic) / self.currentTraffic) * 100.0
        return diff_percent >= percentage_threshold

    def isTrafficDecreaseExpected(self, percentage_threshold: float = 15.0) -> bool:
        """Checks if predicted traffic falls below current traffic by threshold percentage."""
        if self.currentTraffic <= 0:
            return False
        diff_percent = ((self.currentTraffic - self.predictedTraffic) / self.currentTraffic) * 100.0
        return diff_percent >= percentage_threshold

    def to_dict(self) -> Dict[str, Any]:
        return {
            "predictionId": self.predictionId,
            "predictedTraffic": self.predictedTraffic,
            "currentTraffic": self.currentTraffic,
            "predictionWindow": self.predictionWindow,
            "confidence": self.confidence,
            "modelUsed": self.modelUsed,
            "createdAt": self.createdAt.isoformat()
        }
