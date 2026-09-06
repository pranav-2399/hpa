import logging
from typing import Dict, Any, List, Optional
from autoscaler.models.cluster import Pod
from autoscaler.config import config
from pprint import pprint

logger = logging.getLogger("autoscaler.kubernetes")

class KubernetesService:
    """Handles real Kubernetes cluster monitoring and deployment scaling operations."""

    def __init__(self, namespace: str = config.KUBERNETES_NAMESPACE, deploymentName: str = config.DEPLOYMENT_NAME, in_cluster: bool = config.IN_CLUSTER):
        self.namespace = namespace
        self.deploymentName = deploymentName
        self.in_cluster = in_cluster
        self.kubernetesClient = None
        self.coreClient = None
        self.customObjectsClient = None
        self._init_client()

    def _init_client(self) -> None:
        """Initializes official Python kubernetes SDK client from kubeconfig or in-cluster service account."""
        try:
            from kubernetes import client, config as k8s_config
            if self.in_cluster:
                k8s_config.load_incluster_config()
                logger.info("Loaded in-cluster Kubernetes configuration.")
            else:
                k8s_config.load_kube_config(config_file=config.KUBECONFIG_PATH)
                logger.info(f"Loaded kubeconfig from '{config.KUBECONFIG_PATH}'.")

            self.kubernetesClient = client.AppsV1Api()
            self.coreClient = client.CoreV1Api()
            self.customObjectsClient = client.CustomObjectsApi()
            logger.info("Kubernetes API clients initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize Kubernetes API client: {e}. Ensure Kubernetes cluster (Minikube) is running.")
            self.kubernetesClient = None
            self.coreClient = None
            self.customObjectsClient = None

    def getCurrentReplicas(self) -> int:
        """Queries the live active deployment replica count from Kubernetes API."""
        if not self.kubernetesClient:
            logger.warning("Kubernetes client unreachable. Trying to re-initialize connection...")
            self._init_client()

        if self.kubernetesClient:
            try:
                dep = self.kubernetesClient.read_namespaced_deployment(
                    name=self.deploymentName,
                    namespace=self.namespace
                )
                return dep.spec.replicas or 0
            except Exception as e:
                logger.error(f"Error querying deployment '{self.deploymentName}' in namespace '{self.namespace}': {e}")
                return 0
        return 0

    def getPodStatus(self) -> List[Pod]:
        """Queries and returns live Pod objects running in the Kubernetes cluster."""
        pods: List[Pod] = []
        if not self.coreClient:
            self._init_client()

        if self.coreClient:
            try:
                pod_list = self.coreClient.list_namespaced_pod(
                    namespace=self.namespace,
                    label_selector=f"app={self.deploymentName}"
                )
                               
                # Fetch pod metric usage if metrics-server is enabled in cluster
                pod_metrics_map = self._fetch_metrics_server_pod_usage()

                for item in pod_list.items:
                    pod_name = item.metadata.name
                    pod_uid = item.metadata.uid or pod_name
                    phase = item.status.phase or "Unknown"

                    # Check if metrics server returned real CPU/Memory for this pod
                    usage = pod_metrics_map.get(pod_name, {"cpu": 0.0, "memory": 0.0})

                    pods.append(Pod(
                        podId=pod_uid,
                        podName=pod_name,
                        status=phase,
                        cpuUsage=usage["cpu"],
                        memoryUsage=usage["memory"],
                        clusterId=config.CLUSTER_ID
                    ))
                return pods
            except Exception as e:
                logger.error(f"Error fetching live pods from Kubernetes cluster: {e}")
                return []
        return []

    def _fetch_metrics_server_pod_usage(self) -> Dict[str, Dict[str, float]]:
        """Queries metrics.k8s.io metrics-server API if available on Minikube."""
        usage_map = {}
        if not self.customObjectsClient:
            return usage_map
        try:
            res = self.customObjectsClient.list_namespaced_custom_object(
                group="metrics.k8s.io",
                version="v1beta1",
                namespace=self.namespace,
                plural="pods"
            )
            for item in res.get("items", []):
                name = item.get("metadata", {}).get("name")
                containers = item.get("containers", [])
                cpu_nano = 0
                mem_bytes = 0
                for c in containers:
                    cpu_str = c.get("usage", {}).get("cpu", "0")
                    mem_str = c.get("usage", {}).get("memory", "0")
                    # Parse nanocores (e.g. 5000000n)
                    if cpu_str.endswith("n"):
                        cpu_nano += int(cpu_str[:-1])
                    elif cpu_str.endswith("m"):
                        cpu_nano += int(cpu_str[:-1]) * 1000000
                    
                    # Parse memory Ki/Mi
                    if mem_str.endswith("Ki"):
                        mem_bytes += int(mem_str[:-2]) * 1024
                    elif mem_str.endswith("Mi"):
                        mem_bytes += int(mem_str[:-2]) * 1024 * 1024
                
                # Convert CPU to millicores / percentage (250m request base)
                cpu_milli = cpu_nano / 1000000.0
                cpu_percent = round((cpu_milli / 250.0) * 100.0, 2)
                mem_mb = round(mem_bytes / (1024 * 1024), 2)
                usage_map[name] = {"cpu": cpu_percent, "memory": mem_mb}
        except Exception:
            # Metrics server might not have collected data yet
            pass
        
        #rint("USAGE MAP: ")
        #pprint(usage_map)
        return usage_map

    def scaleDeployment(self, new_replica_count: int) -> bool:
        """Issues an actual scale patch request to Kubernetes API for deployment/hpa-flask."""
        current = self.getCurrentReplicas()
        logger.info(f"Issuing Kubernetes patch request to scale '{self.deploymentName}' from {current} to {new_replica_count} replicas...")
        
        if not self.kubernetesClient:
            self._init_client()

        if self.kubernetesClient:
            try:
                body = {"spec": {"replicas": new_replica_count}}
                self.kubernetesClient.patch_namespaced_deployment_scale(
                    name=self.deploymentName,
                    namespace=self.namespace,
                    body=body
                )
                logger.info(f"Kubernetes Deployment '{self.deploymentName}' scaled successfully to {new_replica_count} replicas.")
                return True
            except Exception as e:
                logger.error(f"Failed to scale Kubernetes deployment '{self.deploymentName}': {e}")
                return False
        logger.error("Cannot scale deployment: Kubernetes cluster is unreachable.")
        return False

    def createPod(self) -> bool:
        """Increments replica count by 1 on Kubernetes deployment."""
        current = self.getCurrentReplicas()
        return self.scaleDeployment(current + 1)

    def removePod(self) -> bool:
        """Decrements replica count by 1 (minimum 1) on Kubernetes deployment."""
        current = self.getCurrentReplicas()
        target = max(1, current - 1)
        return self.scaleDeployment(target)

    def getClusterState(self) -> Dict[str, Any]:
        """Returns actual Kubernetes deployment state from cluster."""
        if not self.kubernetesClient:
            self._init_client()

        connected = self.kubernetesClient is not None
        status = "Connected" if connected else "Unreachable"
        replicas = 0
        ready_replicas = 0
        
        if connected:
            try:
                dep = self.kubernetesClient.read_namespaced_deployment(self.deploymentName, self.namespace)
                replicas = dep.spec.replicas or 0
                ready_replicas = dep.status.ready_replicas or 0
            except Exception as e:
                status = f"Error: {e}"

        return {
            "clusterId": config.CLUSTER_ID,
            "namespace": self.namespace,
            "deployment": self.deploymentName,
            "status": status,
            "desiredReplicas": replicas,
            "readyReplicas": ready_replicas,
            "k8sClientConnected": connected
        }
