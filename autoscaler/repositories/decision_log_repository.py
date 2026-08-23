from typing import Optional, List
from autoscaler.repositories.base_repository import BaseRepository, DatabaseService
from autoscaler.models.decision_log import DecisionLog

class DecisionLogRepository(BaseRepository):
    """Repository for storing and auditing AI DecisionLog entities."""

    def __init__(self, db_service: DatabaseService):
        super().__init__(db_service, "decision_logs")

    def save(self, entity: DecisionLog) -> DecisionLog:
        self._store[entity.decisionId] = entity
        return entity

    def findById(self, entity_id: str) -> Optional[DecisionLog]:
        return self._store.get(entity_id)

    def getRecentLogs(self, limit: int = 20) -> List[DecisionLog]:
        logs = self.findAll()
        sorted_logs = sorted(logs, key=lambda d: d.decisionTime, reverse=True)
        return sorted_logs[:limit]
