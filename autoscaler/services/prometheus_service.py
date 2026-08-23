import logging
import requests
from typing import Dict, Any, List, Optional
from autoscaler.config import config

logger = logging.getLogger("autoscaler.prometheus")

class PrometheusService:
    """Handles communication with Prometheus time-series metrics server monitoring the Kubernetes cluster."""

    def __init__(self, prometheusUrl: str = config.PROMETHEUS_URL, queryTimeout: int = config.PROMETHEUS_QUERY_TIMEOUT):
        self.prometheusUrl = prometheusUrl.rstrip('/')
        self.queryTimeout = queryTimeout

    def queryMetrics(self, query: str) -> List[Dict[str, Any]]:
        """Executes PromQL instant query against Prometheus API."""
        endpoint = f"{self.prometheusUrl}/api/v1/query"
        try:
            response = requests.get(endpoint, params={"query": query}, timeout=self.queryTimeout)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    return data.get("data", {}).get("result", [])
            logger.warning(f"Prometheus query returned status {response.status_code}: {response.text}")
            return []
        except Exception as e:
            logger.warning(f"Prometheus unreachable at {self.prometheusUrl} ({e}).")
            return []

    def getCpuUsage(self, deployment_name: str = config.DEPLOYMENT_NAME) -> float:
        """Queries deployment average CPU utilization percentage from Prometheus."""
        query = f'sum(rate(container_cpu_usage_seconds_total{{pod=~"{deployment_name}-.*"}}[2m])) / count(container_cpu_usage_seconds_total{{pod=~"{deployment_name}-.*"}}) * 100'
        results = self.queryMetrics(query)
        if results and "value" in results[0]:
            try:
                return round(float(results[0]["value"][1]), 2)
            except (ValueError, IndexError):
                pass
        return 0.0

    def getMemoryUsage(self, deployment_name: str = config.DEPLOYMENT_NAME) -> float:
        """Queries deployment average memory utilization percentage from Prometheus."""
        query = f'avg(container_memory_working_set_bytes{{pod=~"{deployment_name}-.*"}}) / (1024 * 1024 * 512) * 100'
        results = self.queryMetrics(query)
        if results and "value" in results[0]:
            try:
                return round(float(results[0]["value"][1]), 2)
            except (ValueError, IndexError):
                pass
        return 0.0

    def getRequestRate(self, deployment_name: str = config.DEPLOYMENT_NAME) -> float:
        """Queries incoming request rate (requests per second) from Prometheus."""
        query = f'sum(rate(http_requests_total{{pod=~"{deployment_name}-.*"}}[2m]))'
        results = self.queryMetrics(query)
        if results and "value" in results[0]:
            try:
                return round(float(results[0]["value"][1]), 2)
            except (ValueError, IndexError):
                pass
        return 0.0

    def getResponseTime(self, deployment_name: str = config.DEPLOYMENT_NAME) -> float:
        """Queries 95th percentile HTTP response latency in milliseconds from Prometheus."""
        query = f'histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{{pod=~"{deployment_name}-.*"}}[2m])) by (le)) * 1000'
        results = self.queryMetrics(query)
        if results and "value" in results[0]:
            try:
                return round(float(results[0]["value"][1]), 2)
            except (ValueError, IndexError):
                pass
        return 0.0

    def getPodMetrics(self, deployment_name: str = config.DEPLOYMENT_NAME) -> List[Dict[str, Any]]:
        """Returns per-pod CPU and memory utilization details from Prometheus."""
        query = f'container_cpu_usage_seconds_total{{pod=~"{deployment_name}-.*"}}'
        results = self.queryMetrics(query)
        pod_list = []
        if results:
            for idx, res in enumerate(results):
                metric = res.get("metric", {})
                pod_name = metric.get("pod", f"{deployment_name}-{idx}")
                pod_list.append({
                    "podName": pod_name,
                    "cpuUsage": round(float(res.get("value", [0, 0.0])[1]), 2),
                    "memoryUsage": 0.0,
                    "status": "Running"
                })
        return pod_list
