import os
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from abc import ABC, abstractmethod

logger = logging.getLogger("autoscaler.database")

class DatabaseService:
    """Handles communication with the database engine (PostgreSQL or in-memory fallback)."""
    
    def __init__(self, db_url: str):
        self.db_url = db_url
        self.is_connected = False
        self._in_memory_store: Dict[str, Dict[str, Any]] = {}
        self.pool = None

    def connect(self) -> bool:
        """Establishes database connection."""
        try:
            if "postgresql" in self.db_url:
                try:
                    import psycopg2
                    # Attempt connection if psycopg2 installed
                    self.pool = psycopg2.connect(self.db_url)
                    self.is_connected = True
                    logger.info("Connected to PostgreSQL database successfully.")
                    self._initialize_schema()
                    return True
                except Exception as e:
                    logger.error(f"PostgreSQL connection failed ({e}). Falling back to internal storage.", exc_info=True)
                    self.is_connected = True
                    return True
            else:
                self.is_connected = True
                logger.info("Using SQLite/In-Memory database store.")
                return True
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            self.is_connected = False
            return False

    def _initialize_schema(self) -> None:
        """Runs DDL to create tables if they don't exist."""
        queries = [
            """
            CREATE TABLE IF NOT EXISTS metric_snapshots (
                metricId VARCHAR(50) PRIMARY KEY,
                timestamp TIMESTAMP,
                cpuUsage FLOAT,
                memoryUsage FLOAT,
                requestRate FLOAT,
                responseTime FLOAT,
                activePods INT,
                clusterId VARCHAR(50)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS traffic_predictions (
                predictionId VARCHAR(50) PRIMARY KEY,
                predictedTraffic FLOAT,
                currentTraffic FLOAT,
                predictionWindow INT,
                confidence FLOAT,
                modelUsed VARCHAR(100),
                createdAt TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS resource_analyses (
                analysisId VARCHAR(50) PRIMARY KEY,
                cpuUtilization FLOAT,
                memoryUtilization FLOAT,
                idleResources BOOLEAN,
                recommendedReplicas INT,
                currentReplicas INT,
                targetCpuThreshold FLOAT,
                targetMemThreshold FLOAT,
                analysisTime TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS cost_analyses (
                analysisId VARCHAR(50) PRIMARY KEY,
                currentPodCount INT,
                costPerPodPerHour FLOAT,
                estimatedCost FLOAT,
                estimatedFutureCost FLOAT,
                costEfficiency FLOAT,
                analysisTime TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS scaling_actions (
                actionId VARCHAR(50) PRIMARY KEY,
                actionType VARCHAR(50),
                previousReplicaCount INT,
                newReplicaCount INT,
                status VARCHAR(50),
                reason TEXT,
                executedAt TIMESTAMP,
                executionDuration FLOAT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS decision_logs (
                decisionId VARCHAR(50) PRIMARY KEY,
                inputSummary JSONB,
                decision TEXT,
                reasoning TEXT,
                confidence FLOAT,
                actionId VARCHAR(50),
                decisionTime TIMESTAMP
            )
            """
        ]
        if self.pool:
            try:
                with self.pool.cursor() as cursor:
                    for query in queries:
                        cursor.execute(query)
                self.pool.commit()
                logger.info("Database schema initialized successfully.")
            except Exception as e:
                logger.error(f"Failed to initialize database schema: {e}", exc_info=True)
                self.pool.rollback()

    def disconnect(self) -> None:
        """Disconnects from database."""
        if self.pool and not self.pool.closed:
            self.pool.close()
        self.is_connected = False
        logger.info("Disconnected from database.")

    def executeQuery(self, query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """Executes SQL query or handles local execution."""
        if not self.is_connected:
            self.connect()
        
        if self.pool:
            try:
                with self.pool.cursor() as cursor:
                    cursor.execute(query, params or ())
                    if cursor.description:
                        columns = [desc[0] for desc in cursor.description]
                        return [dict(zip(columns, row)) for row in cursor.fetchall()]
                    self.pool.commit()
                    return []
            except Exception as e:
                logger.error(f"Query execution error: {e}")
                return []
        return []


class BaseRepository(ABC):
    """Abstract Base Repository providing standard CRUD methods."""

    def __init__(self, db_service: DatabaseService, table_name: str):
        self.db_service = db_service
        self.table_name = table_name
        self._store: Dict[str, Any] = {}

    @abstractmethod
    def save(self, entity: Any) -> Any:
        pass

    @abstractmethod
    def findById(self, entity_id: str) -> Optional[Any]:
        pass

    def findAll(self) -> List[Any]:
        return list(self._store.values())

    def findByCluster(self, cluster_id: str) -> List[Any]:
        results = []
        for item in self._store.values():
            if getattr(item, "clusterId", None) == cluster_id:
                results.append(item)
        return results

    def findByTimeRange(self, start_time: datetime, end_time: datetime) -> List[Any]:
        results = []
        for item in self._store.values():
            ts = getattr(item, "timestamp", getattr(item, "createdAt", getattr(item, "decisionTime", getattr(item, "analysisTime", None))))
            if ts and start_time <= ts <= end_time:
                results.append(item)
        return results

    def delete(self, entity_id: str) -> bool:
        if entity_id in self._store:
            del self._store[entity_id]
            return True
        return False
