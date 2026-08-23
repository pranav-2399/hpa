import time
import logging
import argparse
from autoscaler.config import config
from autoscaler.services import (
    PrometheusService,
    KubernetesService,
    PredictionService,
    ResourceAnalysisService,
    CostAnalysisService,
    LLMService
)
from autoscaler.repositories import DatabaseService
from autoscaler.agent import DecisionCoordinator

# Configure Logging Format
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("autoscaler.main")

def build_autoscaler_agent() -> DecisionCoordinator:
    """Factory function instantiating services, repos, and main agent."""
    db_service = DatabaseService(config.DATABASE_URL)
    db_service.connect()

    prom_service = PrometheusService(
        prometheusUrl=config.PROMETHEUS_URL,
        queryTimeout=config.PROMETHEUS_QUERY_TIMEOUT
    )
    
    k8s_service = KubernetesService(
        namespace=config.KUBERNETES_NAMESPACE,
        deploymentName=config.DEPLOYMENT_NAME,
        in_cluster=config.IN_CLUSTER
    )

    pred_service = PredictionService(
        prometheusService=prom_service,
        predictionWindow=config.PREDICTION_WINDOW_MINUTES
    )

    res_service = ResourceAnalysisService(
        prometheusService=prom_service,
        cpuThreshold=config.CPU_THRESHOLD_PERCENT,
        memoryThreshold=config.MEMORY_THRESHOLD_PERCENT
    )

    cost_service = CostAnalysisService(
        podCost=config.COST_PER_POD_HOUR
    )

    llm_service = LLMService(
        modelName=config.LLM_MODEL_NAME,
        apiKey=config.LLM_API_KEY,
        endpoint=config.LLM_ENDPOINT,
        temperature=config.LLM_TEMPERATURE,
        maxTokens=config.LLM_MAX_TOKENS
    )

    coordinator = DecisionCoordinator(
        predictionService=pred_service,
        resourceAnalysisService=res_service,
        costAnalysisService=cost_service,
        llmService=llm_service,
        kubernetesService=k8s_service,
        dbService=db_service
    )
    return coordinator

def main():
    parser = argparse.ArgumentParser(description="AI-Driven Kubernetes Horizontal Pod Autoscaler")
    parser.add_argument("--once", action="store_true", help="Run a single iteration and exit")
    parser.add_argument("--interval", type=int, default=30, help="Polling loop interval in seconds (default: 30)")
    args = parser.parse_args()

    logger.info("Initializing AI-Driven Autoscaler System...")
    coordinator = build_autoscaler_agent()

    if args.once:
        logger.info("Running single control loop iteration...")
        result = coordinator.runSingleControlLoopIteration()
        print("\n--- Control Loop Result Summary ---")
        print(f"Metrics Snapshot : {result['snapshot']}")
        print(f"Prediction       : {result['prediction']}")
        print(f"Resource Analysis: {result['resource']}")
        print(f"Cost Analysis    : {result['cost']}")
        print(f"Recommendation   : {result['recommendation']}")
        print(f"Action Executed  : {result['actionExecuted']}")
    else:
        logger.info(f"Starting continuous HPA monitoring loop (interval: {args.interval}s)...")
        try:
            while True:
                coordinator.runSingleControlLoopIteration()
                time.sleep(args.interval)
        except KeyboardInterrupt:
            logger.info("Autoscaler stopped by user.")

if __name__ == "__main__":
    main()
