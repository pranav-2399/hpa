from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

@dataclass
class Pod:
    podId: str
    podName: str
    status: str  # Running, Pending, Terminated, CrashLoopBackOff
    cpuUsage: float  # Percentage or millicores
    memoryUsage: float  # MB or Bytes
    clusterId: str
    createdAt: datetime = field(default_factory=datetime.utcnow)

    def getStatus(self) -> str:
        return self.status

    def getCpuUsage(self) -> float:
        return self.cpuUsage

    def getMemoryUsage(self) -> float:
        return self.memoryUsage

    def isIdle(self, cpu_idle_threshold: float = 5.0) -> bool:
        """Determines if pod CPU utilization is below idle threshold."""
        return self.cpuUsage < cpu_idle_threshold

    def getResourceUtilization(self) -> Dict[str, float]:
        return {
            "cpuUsage": self.cpuUsage,
            "memoryUsage": self.memoryUsage
        }


@dataclass
class Cluster:
    clusterId: str
    name: str
    environment: str  # dev, staging, production
    status: str  # Healthy, Degraded, Unreachable
    createdAt: datetime = field(default_factory=datetime.utcnow)
    pods: List[Pod] = field(default_factory=list)

    def getClusterDetails(self) -> Dict[str, Any]:
        return {
            "clusterId": self.clusterId,
            "name": self.name,
            "environment": self.environment,
            "status": self.status,
            "createdAt": self.createdAt.isoformat(),
            "activePodCount": len(self.pods)
        }

    def getCurrentMetrics(self) -> Dict[str, float]:
        if not self.pods:
            return {"avgCpu": 0.0, "avgMemory": 0.0, "totalPods": 0}
        avg_cpu = sum(p.cpuUsage for p in self.pods) / len(self.pods)
        avg_mem = sum(p.memoryUsage for p in self.pods) / len(self.pods)
        return {
            "avgCpu": round(avg_cpu, 2),
            "avgMemory": round(avg_mem, 2),
            "totalPods": len(self.pods)
        }

    def getActivePods(self) -> List[Pod]:
        return [p for p in self.pods if p.status.lower() in ("running", "active")]

    def getResourceUsage(self) -> Dict[str, float]:
        total_cpu = sum(p.cpuUsage for p in self.pods)
        total_memory = sum(p.memoryUsage for p in self.pods)
        return {
            "totalCpuUsage": round(total_cpu, 2),
            "totalMemoryUsage": round(total_memory, 2)
        }
