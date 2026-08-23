import uuid
import logging
from typing import Dict, Any, List
from datetime import datetime
from autoscaler.models.analysis import CostAnalysis

logger = logging.getLogger("autoscaler.cost_analysis")

class CostAnalysisService:
    """Analyzes cloud infrastructure costs and scaling options."""

    def __init__(self, podCost: float = 0.05, resourceCost: float = 0.01):
        self.costModel = "Standard-Pod-Hourly"
        self.podCost = podCost          # Cost per pod per hour ($0.05)
        self.resourceCost = resourceCost

    def calculateCurrentCost(self, current_pod_count: int) -> float:
        """Calculates current hourly pod cost."""
        return round(current_pod_count * self.podCost, 4)

    def estimateScalingCost(self, target_pod_count: int) -> float:
        """Estimates projected hourly pod cost after scaling."""
        return round(target_pod_count * self.podCost, 4)

    def compareCostScenarios(self, current_pods: int, recommended_pods: int) -> Dict[str, Any]:
        """Compares current vs recommended pod cost scenarios."""
        current_cost = self.calculateCurrentCost(current_pods)
        projected_cost = self.estimateScalingCost(recommended_pods)
        cost_diff = round(projected_cost - current_cost, 4)
        
        return {
            "currentPodCount": current_pods,
            "recommendedPodCount": recommended_pods,
            "currentHourlyCost": current_cost,
            "projectedHourlyCost": projected_cost,
            "costDifference": cost_diff
        }

    def generateCostAnalysis(self, current_pod_count: int, recommended_pod_count: int) -> CostAnalysis:
        """Produces a CostAnalysis domain model object."""
        current_cost = self.calculateCurrentCost(current_pod_count)
        future_cost = self.estimateScalingCost(recommended_pod_count)
        
        # Cost efficiency score calculation
        if current_pod_count > 0:
            efficiency = round(min(100.0, (recommended_pod_count / current_pod_count) * 100.0), 2)
        else:
            efficiency = 100.0

        cost_analysis = CostAnalysis(
            analysisId=f"cost-{uuid.uuid4().hex[:8]}",
            currentPodCount=current_pod_count,
            costPerPodPerHour=self.podCost,
            estimatedCost=current_cost,
            estimatedFutureCost=future_cost,
            costEfficiency=efficiency,
            analysisTime=datetime.utcnow()
        )
        logger.info(f"Cost analysis generated: Current=${current_cost}/hr ({current_pod_count} pods) -> Future=${future_cost}/hr ({recommended_pod_count} pods)")
        return cost_analysis
