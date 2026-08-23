from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, Any, List

@dataclass
class ResourceAnalysis:
    analysisId: str
    cpuUtilization: float          # Current CPU utilization %
    memoryUtilization: float       # Current Memory utilization %
    idleResources: bool            # Flag if idle resources detected
    recommendedReplicas: int       # Recommended pod count based on metrics
    currentReplicas: int           # Current active pod count
    targetCpuThreshold: float = 75.0
    targetMemThreshold: float = 80.0
    analysisTime: datetime = field(default_factory=datetime.utcnow)

    def detectOverUtilization(self) -> bool:
        """Detects if CPU or Memory exceeds high utilization targets."""
        return self.cpuUtilization >= self.targetCpuThreshold or self.memoryUtilization >= self.targetMemThreshold

    def detectUnderUtilization(self, low_cpu_thresh: float = 25.0, low_mem_thresh: float = 30.0) -> bool:
        """Detects if resource utilization is significantly below target."""
        return self.cpuUtilization < low_cpu_thresh and self.memoryUtilization < low_mem_thresh

    def calculateRecommendedReplicas(self, target_cpu_utilization: float = 70.0) -> int:
        """
        Calculates recommended replica count using standard Kubernetes HPA formula:
        desiredReplicas = ceil(currentReplicas * (currentUtilization / targetUtilization))
        """
        if self.currentReplicas <= 0 or target_cpu_utilization <= 0:
            return 1
        import math
        ratio = self.cpuUtilization / target_cpu_utilization
        calculated = math.ceil(self.currentReplicas * ratio)
        return max(1, calculated)

    def getResourceEfficiency(self) -> float:
        """Calculates resource efficiency percentage (ideal composite utilization)."""
        efficiency = (self.cpuUtilization + self.memoryUtilization) / 2.0
        return round(min(100.0, max(0.0, efficiency)), 2)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "analysisId": self.analysisId,
            "cpuUtilization": self.cpuUtilization,
            "memoryUtilization": self.memoryUtilization,
            "idleResources": self.idleResources,
            "recommendedReplicas": self.recommendedReplicas,
            "currentReplicas": self.currentReplicas,
            "resourceEfficiency": self.getResourceEfficiency(),
            "analysisTime": self.analysisTime.isoformat()
        }


@dataclass
class CostAnalysis:
    analysisId: str
    currentPodCount: int
    costPerPodPerHour: float
    estimatedCost: float           # Current hourly operational cost
    estimatedFutureCost: float     # Future estimated hourly cost based on scaling
    costEfficiency: float          # Cost efficiency rating (0 - 100%)
    analysisTime: datetime = field(default_factory=datetime.utcnow)

    def calculateCurrentCost(self) -> float:
        """Calculates total current hourly cost."""
        self.estimatedCost = round(self.currentPodCount * self.costPerPodPerHour, 4)
        return self.estimatedCost

    def calculateProjectedCost(self, target_pod_count: int) -> float:
        """Calculates projected hourly cost for a given target pod count."""
        self.estimatedFutureCost = round(target_pod_count * self.costPerPodPerHour, 4)
        return self.estimatedFutureCost

    def calculateCostPerPod(self) -> float:
        return self.costPerPodPerHour

    def compareScalingOptions(self, scaling_options: List[int]) -> Dict[int, float]:
        """Returns map of pod count -> projected hourly cost for comparison."""
        return {pods: round(pods * self.costPerPodPerHour, 4) for pods in scaling_options}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "analysisId": self.analysisId,
            "currentPodCount": self.currentPodCount,
            "costPerPodPerHour": self.costPerPodPerHour,
            "estimatedCost": self.estimatedCost,
            "estimatedFutureCost": self.estimatedFutureCost,
            "costEfficiency": self.costEfficiency,
            "analysisTime": self.analysisTime.isoformat()
        }
