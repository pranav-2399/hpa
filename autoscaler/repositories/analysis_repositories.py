from typing import Optional, List
from autoscaler.repositories.base_repository import BaseRepository, DatabaseService
from autoscaler.models.analysis import ResourceAnalysis, CostAnalysis

class ResourceAnalysisRepository(BaseRepository):
    """Repository for storing ResourceAnalysis entities."""

    def __init__(self, db_service: DatabaseService):
        super().__init__(db_service, "resource_analyses")

    def save(self, entity: ResourceAnalysis) -> ResourceAnalysis:
        self._store[entity.analysisId] = entity
        return entity

    def findById(self, entity_id: str) -> Optional[ResourceAnalysis]:
        return self._store.get(entity_id)

    def getLatestAnalysis(self) -> Optional[ResourceAnalysis]:
        all_items = self.findAll()
        if not all_items:
            return None
        return max(all_items, key=lambda a: a.analysisTime)


class CostAnalysisRepository(BaseRepository):
    """Repository for storing CostAnalysis entities."""

    def __init__(self, db_service: DatabaseService):
        super().__init__(db_service, "cost_analyses")

    def save(self, entity: CostAnalysis) -> CostAnalysis:
        self._store[entity.analysisId] = entity
        return entity

    def findById(self, entity_id: str) -> Optional[CostAnalysis]:
        return self._store.get(entity_id)

    def getLatestAnalysis(self) -> Optional[CostAnalysis]:
        all_items = self.findAll()
        if not all_items:
            return None
        return max(all_items, key=lambda a: a.analysisTime)
