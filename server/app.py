import os
from datetime import datetime, timezone
from pprint import pprint
from flask import Flask, jsonify, request
from flask_cors import CORS

from autoscaler.config import config
from autoscaler.main import build_autoscaler_agent

def create_server_app():
    app = Flask(__name__)
    CORS(app)  # Enable cross-origin requests for frontend

    # Initialize shared coordinator agent
    coordinator = build_autoscaler_agent()

    @app.route("/api/cluster/status", methods=["GET"])
    def get_cluster_status():
        try:
            pods = coordinator.kubernetesService.getPodStatus()
            snapshot = coordinator.analyzeSystemState(pod_metrics=pods)
            k8s_state = coordinator.kubernetesService.getClusterState()
            request_rates = coordinator.resourceAnalysisService.prometheusService.getRequestRateByPod(config.DEPLOYMENT_NAME)

            payload = jsonify({
                "status": "success",
                "data": {
                    "clusterId": snapshot.clusterId,
                    "activePods": snapshot.activePods,
                    "cpuUsage": snapshot.cpuUsage,
                    "memoryUsage": snapshot.memoryUsage,
                    "requestRate": snapshot.requestRate,
                    "responseTime": snapshot.responseTime,
                    "averageLoad": snapshot.calculateAverageLoad(),
                    "k8sState": k8s_state,
                    "pods": [
                        p.getResourceUtilization() | {
                            "podName": p.podName,
                            "status": p.status,
                            "requestRate": request_rates.get(p.podName)
                        }
                        for p in pods
                    ]
                }
            })            
            return payload
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route("/api/metrics/history", methods=["GET"])
    def get_metrics_history():
        try:
            limit = min(max(int(request.args.get("limit", 30)), 1), 5000)
            start_value = request.args.get("start")
            end_value = request.args.get("end")
            if start_value and end_value:
                start_time = datetime.fromisoformat(start_value.replace("Z", "+00:00"))
                end_time = datetime.fromisoformat(end_value.replace("Z", "+00:00"))
                if start_time.tzinfo:
                    start_time = start_time.astimezone(timezone.utc).replace(tzinfo=None)
                if end_time.tzinfo:
                    end_time = end_time.astimezone(timezone.utc).replace(tzinfo=None)
                if end_time < start_time:
                    return jsonify({"status": "error", "message": "End time must be after start time."}), 400
                snapshots = coordinator.metricRepo.getSnapshotsInRange(
                    config.CLUSTER_ID, start_time, end_time, limit=limit
                )
            else:
                snapshots = list(reversed(coordinator.metricRepo.getRecentSnapshots(config.CLUSTER_ID, limit=limit)))
            return jsonify({
                "status": "success",
                "data": [s.to_dict() for s in snapshots]
            })
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route("/api/agent/decisions", methods=["GET"])
    def get_agent_decisions():
        try:
            limit = int(request.args.get("limit", 20))
            logs = coordinator.decisionRepo.getRecentLogs(limit=limit)
            return jsonify({
                "status": "success",
                "data": [l.to_dict() for l in logs]
            })
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route("/api/actions/history", methods=["GET"])
    def get_scaling_actions():
        try:
            actions = coordinator.actionRepo.findAll()
            sorted_actions = sorted(actions, key=lambda a: a.executedAt, reverse=True)
            return jsonify({
                "status": "success",
                "data": [a.to_dict() for a in sorted_actions[:20]]
            })
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route("/api/agent/trigger", methods=["POST"])
    def trigger_control_loop():
        """Manually triggers one control loop evaluation iteration."""
        try:
            result = coordinator.runSingleControlLoopIteration()
            return jsonify({
                "status": "success",
                "message": "Control loop iteration completed.",
                "data": result
            })
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    return app

if __name__ == "__main__":
    app = create_server_app()
    app.run(host="0.0.0.0", port=5001, debug=True)
