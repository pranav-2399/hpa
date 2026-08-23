from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, Any

@dataclass
class MetricSnapshot:
    metricId: str
    timestamp: datetime
    cpuUsage: float       # Average CPU utilization percentage (0 - 100%)
    memoryUsage: float    # Average Memory utilization percentage (0 - 100%)
    requestRate: float    # Requests per second (RPS)
    responseTime: float   # Latency in milliseconds (ms)
    activePods: int       # Number of active pods running
    clusterId: str

    def validateMetrics(self) -> bool:
        """Validates metric data integrity."""
        if self.cpuUsage < 0 or self.memoryUsage < 0 or self.activePods < 0:
            return False
        if self.requestRate < 0 or self.responseTime < 0:
            return False
        if not self.clusterId or not self.metricId:
            return False
        return True

    def calculateAverageLoad(self) -> float:
        """Calculates normalized aggregate system load score (0.0 to 100.0)."""
        # Weighted composite score: 60% CPU + 40% Memory
        return round((0.6 * self.cpuUsage) + (0.4 * self.memoryUsage), 2)

    def isHighLoad(self, cpu_threshold: float = 75.0, mem_threshold: float = 80.0) -> bool:
        """Returns True if CPU or Memory exceeds defined high-load thresholds."""
        return self.cpuUsage >= cpu_threshold or self.memoryUsage >= mem_threshold

    def isLowLoad(self, cpu_threshold: float = 25.0, mem_threshold: float = 30.0) -> bool:
        """Returns True if both CPU and Memory fall below low-load thresholds."""
        return self.cpuUsage < cpu_threshold and self.memoryUsage < mem_threshold

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metricId": self.metricId,
            "timestamp": self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else str(self.timestamp),
            "cpuUsage": self.cpuUsage,
            "memoryUsage": self.memoryUsage,
            "requestRate": self.requestRate,
            "responseTime": self.responseTime,
            "activePods": self.activePods,
            "clusterId": self.clusterId,
            "averageLoad": self.calculateAverageLoad()
        }
