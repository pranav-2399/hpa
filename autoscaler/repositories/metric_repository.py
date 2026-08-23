from typing import Optional, List
from datetime import datetime
from autoscaler.repositories.base_repository import BaseRepository, DatabaseService
from autoscaler.models.metrics import MetricSnapshot

class MetricRepository(BaseRepository):
    """Repository for persisting and querying MetricSnapshot entities."""

    def __init__(self, db_service: DatabaseService):
        super().__init__(db_service, "metric_snapshots")

    def save(self, entity: MetricSnapshot) -> MetricSnapshot:
        entity.validateMetrics()
        self._store[entity.metricId] = entity
        return entity

    def findById(self, entity_id: str) -> Optional[MetricSnapshot]:
        return self._store.get(entity_id)

    def getLatestSnapshot(self, cluster_id: str) -> Optional[MetricSnapshot]:
        snapshots = self.findByCluster(cluster_id)
        if not snapshots:
            return None
        return max(snapshots, key=lambda s: s.timestamp)

    def getRecentSnapshots(self, cluster_id: str, limit: int = 10) -> List[MetricSnapshot]:
        snapshots = self.findByCluster(cluster_id)
        sorted_snaps = sorted(snapshots, key=lambda s: s.timestamp, reverse=True)
        return sorted_snaps[:limit]
