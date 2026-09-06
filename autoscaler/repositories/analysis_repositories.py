from typing import Optional, List
from autoscaler.repositories.base_repository import BaseRepository, DatabaseService
from autoscaler.models.analysis import ResourceAnalysis, CostAnalysis

class ResourceAnalysisRepository(BaseRepository):
    """Repository for storing ResourceAnalysis entities."""

    def __init__(self, db_service: DatabaseService):
        super().__init__(db_service, "resource_analyses")

    def save(self, entity: ResourceAnalysis) -> ResourceAnalysis:
        query = """
            INSERT INTO resource_analyses (analysisId, cpuUtilization, memoryUtilization, idleResources, recommendedReplicas, currentReplicas, targetCpuThreshold, targetMemThreshold, analysisTime)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (analysisId) DO UPDATE SET
                cpuUtilization = EXCLUDED.cpuUtilization,
                memoryUtilization = EXCLUDED.memoryUtilization,
                idleResources = EXCLUDED.idleResources,
                recommendedReplicas = EXCLUDED.recommendedReplicas,
                currentReplicas = EXCLUDED.currentReplicas,
                targetCpuThreshold = EXCLUDED.targetCpuThreshold,
                targetMemThreshold = EXCLUDED.targetMemThreshold,
                analysisTime = EXCLUDED.analysisTime
        """
        params = (
            entity.analysisId, entity.cpuUtilization, entity.memoryUtilization, 
            entity.idleResources, entity.recommendedReplicas, entity.currentReplicas, 
            entity.targetCpuThreshold, entity.targetMemThreshold, entity.analysisTime
        )
        self.db_service.executeQuery(query, params)
        self._store[entity.analysisId] = entity
        return entity

    def _row_to_entity(self, row: dict) -> ResourceAnalysis:
        return ResourceAnalysis(
            analysisId=row.get("analysisid", row.get("analysisId", "")),
            cpuUtilization=float(row.get("cpuutilization", row.get("cpuUtilization", 0.0))),
            memoryUtilization=float(row.get("memoryutilization", row.get("memoryUtilization", 0.0))),
            idleResources=bool(row.get("idleresources", row.get("idleResources", False))),
            recommendedReplicas=int(row.get("recommendedreplicas", row.get("recommendedReplicas", 1))),
            currentReplicas=int(row.get("currentreplicas", row.get("currentReplicas", 1))),
            targetCpuThreshold=float(row.get("targetcputhreshold", row.get("targetCpuThreshold", 75.0))),
            targetMemThreshold=float(row.get("targetmemthreshold", row.get("targetMemThreshold", 80.0))),
            analysisTime=row.get("analysistime", row.get("analysisTime"))
        )

    def findById(self, entity_id: str) -> Optional[ResourceAnalysis]:
        rows = self.db_service.executeQuery(f"SELECT * FROM {self.table_name} WHERE analysisId = %s", (entity_id,))
        if rows:
            return self._row_to_entity(rows[0])
        return self._store.get(entity_id)

    def getLatestAnalysis(self) -> Optional[ResourceAnalysis]:
        rows = self.db_service.executeQuery(f"SELECT * FROM {self.table_name} ORDER BY analysisTime DESC LIMIT 1")
        if rows:
            return self._row_to_entity(rows[0])
        all_items = self.findAll()
        if not all_items:
            return None
        return max(all_items, key=lambda a: a.analysisTime)


class CostAnalysisRepository(BaseRepository):
    """Repository for storing CostAnalysis entities."""

    def __init__(self, db_service: DatabaseService):
        super().__init__(db_service, "cost_analyses")

    def save(self, entity: CostAnalysis) -> CostAnalysis:
        query = """
            INSERT INTO cost_analyses (analysisId, currentPodCount, costPerPodPerHour, estimatedCost, estimatedFutureCost, costEfficiency, analysisTime)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (analysisId) DO UPDATE SET
                currentPodCount = EXCLUDED.currentPodCount,
                costPerPodPerHour = EXCLUDED.costPerPodPerHour,
                estimatedCost = EXCLUDED.estimatedCost,
                estimatedFutureCost = EXCLUDED.estimatedFutureCost,
                costEfficiency = EXCLUDED.costEfficiency,
                analysisTime = EXCLUDED.analysisTime
        """
        params = (
            entity.analysisId, entity.currentPodCount, entity.costPerPodPerHour, 
            entity.estimatedCost, entity.estimatedFutureCost, entity.costEfficiency, 
            entity.analysisTime
        )
        self.db_service.executeQuery(query, params)
        self._store[entity.analysisId] = entity
        return entity

    def _row_to_entity(self, row: dict) -> CostAnalysis:
        return CostAnalysis(
            analysisId=row.get("analysisid", row.get("analysisId", "")),
            currentPodCount=int(row.get("currentpodcount", row.get("currentPodCount", 0))),
            costPerPodPerHour=float(row.get("costperpodperhour", row.get("costPerPodPerHour", 0.0))),
            estimatedCost=float(row.get("estimatedcost", row.get("estimatedCost", 0.0))),
            estimatedFutureCost=float(row.get("estimatedfuturecost", row.get("estimatedFutureCost", 0.0))),
            costEfficiency=float(row.get("costefficiency", row.get("costEfficiency", 0.0))),
            analysisTime=row.get("analysistime", row.get("analysisTime"))
        )

    def findById(self, entity_id: str) -> Optional[CostAnalysis]:
        rows = self.db_service.executeQuery(f"SELECT * FROM {self.table_name} WHERE analysisId = %s", (entity_id,))
        if rows:
            return self._row_to_entity(rows[0])
        return self._store.get(entity_id)

    def getLatestAnalysis(self) -> Optional[CostAnalysis]:
        rows = self.db_service.executeQuery(f"SELECT * FROM {self.table_name} ORDER BY analysisTime DESC LIMIT 1")
        if rows:
            return self._row_to_entity(rows[0])
        all_items = self.findAll()
        if not all_items:
            return None
        return max(all_items, key=lambda a: a.analysisTime)
