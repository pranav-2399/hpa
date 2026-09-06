from typing import Optional, List
from autoscaler.repositories.base_repository import BaseRepository, DatabaseService
from autoscaler.models.recommendation import ScalingAction

class ScalingActionRepository(BaseRepository):
    """Repository for storing ScalingAction entities."""

    def __init__(self, db_service: DatabaseService):
        super().__init__(db_service, "scaling_actions")

    def save(self, entity: ScalingAction) -> ScalingAction:
        query = """
            INSERT INTO scaling_actions (actionId, actionType, previousReplicaCount, newReplicaCount, status, reason, executedAt, executionDuration)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (actionId) DO UPDATE SET
                actionType = EXCLUDED.actionType,
                previousReplicaCount = EXCLUDED.previousReplicaCount,
                newReplicaCount = EXCLUDED.newReplicaCount,
                status = EXCLUDED.status,
                reason = EXCLUDED.reason,
                executedAt = EXCLUDED.executedAt,
                executionDuration = EXCLUDED.executionDuration
        """
        params = (
            entity.actionId, entity.actionType, entity.previousReplicaCount, 
            entity.newReplicaCount, entity.status, entity.reason, 
            entity.executedAt, entity.executionDuration
        )
        self.db_service.executeQuery(query, params)
        self._store[entity.actionId] = entity
        return entity

    def _row_to_entity(self, row: dict) -> ScalingAction:
        return ScalingAction(
            actionId=row.get("actionid", row.get("actionId", "")),
            actionType=row.get("actiontype", row.get("actionType", "")),
            previousReplicaCount=int(row.get("previousreplicacount", row.get("previousReplicaCount", 0))),
            newReplicaCount=int(row.get("newreplicacount", row.get("newReplicaCount", 0))),
            status=row.get("status", ""),
            reason=row.get("reason", ""),
            executedAt=row.get("executedat", row.get("executedAt")),
            executionDuration=float(row.get("executionduration", row.get("executionDuration", 0.0)))
        )

    def findById(self, entity_id: str) -> Optional[ScalingAction]:
        rows = self.db_service.executeQuery(f"SELECT * FROM {self.table_name} WHERE actionId = %s", (entity_id,))
        if rows:
            return self._row_to_entity(rows[0])
        return self._store.get(entity_id)

    def getLatestAction(self) -> Optional[ScalingAction]:
        rows = self.db_service.executeQuery(f"SELECT * FROM {self.table_name} ORDER BY executedAt DESC LIMIT 1")
        if rows:
            return self._row_to_entity(rows[0])
        actions = self.findAll()
        if not actions:
            return None
        return max(actions, key=lambda a: a.executedAt)
