import uuid
import math
import logging
from typing import Dict, Any
from datetime import datetime
from autoscaler.models.analysis import ResourceAnalysis
from autoscaler.models.metrics import MetricSnapshot
from autoscaler.services.prometheus_service import PrometheusService

logger = logging.getLogger("autoscaler.resource_analysis")

class ResourceAnalysisService:
    """Analyzes pod and cluster resource utilization against high/low thresholds."""

    def __init__(self, prometheusService: PrometheusService, cpuThreshold: float = 75.0, memoryThreshold: float = 80.0):
        self.prometheusService = prometheusService
        self.cpuThreshold = cpuThreshold
        self.memoryThreshold = memoryThreshold

    def fetchResourceMetrics(self, deployment_name: str) -> Dict[str, float]:
        """Fetches live CPU & memory metrics from Prometheus."""
        cpu = self.prometheusService.getCpuUsage(deployment_name)
        mem = self.prometheusService.getMemoryUsage(deployment_name)
        return {"cpuUsage": cpu, "memoryUsage": mem}

    def analyzeCpuUsage(self, cpu_usage: float) -> str:
        """Categorizes CPU state."""
        if cpu_usage >= self.cpuThreshold:
            return "OVER_UTILIZED"
        elif cpu_usage < 25.0:
            return "UNDER_UTILIZED"
        return "NORMAL"

    def analyzeMemoryUsage(self, memory_usage: float) -> str:
        """Categorizes Memory state."""
        if memory_usage >= self.memoryThreshold:
            return "OVER_UTILIZED"
        elif memory_usage < 30.0:
            return "UNDER_UTILIZED"
        return "NORMAL"

    def detectIdleResources(self, cpu_usage: float, memory_usage: float) -> bool:
        """Returns True if cluster is largely idle."""
        return cpu_usage < 15.0 and memory_usage < 20.0

    def recommendReplicaCount(self, snapshot: MetricSnapshot, min_replicas: int = 1, max_replicas: int = 10) -> int:
        """
        Calculates recommended replica count using HPA math based on CPU target utilization.
        """
        current_replicas = max(1, snapshot.activePods)
        current_cpu = snapshot.cpuUsage
        
        if current_cpu <= 0:
            return current_replicas
        
        # Desired = ceil(current * (current_cpu / target_cpu))
        target_utilization = self.cpuThreshold
        desired = math.ceil(current_replicas * (current_cpu / target_utilization))
        return max(min_replicas, min(max_replicas, desired))

    def generateResourceAnalysis(self, snapshot: MetricSnapshot, min_replicas: int = 1, max_replicas: int = 10) -> ResourceAnalysis:
        """Produces a ResourceAnalysis domain model."""
        recommended_replicas = self.recommendReplicaCount(snapshot, min_replicas, max_replicas)
        is_idle = self.detectIdleResources(snapshot.cpuUsage, snapshot.memoryUsage)
        
        analysis = ResourceAnalysis(
            analysisId=f"res-{uuid.uuid4().hex[:8]}",
            cpuUtilization=snapshot.cpuUsage,
            memoryUtilization=snapshot.memoryUsage,
            idleResources=is_idle,
            recommendedReplicas=recommended_replicas,
            currentReplicas=snapshot.activePods,
            targetCpuThreshold=self.cpuThreshold,
            targetMemThreshold=self.memoryThreshold,
            analysisTime=datetime.utcnow()
        )
        logger.info(f"Resource analysis generated: CPU={snapshot.cpuUsage}%, Mem={snapshot.memoryUsage}%, RecommReplicas={recommended_replicas}")
        return analysis
