from typing import Optional, List
from autoscaler.repositories.base_repository import BaseRepository, DatabaseService
from autoscaler.models.prediction import TrafficPrediction

class PredictionRepository(BaseRepository):
    """Repository for storing and querying TrafficPrediction entities."""

    def __init__(self, db_service: DatabaseService):
        super().__init__(db_service, "traffic_predictions")

    def save(self, entity: TrafficPrediction) -> TrafficPrediction:
        self._store[entity.predictionId] = entity
        return entity

    def findById(self, entity_id: str) -> Optional[TrafficPrediction]:
        return self._store.get(entity_id)

    def getLatestPrediction(self) -> Optional[TrafficPrediction]:
        all_preds = self.findAll()
        if not all_preds:
            return None
        return max(all_preds, key=lambda p: p.createdAt)
