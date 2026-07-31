import time
from datetime import datetime
from flask import Blueprint, jsonify, current_app
from app.extensions import db

health_bp = Blueprint("health", __name__)

_start_time = time.time()


@health_bp.get("/")
def index():
    return jsonify({"service": "hpa-flask", "status": "ok", "ts": datetime.utcnow().isoformat()})


@health_bp.get("/health")
def health():
    try:
        db.session.execute(db.text("SELECT 1"))
        db_status = "ok"
    except Exception as e:
        db_status = str(e)
    return jsonify({"status": "healthy", "db": db_status, "ts": datetime.utcnow().isoformat()})


@health_bp.get("/ready")
def ready():
    return jsonify({"ready": True}), 200


@health_bp.get("/ping")
def ping():
    return jsonify({"pong": True, "ts": datetime.utcnow().isoformat()})


@health_bp.get("/metrics")
def metrics():
    from app.models import User, Product, Order, Review, AnalyticsEvent
    uptime = round(time.time() - _start_time, 2)
    return jsonify({
        "uptime_seconds": uptime,
        "counts": {
            "users": User.query.count(),
            "products": Product.query.count(),
            "orders": Order.query.count(),
            "reviews": Review.query.count(),
            "analytics_events": AnalyticsEvent.query.count(),
        },
        "ts": datetime.utcnow().isoformat(),
    })
