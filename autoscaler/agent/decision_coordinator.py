import uuid
import time
import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

from autoscaler.config import config
from autoscaler.models import (
    MetricSnapshot,
    TrafficPrediction,
    ResourceAnalysis,
    CostAnalysis,
    ScalingRecommendation,
    ScalingAction,
    DecisionLog,
    ACTION_SCALE_UP,
    ACTION_SCALE_DOWN,
    ACTION_MAINTAIN
)
from autoscaler.services import (
    PrometheusService,
    KubernetesService,
    PredictionService,
    ResourceAnalysisService,
    CostAnalysisService,
    LLMService
)
from autoscaler.repositories import (
    DatabaseService,
    MetricRepository,
    PredictionRepository,
    ResourceAnalysisRepository,
    CostAnalysisRepository,
    ScalingActionRepository,
    DecisionLogRepository
)

logger = logging.getLogger("autoscaler.coordinator")

class DecisionCoordinator:
    """
    Main AI Agent class and core control loop orchestrator.
    Receives data from analysis services, queries LLM for decision reasoning,
    validates recommendations, executes K8s scaling actions, and logs outcomes.
    """

    def __init__(
        self,
        predictionService: PredictionService,
        resourceAnalysisService: ResourceAnalysisService,
        costAnalysisService: CostAnalysisService,
        llmService: LLMService,
        kubernetesService: KubernetesService,
        dbService: DatabaseService
    ):
        self.predictionService = predictionService
        self.resourceAnalysisService = resourceAnalysisService
        self.costAnalysisService = costAnalysisService
        self.llmService = llmService
        self.kubernetesService = kubernetesService
        
        # Repositories
        self.metricRepo = MetricRepository(dbService)
        self.predictionRepo = PredictionRepository(dbService)
        self.resourceRepo = ResourceAnalysisRepository(dbService)
        self.costRepo = CostAnalysisRepository(dbService)
        self.actionRepo = ScalingActionRepository(dbService)
        self.decisionRepo = DecisionLogRepository(dbService)

        # Stabilization timer tracking
        self.lastScalingTime: Optional[datetime] = None

    def analyzeSystemState(self, cluster_id: str = config.CLUSTER_ID) -> MetricSnapshot:
        """Polls Prometheus and Kubernetes to collect current cluster state."""
        current_replicas = self.kubernetesService.getCurrentReplicas()
        cpu = self.resourceAnalysisService.prometheusService.getCpuUsage(config.DEPLOYMENT_NAME)
        memory = self.resourceAnalysisService.prometheusService.getMemoryUsage(config.DEPLOYMENT_NAME)
        request_rate = self.resourceAnalysisService.prometheusService.getRequestRate(config.DEPLOYMENT_NAME)
        response_time = self.resourceAnalysisService.prometheusService.getResponseTime(config.DEPLOYMENT_NAME)

        snapshot = MetricSnapshot(
            metricId=f"metric-{uuid.uuid4().hex[:8]}",
            timestamp=datetime.utcnow(),
            cpuUsage=cpu,
            memoryUsage=memory,
            requestRate=request_rate,
            responseTime=response_time,
            activePods=current_replicas,
            clusterId=cluster_id
        )
        snapshot.validateMetrics()
        self.metricRepo.save(snapshot)
        logger.info(f"Captured MetricSnapshot: CPU={cpu}%, Mem={memory}%, RPS={request_rate}, ActivePods={current_replicas}")
        return snapshot

    def collectAnalysisResults(self, snapshot: MetricSnapshot) -> Tuple[TrafficPrediction, ResourceAnalysis, CostAnalysis]:
        """Runs prediction, resource analysis, and cost estimation services."""
        history = self.metricRepo.getRecentSnapshots(snapshot.clusterId, limit=10)
        
        # 1. Traffic Prediction
        prediction = self.predictionService.generatePrediction(snapshot, history)
        self.predictionRepo.save(prediction)

        # 2. Resource Analysis
        resource_analysis = self.resourceAnalysisService.generateResourceAnalysis(
            snapshot, config.MIN_REPLICAS, config.MAX_REPLICAS
        )
        self.resourceRepo.save(resource_analysis)

        # 3. Cost Analysis
        cost_analysis = self.costAnalysisService.generateCostAnalysis(
            snapshot.activePods, resource_analysis.recommendedReplicas
        )
        self.costRepo.save(cost_analysis)

        return prediction, resource_analysis, cost_analysis

    def generateDecision(
        self,
        snapshot: MetricSnapshot,
        prediction: TrafficPrediction,
        resource: ResourceAnalysis,
        cost: CostAnalysis
    ) -> Tuple[Dict[str, Any], float]:
        """Queries LLM (or rule fallback) to determine scaling action and target replica count."""
        prompt = self.llmService.buildPrompt(
            metric_summary=snapshot.to_dict(),
            prediction_summary=prediction.to_dict(),
            resource_summary=resource.to_dict(),
            cost_summary=cost.to_dict(),
            min_replicas=config.MIN_REPLICAS,
            max_replicas=config.MAX_REPLICAS
        )

        raw_llm_output = self.llmService.sendRequest(prompt)
        parsed_decision = self.llmService.parseResponse(raw_llm_output) if raw_llm_output else None

        if parsed_decision and self.llmService.validateDecision(parsed_decision, config.MIN_REPLICAS, config.MAX_REPLICAS):
            confidence = float(parsed_decision.get("confidence", 0.85))
            logger.info(f"LLM Decision generated: Action={parsed_decision.get('action')}, TargetReplicas={parsed_decision.get('target_replicas')}")
            return parsed_decision, confidence

        # Fallback Rule-based engine decision
        logger.info("Executing rule-based AI fallback reasoning engine...")
        fallback_decision = self.evaluateScalingOptions(snapshot, prediction, resource)
        return fallback_decision, 0.80

    def evaluateScalingOptions(
        self,
        snapshot: MetricSnapshot,
        prediction: TrafficPrediction,
        resource: ResourceAnalysis
    ) -> Dict[str, Any]:
        """Rule-based decision evaluator used when LLM API is unavailable."""
        current_replicas = snapshot.activePods
        recommended_replicas = resource.recommendedReplicas

        if resource.detectOverUtilization() or prediction.isTrafficIncreaseExpected(15.0):
            target = min(config.MAX_REPLICAS, max(current_replicas + 1, recommended_replicas))
            action = ACTION_SCALE_UP if target > current_replicas else ACTION_MAINTAIN
            reasoning = f"High workload detected (CPU: {snapshot.cpuUsage}%, Mem: {snapshot.memoryUsage}% or predicted RPS increase to {prediction.predictedTraffic}). Scaling up for performance reliability."
            priority = "HIGH"
        elif resource.detectUnderUtilization() and prediction.isTrafficDecreaseExpected(15.0):
            target = max(config.MIN_REPLICAS, min(current_replicas - 1, recommended_replicas))
            action = ACTION_SCALE_DOWN if target < current_replicas else ACTION_MAINTAIN
            reasoning = f"Low resource utilization (CPU: {snapshot.cpuUsage}%, Mem: {snapshot.memoryUsage}%) and declining traffic. Scaling down to reduce infrastructure cost."
            priority = "MEDIUM"
        else:
            target = current_replicas
            action = ACTION_MAINTAIN
            reasoning = "System operating within healthy utilization bounds. Maintaining current replica count."
            priority = "LOW"

        return {
            "action": action,
            "target_replicas": target,
            "priority": priority,
            "confidence": 0.85,
            "reasoning": reasoning
        }

    def createRecommendation(self, decision_data: Dict[str, Any]) -> ScalingRecommendation:
        """Constructs a validated ScalingRecommendation entity."""
        recommendation = ScalingRecommendation(
            recommendationId=f"rec-{uuid.uuid4().hex[:8]}",
            recommendedAction=decision_data["action"],
            recommendedReplicaCount=decision_data["target_replicas"],
            reason=decision_data["reasoning"],
            priority=decision_data.get("priority", "MEDIUM"),
            createdAt=datetime.utcnow()
        )
        recommendation.validateRecommendation(config.MIN_REPLICAS, config.MAX_REPLICAS)
        return recommendation

    def executeDecision(self, snapshot: MetricSnapshot, recommendation: ScalingRecommendation, decision_dict: Dict[str, Any], confidence: float) -> Optional[ScalingAction]:
        """Executes scaling action on Kubernetes and persists DecisionLog."""
        current_replicas = snapshot.activePods
        new_replicas = recommendation.recommendedReplicaCount
        action_type = recommendation.recommendedAction

        # Check stabilization window cooldown
        now = datetime.utcnow()
        if self.lastScalingTime and (now - self.lastScalingTime).total_seconds() < config.STABILIZATION_WINDOW_SECONDS:
            logger.info(f"Stabilization window active ({config.STABILIZATION_WINDOW_SECONDS}s). Skipping scaling execution to avoid pod thrashing.")
            action_type = ACTION_MAINTAIN
            new_replicas = current_replicas

        scaling_action = None

        if action_type in (ACTION_SCALE_UP, ACTION_SCALE_DOWN) and new_replicas != current_replicas:
            scaling_action = ScalingAction(
                actionId=f"act-{uuid.uuid4().hex[:8]}",
                actionType=action_type,
                previousReplicaCount=current_replicas,
                newReplicaCount=new_replicas,
                status="PENDING",
                reason=recommendation.reason,
                executedAt=now
            )
            scaling_action.execute()
            
            start_time = time.time()
            success = self.kubernetesService.scaleDeployment(new_replicas)
            duration = time.time() - start_time

            if success:
                scaling_action.markSuccessful(duration)
                self.lastScalingTime = datetime.utcnow()
                logger.info(f"Scaling action EXECUTED SUCCESSFULLY: {action_type} ({current_replicas} -> {new_replicas} pods in {duration:.2f}s)")
            else:
                scaling_action.markFailed("Kubernetes API deployment patch rejected")
                scaling_action.rollback()
                logger.error("Scaling action execution failed. Triggered rollback state.")

            self.actionRepo.save(scaling_action)

        # Create and persist DecisionLog audit entry
        decision_log = DecisionLog(
            decisionId=f"dec-{uuid.uuid4().hex[:8]}",
            inputSummary={
                "cpuUsage": snapshot.cpuUsage,
                "memoryUsage": snapshot.memoryUsage,
                "requestRate": snapshot.requestRate,
                "activePods": snapshot.activePods
            },
            decision=f"{action_type} to {new_replicas} pods",
            reasoning=recommendation.reason,
            confidence=confidence,
            actionId=scaling_action.actionId if scaling_action else None,
            decisionTime=now
        )
        self.decisionRepo.save(decision_log)
        return scaling_action

    def runSingleControlLoopIteration(self) -> Dict[str, Any]:
        """Runs one full iteration of the autoscaler decision pipeline."""
        logger.info("--- Starting HPA Control Loop Iteration ---")
        snapshot = self.analyzeSystemState()
        prediction, resource, cost = self.collectAnalysisResults(snapshot)
        decision_dict, confidence = self.generateDecision(snapshot, prediction, resource, cost)
        recommendation = self.createRecommendation(decision_dict)
        action = self.executeDecision(snapshot, recommendation, decision_dict, confidence)

        return {
            "snapshot": snapshot.to_dict(),
            "prediction": prediction.to_dict(),
            "resource": resource.to_dict(),
            "cost": cost.to_dict(),
            "recommendation": recommendation.getRecommendationSummary(),
            "actionExecuted": action.to_dict() if action else None
        }
