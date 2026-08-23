from typing import Optional, List
from autoscaler.repositories.base_repository import BaseRepository, DatabaseService
from autoscaler.models.recommendation import ScalingAction

class ScalingActionRepository(BaseRepository):
    """Repository for storing ScalingAction entities."""

    def __init__(self, db_service: DatabaseService):
        super().__init__(db_service, "scaling_actions")

    def save(self, entity: ScalingAction) -> ScalingAction:
        self._store[entity.actionId] = entity
        return entity

    def findById(self, entity_id: str) -> Optional[ScalingAction]:
        return self._store.get(entity_id)

    def getLatestAction(self) -> Optional[ScalingAction]:
        actions = self.findAll()
        if not actions:
            return None
        return max(actions, key=lambda a: a.executedAt)
