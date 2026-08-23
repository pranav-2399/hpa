import json
import logging
import requests
from typing import Dict, Any, Optional

logger = logging.getLogger("autoscaler.llm")

class LLMService:
    """Abstraction layer interfacing between Autoscaler decision loop and Llama / Groq LLM API."""

    def __init__(
        self,
        modelName: str = "llama-3.3-70b-versatile",
        apiKey: str = "mock-key",
        endpoint: str = "https://api.groq.com/openai/v1/chat/completions",
        temperature: float = 0.2,
        maxTokens: int = 500
    ):
        self.modelName = modelName
        self.apiKey = apiKey
        self.endpoint = endpoint
        self.temperature = temperature
        self.maxTokens = maxTokens

    def buildPrompt(self, metric_summary: Dict[str, Any], prediction_summary: Dict[str, Any], resource_summary: Dict[str, Any], cost_summary: Dict[str, Any], min_replicas: int, max_replicas: int) -> str:
        """Constructs structured JSON system prompt for Llama reasoning."""
        prompt = f"""You are an expert Kubernetes AI Horizontal Pod Autoscaler agent.
Analyze the provided system state metrics, workload prediction, resource analysis, and cost estimation to decide whether to scale up, scale down, or maintain replica count.

Current System Metrics:
- CPU Utilization: {metric_summary.get('cpuUsage')}%
- Memory Utilization: {metric_summary.get('memoryUsage')}%
- Request Rate (RPS): {metric_summary.get('requestRate')}
- Latency (ms): {metric_summary.get('responseTime')}
- Active Pod Count: {metric_summary.get('activePods')}

Traffic Prediction:
- Predicted RPS: {prediction_summary.get('predictedTraffic')}
- Prediction Confidence: {prediction_summary.get('confidence')}

Resource Analysis Recommendation:
- Calculated Replica Count: {resource_summary.get('recommendedReplicas')}
- Idle Resources: {resource_summary.get('idleResources')}

Cost Analysis:
- Current Cost: ${cost_summary.get('estimatedCost')}/hr
- Projected Cost: ${cost_summary.get('estimatedFutureCost')}/hr

Constraints:
- Minimum Allowed Replicas: {min_replicas}
- Maximum Allowed Replicas: {max_replicas}

Respond STRICTLY in valid JSON format with NO markdown wrapping or extra commentary using this exact schema:
{{
  "action": "SCALE_UP" | "SCALE_DOWN" | "MAINTAIN",
  "target_replicas": <integer between {min_replicas} and {max_replicas}>,
  "priority": "HIGH" | "MEDIUM" | "LOW",
  "confidence": <float between 0.0 and 1.0>,
  "reasoning": "<clear step-by-step reasoning for the action>"
}}
"""
        return prompt.strip()

    def sendRequest(self, prompt: str) -> Optional[str]:
        """Sends HTTP request to Groq / Llama API endpoint."""
        if not self.apiKey or self.apiKey in ("mock-key", "change-me", ""):
            logger.info("No valid LLM API key provided. Using built-in AI reasoning engine fallback.")
            return None

        headers = {
            "Authorization": f"Bearer {self.apiKey}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.modelName,
            "messages": [
                {"role": "system", "content": "You are a Kubernetes Auto-scaling decision AI. Always respond in pure JSON."},
                {"role": "user", "content": prompt}
            ],
            "temperature": self.temperature,
            "max_tokens": self.maxTokens,
            "response_format": {"type": "json_object"}
        }

        try:
            response = requests.post(self.endpoint, headers=headers, json=payload, timeout=12)
            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                return content
            else:
                logger.warning(f"LLM API request failed with status {response.status_code}: {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error calling LLM API: {e}")
            return None

    def parseResponse(self, raw_response: str) -> Optional[Dict[str, Any]]:
        """Parses raw text response into JSON dict."""
        try:
            # Clean markdown code blocks if any
            clean_str = raw_response.strip()
            if clean_str.startswith("```json"):
                clean_str = clean_str[7:]
            if clean_str.startswith("```"):
                clean_str = clean_str[3:]
            if clean_str.endswith("```"):
                clean_str = clean_str[:-3]
            return json.loads(clean_str.strip())
        except Exception as e:
            logger.error(f"Failed to parse LLM JSON response: {e}")
            return None

    def validateDecision(self, decision: Dict[str, Any], min_replicas: int, max_replicas: int) -> bool:
        """Validates decision keys and replica bounds."""
        if not isinstance(decision, dict):
            return False
        action = decision.get("action")
        replicas = decision.get("target_replicas")
        if action not in ("SCALE_UP", "SCALE_DOWN", "MAINTAIN"):
            return False
        if not isinstance(replicas, int) or replicas < min_replicas or replicas > max_replicas:
            return False
        return True
