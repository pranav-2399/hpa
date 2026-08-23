import uuid
import logging
from typing import Dict, Any, List
from datetime import datetime
from autoscaler.models.prediction import TrafficPrediction
from autoscaler.models.metrics import MetricSnapshot
from autoscaler.services.prometheus_service import PrometheusService

logger = logging.getLogger("autoscaler.prediction")

class PredictionService:
    """Predicts future workload traffic using historical metric trend forecasting."""

    def __init__(self, prometheusService: PrometheusService, predictionWindow: int = 15):
        self.prometheusService = prometheusService
        self.predictionModel = "Linear-Trend-Predictor"
        self.predictionWindow = predictionWindow

    def fetchHistoricalMetrics(self, snapshots: List[MetricSnapshot]) -> List[float]:
        """Extracts request rate time-series sequence from snapshots."""
        return [s.requestRate for s in snapshots]

    def prepareTrafficData(self, historical_rps: List[float]) -> Dict[str, Any]:
        """Prepares traffic statistical features."""
        if not historical_rps:
            return {"meanRps": 100.0, "trendSlope": 0.0}
        mean_rps = sum(historical_rps) / len(historical_rps)
        if len(historical_rps) >= 2:
            trend_slope = (historical_rps[-1] - historical_rps[0]) / len(historical_rps)
        else:
            trend_slope = 0.0
        return {"meanRps": mean_rps, "trendSlope": trend_slope}

    def predictTraffic(self, current_snapshot: MetricSnapshot, history: List[MetricSnapshot]) -> float:
        """Projects traffic RPS for the prediction window horizon."""
        historical_rps = self.fetchHistoricalMetrics(history)
        traffic_data = self.prepareTrafficData(historical_rps)
        
        current_rps = current_snapshot.requestRate
        projected_growth = traffic_data["trendSlope"] * self.predictionWindow
        predicted_rps = max(0.0, current_rps + projected_growth)
        return round(predicted_rps, 2)

    def generatePrediction(self, current_snapshot: MetricSnapshot, history: List[MetricSnapshot]) -> TrafficPrediction:
        """Produces a TrafficPrediction domain object."""
        predicted_traffic = self.predictTraffic(current_snapshot, history)
        confidence = 0.88 if len(history) >= 5 else 0.70
        
        prediction = TrafficPrediction(
            predictionId=f"pred-{uuid.uuid4().hex[:8]}",
            predictedTraffic=predicted_traffic,
            currentTraffic=current_snapshot.requestRate,
            predictionWindow=self.predictionWindow,
            confidence=confidence,
            modelUsed=self.predictionModel,
            createdAt=datetime.utcnow()
        )
        logger.info(f"Generated prediction: {prediction.predictedTraffic} RPS (Current: {prediction.currentTraffic} RPS, Confidence: {prediction.confidence})")
        return prediction
