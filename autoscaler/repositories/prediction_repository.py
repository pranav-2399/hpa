from typing import Optional, List
from autoscaler.repositories.base_repository import BaseRepository, DatabaseService
from autoscaler.models.prediction import TrafficPrediction

class PredictionRepository(BaseRepository):
    """Repository for storing and querying TrafficPrediction entities."""

    def __init__(self, db_service: DatabaseService):
        super().__init__(db_service, "traffic_predictions")

    def save(self, entity: TrafficPrediction) -> TrafficPrediction:
        query = """
            INSERT INTO traffic_predictions (predictionId, predictedTraffic, currentTraffic, predictionWindow, confidence, modelUsed, createdAt)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (predictionId) DO UPDATE SET
                predictedTraffic = EXCLUDED.predictedTraffic,
                currentTraffic = EXCLUDED.currentTraffic,
                predictionWindow = EXCLUDED.predictionWindow,
                confidence = EXCLUDED.confidence,
                modelUsed = EXCLUDED.modelUsed,
                createdAt = EXCLUDED.createdAt
        """
        params = (
            entity.predictionId, entity.predictedTraffic, entity.currentTraffic, 
            entity.predictionWindow, entity.confidence, entity.modelUsed, entity.createdAt
        )
        self.db_service.executeQuery(query, params)
        self._store[entity.predictionId] = entity
        return entity

    def _row_to_entity(self, row: dict) -> TrafficPrediction:
        return TrafficPrediction(
            predictionId=row.get("predictionid", row.get("predictionId", "")),
            predictedTraffic=float(row.get("predictedtraffic", row.get("predictedTraffic", 0.0))),
            currentTraffic=float(row.get("currenttraffic", row.get("currentTraffic", 0.0))),
            predictionWindow=int(row.get("predictionwindow", row.get("predictionWindow", 0))),
            confidence=float(row.get("confidence", 0.0)),
            modelUsed=row.get("modelused", row.get("modelUsed", "")),
            createdAt=row.get("createdat", row.get("createdAt"))
        )

    def findById(self, entity_id: str) -> Optional[TrafficPrediction]:
        rows = self.db_service.executeQuery(f"SELECT * FROM {self.table_name} WHERE predictionId = %s", (entity_id,))
        if rows:
            return self._row_to_entity(rows[0])
        return self._store.get(entity_id)

    def getLatestPrediction(self) -> Optional[TrafficPrediction]:
        rows = self.db_service.executeQuery(f"SELECT * FROM {self.table_name} ORDER BY createdAt DESC LIMIT 1")
        if rows:
            return self._row_to_entity(rows[0])
        # Fallback
        all_preds = self.findAll()
        if not all_preds:
            return None
        return max(all_preds, key=lambda p: p.createdAt)
