from typing import Optional, List
from autoscaler.repositories.base_repository import BaseRepository, DatabaseService
from autoscaler.models.decision_log import DecisionLog

class DecisionLogRepository(BaseRepository):
    """Repository for storing and auditing AI DecisionLog entities."""

    def __init__(self, db_service: DatabaseService):
        super().__init__(db_service, "decision_logs")

    def save(self, entity: DecisionLog) -> DecisionLog:
        import json
        query = """
            INSERT INTO decision_logs (decisionId, inputSummary, decision, reasoning, confidence, actionId, decisionTime)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (decisionId) DO UPDATE SET
                inputSummary = EXCLUDED.inputSummary,
                decision = EXCLUDED.decision,
                reasoning = EXCLUDED.reasoning,
                confidence = EXCLUDED.confidence,
                actionId = EXCLUDED.actionId,
                decisionTime = EXCLUDED.decisionTime
        """
        params = (
            entity.decisionId, json.dumps(entity.inputSummary), entity.decision, 
            entity.reasoning, entity.confidence, entity.actionId, entity.decisionTime
        )
        self.db_service.executeQuery(query, params)
        self._store[entity.decisionId] = entity
        return entity

    def _row_to_entity(self, row: dict) -> DecisionLog:
        input_summary = row.get("inputsummary", row.get("inputSummary", {}))
        if isinstance(input_summary, str):
            import json
            try:
                input_summary = json.loads(input_summary)
            except Exception:
                input_summary = {}
        return DecisionLog(
            decisionId=row.get("decisionid", row.get("decisionId", "")),
            inputSummary=input_summary,
            decision=row.get("decision", ""),
            reasoning=row.get("reasoning", ""),
            confidence=float(row.get("confidence", 0.0)),
            actionId=row.get("actionid", row.get("actionId")),
            decisionTime=row.get("decisiontime", row.get("decisionTime"))
        )

    def findById(self, entity_id: str) -> Optional[DecisionLog]:
        rows = self.db_service.executeQuery(f"SELECT * FROM {self.table_name} WHERE decisionId = %s", (entity_id,))
        if rows:
            return self._row_to_entity(rows[0])
        return self._store.get(entity_id)

    def getRecentLogs(self, limit: int = 20) -> List[DecisionLog]:
        rows = self.db_service.executeQuery(f"SELECT * FROM {self.table_name} ORDER BY decisionTime DESC LIMIT %s", (limit,))
        if rows or self.db_service.is_connected and "postgresql" in self.db_service.db_url:
            return [self._row_to_entity(r) for r in rows]
        logs = self.findAll()
        sorted_logs = sorted(logs, key=lambda d: d.decisionTime, reverse=True)
        return sorted_logs[:limit]
