import json
from datetime import datetime, timedelta
from flask import Blueprint, request, g
from sqlalchemy import func
from app.extensions import db
from app.models import AnalyticsEvent, Product, Order, User
from app.utils import ok, err, require_admin, optional_auth, paginate_query

analytics_bp = Blueprint("analytics", __name__)

VALID_EVENTS = {
    "page_view", "product_view", "add_to_cart", "remove_from_cart",
    "checkout_start", "purchase", "search", "signup", "login",
    "wishlist_add", "review_submit", "coupon_apply",
}


@analytics_bp.post("/events")
@optional_auth
def track_event():
    body = request.get_json(silent=True) or {}
    event_type = body.get("event_type")
    if not event_type:
        return err("event_type required")
    if event_type not in VALID_EVENTS:
        return err(f"event_type must be one of: {sorted(VALID_EVENTS)}")

    event = AnalyticsEvent(
        user_id=g.current_user.id if g.current_user else None,
        session_key=body.get("session_key") or request.headers.get("X-Session-Key"),
        event_type=event_type,
        event_data=json.dumps(body.get("data") or {}),
        ip_address=request.remote_addr,
        user_agent=(request.user_agent.string or "")[:300],
        page_url=body.get("page_url"),
        referrer=body.get("referrer"),
    )
    db.session.add(event)
    db.session.commit()
    return ok({"id": event.id}, "Event tracked", 201)


@analytics_bp.get("/events")
@require_admin
def list_events():
    q = AnalyticsEvent.query
    if request.args.get("event_type"):
        q = q.filter_by(event_type=request.args["event_type"])
    if request.args.get("user_id"):
        q = q.filter_by(user_id=int(request.args["user_id"]))
    q = q.order_by(AnalyticsEvent.created_at.desc())
    return ok(paginate_query(q))


@analytics_bp.get("/dashboard")
@require_admin
def dashboard():
    days = int(request.args.get("days", 30))
    since = datetime.utcnow() - timedelta(days=days)

    total_orders = Order.query.filter(Order.created_at >= since).count()
    revenue = db.session.query(func.sum(Order.total_amount)).filter(
        Order.created_at >= since, Order.payment_status == "paid"
    ).scalar() or 0

    new_users = User.query.filter(User.created_at >= since).count()

    event_breakdown = db.session.query(
        AnalyticsEvent.event_type, func.count(AnalyticsEvent.id)
    ).filter(AnalyticsEvent.created_at >= since).group_by(AnalyticsEvent.event_type).all()

    # Daily revenue for chart
    daily_revenue = db.session.query(
        func.date(Order.created_at).label("day"),
        func.sum(Order.total_amount).label("revenue"),
        func.count(Order.id).label("orders"),
    ).filter(
        Order.created_at >= since,
        Order.payment_status == "paid",
    ).group_by(func.date(Order.created_at)).order_by(func.date(Order.created_at)).all()

    # Top products by sales
    from app.models import OrderItem
    top_products = db.session.query(
        OrderItem.product_id, OrderItem.product_name,
        func.sum(OrderItem.quantity).label("units"),
        func.sum(OrderItem.total_price).label("revenue"),
    ).join(Order).filter(
        Order.created_at >= since,
        Order.payment_status == "paid",
    ).group_by(OrderItem.product_id).order_by(func.sum(OrderItem.total_price).desc()).limit(10).all()

    return ok({
        "period_days": days,
        "summary": {
            "total_orders": total_orders,
            "revenue": float(revenue),
            "new_users": new_users,
        },
        "event_breakdown": {et: cnt for et, cnt in event_breakdown},
        "daily_revenue": [
            {"day": str(r.day), "revenue": float(r.revenue or 0), "orders": r.orders}
            for r in daily_revenue
        ],
        "top_products": [
            {"product_id": r.product_id, "name": r.product_name,
             "units_sold": int(r.units or 0), "revenue": float(r.revenue or 0)}
            for r in top_products
        ],
    })


@analytics_bp.get("/products/<int:product_id>")
@require_admin
def product_analytics(product_id):
    days = int(request.args.get("days", 30))
    since = datetime.utcnow() - timedelta(days=days)
    views = AnalyticsEvent.query.filter(
        AnalyticsEvent.event_type == "product_view",
        AnalyticsEvent.event_data.contains(str(product_id)),
        AnalyticsEvent.created_at >= since,
    ).count()
    from app.models import OrderItem
    sales = db.session.query(func.sum(OrderItem.quantity)).filter(
        OrderItem.product_id == product_id,
    ).scalar() or 0
    return ok({"product_id": product_id, "views": views, "total_sold": int(sales), "period_days": days})
