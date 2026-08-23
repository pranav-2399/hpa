import logging
from typing import Dict, Any, List, Optional
from autoscaler.models.cluster import Pod

logger = logging.getLogger("autoscaler.kubernetes")

class KubernetesService:
    """Handles actual Kubernetes cluster and deployment scaling operations."""

    def __init__(self, namespace: str = "default", deploymentName: str = "hpa-load-target", in_cluster: bool = False):
        self.namespace = namespace
        self.deploymentName = deploymentName
        self.in_cluster = in_cluster
        self.kubernetesClient = None
        self._current_replicas = 2  # Simulated / initial replica state
        self._init_client()

    def _init_client(self) -> None:
        """Initializes Python kubernetes client if available."""
        try:
            from kubernetes import client, config
            if self.in_cluster:
                config.load_incluster_config()
            else:
                config.load_kube_config()
            self.kubernetesClient = client.AppsV1Api()
            self.coreClient = client.CoreV1Api()
            logger.info("Successfully initialized Kubernetes API client.")
        except Exception as e:
            logger.warning(f"Kubernetes API client init warning ({e}). Operating in direct control / mock mode.")
            self.kubernetesClient = None

    def getCurrentReplicas(self) -> int:
        """Queries deployment active replica count."""
        if self.kubernetesClient:
            try:
                dep = self.kubernetesClient.read_namespaced_deployment(self.deploymentName, self.namespace)
                self._current_replicas = dep.spec.replicas or 1
                return self._current_replicas
            except Exception as e:
                logger.error(f"Failed to query Kubernetes deployment: {e}")
        return self._current_replicas

    def getPodStatus(self) -> List[Pod]:
        """Returns pod object instances running under deployment."""
        pods = []
        if self.kubernetesClient and hasattr(self, 'coreClient'):
            try:
                pod_list = self.coreClient.list_namespaced_pod(
                    self.namespace, label_selector=f"app={self.deploymentName}"
                )
                for item in pod_list.items:
                    pods.append(Pod(
                        podId=item.metadata.uid or item.metadata.name,
                        podName=item.metadata.name,
                        status=item.status.phase or "Running",
                        cpuUsage=45.0,
                        memoryUsage=128.0,
                        clusterId="k8s-cluster"
                    ))
                return pods
            except Exception as e:
                logger.error(f"Error fetching pod status from K8s: {e}")
        
        # Fallback simulation list
        for i in range(self._current_replicas):
            pods.append(Pod(
                podId=f"pod-uid-{i+1}",
                podName=f"{self.deploymentName}-{i+1}",
                status="Running",
                cpuUsage=50.0,
                memoryUsage=128.0,
                clusterId="k8s-cluster"
            ))
        return pods

    def scaleDeployment(self, new_replica_count: int) -> bool:
        """Scales Kubernetes deployment to new target replica count."""
        logger.info(f"Scaling deployment '{self.deploymentName}' from {self._current_replicas} to {new_replica_count} replicas...")
        
        if self.kubernetesClient:
            try:
                body = {"spec": {"replicas": new_replica_count}}
                self.kubernetesClient.patch_namespaced_deployment_scale(
                    name=self.deploymentName,
                    namespace=self.namespace,
                    body=body
                )
                self._current_replicas = new_replica_count
                logger.info("K8s Deployment patch scale successful.")
                return True
            except Exception as e:
                logger.error(f"K8s scaling failed: {e}")
                return False
        
        # In mock/standalone mode, update state directly
        self._current_replicas = new_replica_count
        logger.info(f"Deployment scaling completed. New replica count: {self._current_replicas}")
        return True

    def createPod(self) -> bool:
        """Increments replica count by 1."""
        return self.scaleDeployment(self._current_replicas + 1)

    def removePod(self) -> bool:
        """Decrements replica count by 1 (minimum 1)."""
        target = max(1, self._current_replicas - 1)
        return self.scaleDeployment(target)

    def getClusterState(self) -> Dict[str, Any]:
        return {
            "namespace": self.namespace,
            "deployment": self.deploymentName,
            "replicas": self.getCurrentReplicas(),
            "k8sClientConnected": self.kubernetesClient is not None
        }
