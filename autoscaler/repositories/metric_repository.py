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
        query = """
            INSERT INTO metric_snapshots (metricId, timestamp, cpuUsage, memoryUsage, requestRate, responseTime, activePods, clusterId)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (metricId) DO UPDATE SET
                timestamp = EXCLUDED.timestamp,
                cpuUsage = EXCLUDED.cpuUsage,
                memoryUsage = EXCLUDED.memoryUsage,
                requestRate = EXCLUDED.requestRate,
                responseTime = EXCLUDED.responseTime,
                activePods = EXCLUDED.activePods,
                clusterId = EXCLUDED.clusterId
        """
        params = (
            entity.metricId, entity.timestamp, entity.cpuUsage, entity.memoryUsage,
            entity.requestRate, entity.responseTime, entity.activePods, entity.clusterId
        )
        self.db_service.executeQuery(query, params)
        # Still update in-memory store for fallback if DB fails
        self._store[entity.metricId] = entity
        return entity

    def _row_to_entity(self, row: dict) -> MetricSnapshot:
        # Postgres lowercases unquoted identifiers
        return MetricSnapshot(
            metricId=row.get("metricid") or row.get("metricId", ""),
            timestamp=row.get("timestamp"),
            cpuUsage=float(row.get("cpuusage", row.get("cpuUsage", 0.0))),
            memoryUsage=float(row.get("memoryusage", row.get("memoryUsage", 0.0))),
            requestRate=float(row.get("requestrate", row.get("requestRate", 0.0))),
            responseTime=float(row.get("responsetime", row.get("responseTime", 0.0))),
            activePods=int(row.get("activepods", row.get("activePods", 0))),
            clusterId=row.get("clusterid", row.get("clusterId", ""))
        )

    def findById(self, entity_id: str) -> Optional[MetricSnapshot]:
        rows = self.db_service.executeQuery(f"SELECT * FROM {self.table_name} WHERE metricId = %s", (entity_id,))
        if rows:
            return self._row_to_entity(rows[0])
        return self._store.get(entity_id)

    def getLatestSnapshot(self, cluster_id: str) -> Optional[MetricSnapshot]:
        rows = self.db_service.executeQuery(
            f"SELECT * FROM {self.table_name} WHERE clusterId = %s ORDER BY timestamp DESC LIMIT 1",
            (cluster_id,)
        )
        if rows:
            return self._row_to_entity(rows[0])
        return super().getLatestSnapshot(cluster_id) if hasattr(super(), 'getLatestSnapshot') else self._fallback_latest(cluster_id)

    def getRecentSnapshots(self, cluster_id: str, limit: int = 10) -> List[MetricSnapshot]:
        rows = self.db_service.executeQuery(
            f"SELECT * FROM {self.table_name} WHERE clusterId = %s ORDER BY timestamp DESC LIMIT %s",
            (cluster_id, limit)
        )
        if rows or self.db_service.is_connected and "postgresql" in self.db_service.db_url:
            return [self._row_to_entity(r) for r in rows]
        # Fallback
        snapshots = self.findByCluster(cluster_id)
        sorted_snaps = sorted(snapshots, key=lambda s: s.timestamp, reverse=True)
        return sorted_snaps[:limit]

    def _fallback_latest(self, cluster_id: str) -> Optional[MetricSnapshot]:
        snapshots = self.findByCluster(cluster_id)
        if not snapshots:
            return None
        return max(snapshots, key=lambda s: s.timestamp)

    def findByCluster(self, cluster_id: str) -> List[MetricSnapshot]:
        rows = self.db_service.executeQuery(f"SELECT * FROM {self.table_name} WHERE clusterId = %s", (cluster_id,))
        if rows or self.db_service.is_connected and "postgresql" in self.db_service.db_url:
            return [self._row_to_entity(r) for r in rows]
        return super().findByCluster(cluster_id)
