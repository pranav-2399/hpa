import json
import random
from datetime import datetime, timedelta
from flask import Blueprint, request, g
from sqlalchemy import func
from app.extensions import db
from app.models import (User, Product, Order, Review, Category, Tag,
                        Coupon, Notification, AnalyticsEvent, UserSession)
from app.utils import ok, err, require_admin, paginate_query, slugify

admin_bp = Blueprint("admin", __name__)


# ── Dashboard ─────────────────────────────────────────────────────────────────
@admin_bp.get("/dashboard")
@require_admin
def dashboard():
    now = datetime.utcnow()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    revenue_today = db.session.query(func.sum(Order.total_amount)).filter(
        Order.created_at >= today, Order.payment_status == "paid"
    ).scalar() or 0
    revenue_month = db.session.query(func.sum(Order.total_amount)).filter(
        Order.created_at >= this_month, Order.payment_status == "paid"
    ).scalar() or 0

    return ok({
        "users": {
            "total": User.query.count(),
            "active": User.query.filter_by(is_active=True).count(),
            "new_today": User.query.filter(User.created_at >= today).count(),
        },
        "products": {
            "total": Product.query.count(),
            "active": Product.query.filter_by(is_active=True).count(),
            "low_stock": Product.query.filter(
                Product.stock_quantity <= Product.low_stock_threshold,
                Product.is_active == True
            ).count(),
            "out_of_stock": Product.query.filter_by(stock_quantity=0, is_active=True).count(),
        },
        "orders": {
            "total": Order.query.count(),
            "pending": Order.query.filter_by(status="pending").count(),
            "processing": Order.query.filter_by(status="processing").count(),
            "today": Order.query.filter(Order.created_at >= today).count(),
        },
        "revenue": {
            "today": float(revenue_today),
            "this_month": float(revenue_month),
        },
        "reviews": {
            "total": Review.query.count(),
            "pending": Review.query.filter_by(status="pending").count(),
        },
    })


# ── User management ───────────────────────────────────────────────────────────
@admin_bp.put("/users/<int:uid>/role")
@require_admin
def set_role(uid):
    user = User.query.get_or_404(uid)
    body = request.get_json(silent=True) or {}
    role = body.get("role")
    if role not in ("admin", "moderator", "user"):
        return err("role must be admin|moderator|user")
    user.role = role
    db.session.commit()
    return ok(user.to_dict())


@admin_bp.put("/users/<int:uid>/ban")
@require_admin
def ban_user(uid):
    user = User.query.get_or_404(uid)
    if user.id == g.current_user.id:
        return err("Cannot ban yourself")
    body = request.get_json(silent=True) or {}
    action = body.get("action", "ban")   # ban | unban
    if action == "ban":
        user.banned_at = datetime.utcnow()
        user.ban_reason = body.get("reason", "Violated terms of service")
        user.is_active = False
        UserSession.query.filter_by(user_id=uid).update({"is_revoked": True})
    else:
        user.banned_at = None
        user.ban_reason = None
        user.is_active = True
    db.session.commit()
    return ok(user.to_dict(include_private=True))


# ── Order management ──────────────────────────────────────────────────────────
@admin_bp.get("/orders")
@require_admin
def all_orders():
    q = Order.query
    if request.args.get("status"):
        q = q.filter_by(status=request.args["status"])
    if request.args.get("payment_status"):
        q = q.filter_by(payment_status=request.args["payment_status"])
    q = q.order_by(Order.created_at.desc())
    return ok(paginate_query(q))


@admin_bp.get("/revenue")
@require_admin
def revenue_report():
    days = int(request.args.get("days", 30))
    since = datetime.utcnow() - timedelta(days=days)
    rows = db.session.query(
        func.date(Order.created_at).label("day"),
        func.count(Order.id).label("orders"),
        func.sum(Order.total_amount).label("revenue"),
        func.sum(Order.discount_amount).label("discounts"),
    ).filter(Order.created_at >= since, Order.payment_status == "paid"
    ).group_by(func.date(Order.created_at)).order_by(func.date(Order.created_at)).all()
    return ok([{
        "day": str(r.day), "orders": r.orders,
        "revenue": float(r.revenue or 0), "discounts": float(r.discounts or 0),
    } for r in rows])


@admin_bp.get("/inventory")
@require_admin
def inventory():
    q = Product.query.filter_by(is_active=True).order_by(Product.stock_quantity.asc())
    return ok(paginate_query(q, serializer=lambda p: {
        "id": p.id, "name": p.name, "sku": p.sku,
        "stock_quantity": p.stock_quantity,
        "low_stock_threshold": p.low_stock_threshold,
        "status": "out" if p.stock_quantity == 0 else (
            "low" if p.stock_quantity <= p.low_stock_threshold else "ok"
        ),
    }))


# ── Coupon management ─────────────────────────────────────────────────────────
@admin_bp.get("/coupons")
@require_admin
def list_coupons():
    coupons = Coupon.query.order_by(Coupon.created_at.desc()).all()
    return ok([c.to_dict() for c in coupons])


@admin_bp.post("/coupons")
@require_admin
def create_coupon():
    body = request.get_json(silent=True) or {}
    for f in ("code", "discount_type", "discount_value"):
        if not body.get(f):
            return err(f"'{f}' required")
    if body["discount_type"] not in ("percentage", "fixed"):
        return err("discount_type must be percentage|fixed")
    if Coupon.query.filter_by(code=body["code"].upper()).first():
        return err("Coupon code already exists", 409)
    coupon = Coupon(
        code=body["code"].upper(), description=body.get("description"),
        discount_type=body["discount_type"], discount_value=body["discount_value"],
        min_order_amount=body.get("min_order_amount", 0),
        max_uses=body.get("max_uses"),
        starts_at=datetime.fromisoformat(body["starts_at"]) if body.get("starts_at") else None,
        expires_at=datetime.fromisoformat(body["expires_at"]) if body.get("expires_at") else None,
    )
    db.session.add(coupon)
    db.session.commit()
    return ok(coupon.to_dict(), "Coupon created", 201)


@admin_bp.put("/coupons/<int:cid>")
@require_admin
def update_coupon(cid):
    coupon = Coupon.query.get_or_404(cid)
    body = request.get_json(silent=True) or {}
    for f in ("description", "discount_value", "min_order_amount", "max_uses", "is_active"):
        if f in body:
            setattr(coupon, f, body[f])
    db.session.commit()
    return ok(coupon.to_dict())


@admin_bp.delete("/coupons/<int:cid>")
@require_admin
def delete_coupon(cid):
    coupon = Coupon.query.get_or_404(cid)
    db.session.delete(coupon)
    db.session.commit()
    return ok(msg="Coupon deleted")


# ── Broadcast notification ────────────────────────────────────────────────────
@admin_bp.post("/notifications/broadcast")
@require_admin
def broadcast_notification():
    body = request.get_json(silent=True) or {}
    if not body.get("title") or not body.get("message"):
        return err("title and message required")
    users = User.query.filter_by(is_active=True, email_notifications=True).all()
    notifs = [
        Notification(user_id=u.id, type=body.get("type", "system"),
                     title=body["title"], message=body["message"],
                     data=json.dumps(body.get("data") or {}))
        for u in users
    ]
    db.session.bulk_save_objects(notifs)
    db.session.commit()
    return ok({"sent_to": len(notifs)}, "Broadcast sent")


# ── Seed data ─────────────────────────────────────────────────────────────────
@admin_bp.post("/seed")
def seed():
    """Populate the DB with realistic sample data. Safe to call multiple times."""
    counts = {"users": 0, "categories": 0, "products": 0, "orders": 0, "reviews": 0}

    # Admin user
    if not User.query.filter_by(email="admin@example.com").first():
        admin = User(username="admin", email="admin@example.com",
                     first_name="Admin", last_name="User", role="admin",
                     is_active=True, is_verified=True)
        admin.set_password("admin1234")
        db.session.add(admin)
        counts["users"] += 1

    # Regular users
    for i in range(1, 11):
        email = f"user{i}@example.com"
        if not User.query.filter_by(email=email).first():
            u = User(username=f"user{i}", email=email,
                     first_name=f"First{i}", last_name=f"Last{i}",
                     role="user", is_active=True, is_verified=True)
            u.set_password("password123")
            db.session.add(u)
            counts["users"] += 1

    db.session.flush()

    # Categories
    cat_names = ["Electronics", "Clothing", "Books", "Home & Garden", "Sports", "Toys", "Beauty", "Food"]
    cat_map = {}
    for name in cat_names:
        slug = slugify(name)
        cat = Category.query.filter_by(slug=slug).first()
        if not cat:
            cat = Category(name=name, slug=slug,
                           description=f"Everything in {name}",
                           is_active=True)
            db.session.add(cat)
            counts["categories"] += 1
        cat_map[name] = cat

    db.session.flush()

    # Tags
    tag_names = ["sale", "new-arrival", "trending", "eco-friendly", "limited-edition", "bestseller"]
    tag_map = {}
    for tname in tag_names:
        tag = Tag.query.filter_by(slug=tname).first()
        if not tag:
            tag = Tag(name=tname, slug=tname)
            db.session.add(tag)
        tag_map[tname] = tag

    db.session.flush()

    # Products
    product_data = [
        ("Wireless Noise-Cancelling Headphones", "Electronics", 299.99, 50),
        ("4K Smart TV 55 inch", "Electronics", 799.99, 20),
        ("Mechanical Keyboard RGB", "Electronics", 149.99, 100),
        ("Premium Running Shoes", "Clothing", 129.99, 200),
        ("Slim Fit Denim Jacket", "Clothing", 89.99, 150),
        ("The Art of Clean Code", "Books", 34.99, 300),
        ("Python for Data Science", "Books", 44.99, 250),
        ("Ergonomic Office Chair", "Home & Garden", 399.99, 30),
        ("Smart Coffee Maker", "Home & Garden", 79.99, 80),
        ("Yoga Mat Premium", "Sports", 49.99, 500),
        ("Protein Powder Vanilla 2kg", "Food", 59.99, 120),
        ("LEGO Architecture Set", "Toys", 89.99, 60),
        ("Vitamin C Serum", "Beauty", 29.99, 400),
        ("Bluetooth Speaker Portable", "Electronics", 79.99, 180),
        ("Stainless Steel Water Bottle", "Home & Garden", 24.99, 350),
    ]

    products = []
    for name, cat_name, price, stock in product_data:
        slug = slugify(name)
        p = Product.query.filter_by(slug=slug).first()
        if not p:
            p = Product(
                name=name, slug=slug,
                description=f"High quality {name}. Perfect for everyday use. Comes with a 1-year warranty and free shipping on orders over $50.",
                short_description=f"Top-rated {name} loved by thousands of customers.",
                price=price,
                compare_price=round(price * 1.2, 2),
                cost_price=round(price * 0.6, 2),
                sku=f"SKU-{slugify(name)[:10].upper()}-{random.randint(1000,9999)}",
                stock_quantity=stock,
                category_id=cat_map[cat_name].id,
                is_active=True,
                is_featured=random.random() > 0.6,
                avg_rating=round(random.uniform(3.5, 5.0), 1),
                total_reviews=random.randint(5, 200),
                total_sold=random.randint(10, 1000),
            )
            p.tags.append(tag_map[random.choice(tag_names)])
            db.session.add(p)
            counts["products"] += 1
            products.append(p)

    db.session.flush()

    # Coupon
    if not Coupon.query.filter_by(code="WELCOME10").first():
        db.session.add(Coupon(
            code="WELCOME10", description="10% off your first order",
            discount_type="percentage", discount_value=10,
            min_order_amount=30, is_active=True,
        ))
    if not Coupon.query.filter_by(code="SAVE20").first():
        db.session.add(Coupon(
            code="SAVE20", description="$20 off orders over $100",
            discount_type="fixed", discount_value=20,
            min_order_amount=100, is_active=True,
        ))

    db.session.commit()
    return ok(counts, "Seed complete", 201)
