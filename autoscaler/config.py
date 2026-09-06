import os
from dotenv import load_dotenv
from dataclasses import dataclass

# Load environment variables from .env file at project root
load_dotenv()

@dataclass
class AutoscalerConfig:
    # Cluster & Kubernetes Settings
    CLUSTER_ID: str = os.getenv("CLUSTER_ID", "cluster-k8s-local-01")
    CLUSTER_NAME: str = os.getenv("CLUSTER_NAME")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    KUBERNETES_NAMESPACE: str = os.getenv("KUBERNETES_NAMESPACE", "default")
    DEPLOYMENT_NAME: str = os.getenv("DEPLOYMENT_NAME", "hpa-flask")
    IN_CLUSTER: bool = os.getenv("IN_CLUSTER", "false").lower() == "true"
    KUBECONFIG_PATH: str = os.getenv("KUBECONFIG_PATH", "~/.kube/config")

    # Prometheus Integration Settings
    PROMETHEUS_URL: str = os.getenv("PROMETHEUS_URL", "http://localhost:9090")
    PROMETHEUS_QUERY_TIMEOUT: int = int(os.getenv("PROMETHEUS_QUERY_TIMEOUT", "10"))

    # Database / PostgreSQL Settings
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/hpa_db")

    # LLM / Groq Integration Settings
    LLM_API_KEY: str = os.getenv("GROQ_API_KEY", os.getenv("LLM_API_KEY", ""))
    LLM_MODEL_NAME: str = os.getenv("LLM_MODEL_NAME", "openai/gpt-oss-20b")
    LLM_ENDPOINT: str = os.getenv("LLM_ENDPOINT", "https://api.groq.com/openai/v1/chat/completions")
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.2"))
    LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "500"))

    # Autoscaling Guardrails & Thresholds
    CPU_THRESHOLD_PERCENT: float = float(os.getenv("CPU_THRESHOLD_PERCENT", "75.0"))
    MEMORY_THRESHOLD_PERCENT: float = float(os.getenv("MEMORY_THRESHOLD_PERCENT", "80.0"))
    MIN_REPLICAS: int = int(os.getenv("MIN_REPLICAS", "1"))
    MAX_REPLICAS: int = int(os.getenv("MAX_REPLICAS", "10"))
    STABILIZATION_WINDOW_SECONDS: int = int(os.getenv("STABILIZATION_WINDOW_SECONDS", "60"))
    PREDICTION_WINDOW_MINUTES: int = int(os.getenv("PREDICTION_WINDOW_MINUTES", "15"))

    # Cost Parameters ($ per pod hour)
    COST_PER_POD_HOUR: float = float(os.getenv("COST_PER_POD_HOUR", "0.05"))

config = AutoscalerConfig()
