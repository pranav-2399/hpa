from flask import Blueprint, request, g
from app.extensions import db
from app.models import User, Order, Review, WishlistItem, Address, Notification
from app.utils import ok, err, require_auth, require_admin, paginate_query

users_bp = Blueprint("users", __name__)


def _own_or_admin(user_id):
    """Return True if request user owns the resource or is admin."""
    return g.current_user.id == user_id or g.current_user.role == "admin"


# ── User listing (admin only) ────────────────────────────────────────────────
@users_bp.get("")
@require_admin
def list_users():
    q = User.query
    if request.args.get("role"):
        q = q.filter_by(role=request.args["role"])
    if request.args.get("search"):
        s = f"%{request.args['search']}%"
        q = q.filter(db.or_(User.username.ilike(s), User.email.ilike(s)))
    q = q.order_by(User.created_at.desc())
    return ok(paginate_query(q, serializer=lambda u: u.to_dict(include_private=True)))


@users_bp.get("/<int:uid>")
@require_auth
def get_user(uid):
    user = User.query.get_or_404(uid)
    include_private = _own_or_admin(uid)
    return ok(user.to_dict(include_private=include_private))


@users_bp.put("/<int:uid>")
@require_auth
def update_user(uid):
    if not _own_or_admin(uid):
        return err("Forbidden", 403)
    user = User.query.get_or_404(uid)
    body = request.get_json(silent=True) or {}
    allowed = ["first_name", "last_name", "bio", "phone", "avatar_url", "email_notifications"]
    if g.current_user.role == "admin":
        allowed += ["role", "is_active", "is_verified"]
    for field in allowed:
        if field in body:
            setattr(user, field, body[field])
    db.session.commit()
    return ok(user.to_dict())


@users_bp.delete("/<int:uid>")
@require_admin
def delete_user(uid):
    user = User.query.get_or_404(uid)
    user.is_active = False
    db.session.commit()
    return ok(msg="User deactivated")


# ── Orders ────────────────────────────────────────────────────────────────────
@users_bp.get("/<int:uid>/orders")
@require_auth
def user_orders(uid):
    if not _own_or_admin(uid):
        return err("Forbidden", 403)
    q = Order.query.filter_by(user_id=uid).order_by(Order.created_at.desc())
    return ok(paginate_query(q))


# ── Reviews ───────────────────────────────────────────────────────────────────
@users_bp.get("/<int:uid>/reviews")
@require_auth
def user_reviews(uid):
    if not _own_or_admin(uid):
        return err("Forbidden", 403)
    q = Review.query.filter_by(user_id=uid).order_by(Review.created_at.desc())
    return ok(paginate_query(q))


# ── Wishlist ──────────────────────────────────────────────────────────────────
@users_bp.get("/<int:uid>/wishlist")
@require_auth
def get_wishlist(uid):
    if not _own_or_admin(uid):
        return err("Forbidden", 403)
    q = WishlistItem.query.filter_by(user_id=uid).order_by(WishlistItem.created_at.desc())
    return ok(paginate_query(q))


@users_bp.post("/<int:uid>/wishlist")
@require_auth
def add_to_wishlist(uid):
    if not _own_or_admin(uid):
        return err("Forbidden", 403)
    body = request.get_json(silent=True) or {}
    product_id = body.get("product_id")
    if not product_id:
        return err("product_id required")
    existing = WishlistItem.query.filter_by(user_id=uid, product_id=product_id).first()
    if existing:
        return err("Already in wishlist", 409)
    item = WishlistItem(user_id=uid, product_id=product_id)
    db.session.add(item)
    db.session.commit()
    return ok(item.to_dict(), "Added to wishlist", 201)


@users_bp.delete("/<int:uid>/wishlist/<int:product_id>")
@require_auth
def remove_from_wishlist(uid, product_id):
    if not _own_or_admin(uid):
        return err("Forbidden", 403)
    item = WishlistItem.query.filter_by(user_id=uid, product_id=product_id).first()
    if not item:
        return err("Not in wishlist", 404)
    db.session.delete(item)
    db.session.commit()
    return ok(msg="Removed from wishlist")


# ── Addresses ─────────────────────────────────────────────────────────────────
@users_bp.get("/<int:uid>/addresses")
@require_auth
def list_addresses(uid):
    if not _own_or_admin(uid):
        return err("Forbidden", 403)
    addrs = Address.query.filter_by(user_id=uid).order_by(Address.is_default.desc()).all()
    return ok([a.to_dict() for a in addrs])


@users_bp.post("/<int:uid>/addresses")
@require_auth
def add_address(uid):
    if not _own_or_admin(uid):
        return err("Forbidden", 403)
    body = request.get_json(silent=True) or {}
    for f in ("line1", "city", "country"):
        if not body.get(f):
            return err(f"'{f}' is required")
    if body.get("is_default"):
        Address.query.filter_by(user_id=uid).update({"is_default": False})
    addr = Address(user_id=uid, label=body.get("label", "Home"),
                   first_name=body.get("first_name"), last_name=body.get("last_name"),
                   line1=body["line1"], line2=body.get("line2"),
                   city=body["city"], state=body.get("state"),
                   postal_code=body.get("postal_code"), country=body["country"],
                   phone=body.get("phone"), is_default=body.get("is_default", False))
    db.session.add(addr)
    db.session.commit()
    return ok(addr.to_dict(), "Address added", 201)


@users_bp.put("/<int:uid>/addresses/<int:addr_id>")
@require_auth
def update_address(uid, addr_id):
    if not _own_or_admin(uid):
        return err("Forbidden", 403)
    addr = Address.query.filter_by(id=addr_id, user_id=uid).first()
    if not addr:
        return err("Address not found", 404)
    body = request.get_json(silent=True) or {}
    if body.get("is_default"):
        Address.query.filter_by(user_id=uid).update({"is_default": False})
    for f in ("label", "first_name", "last_name", "line1", "line2",
              "city", "state", "postal_code", "country", "phone", "is_default"):
        if f in body:
            setattr(addr, f, body[f])
    db.session.commit()
    return ok(addr.to_dict())


@users_bp.delete("/<int:uid>/addresses/<int:addr_id>")
@require_auth
def delete_address(uid, addr_id):
    if not _own_or_admin(uid):
        return err("Forbidden", 403)
    addr = Address.query.filter_by(id=addr_id, user_id=uid).first()
    if not addr:
        return err("Address not found", 404)
    db.session.delete(addr)
    db.session.commit()
    return ok(msg="Address deleted")


# ── Notifications ─────────────────────────────────────────────────────────────
@users_bp.get("/<int:uid>/notifications")
@require_auth
def user_notifications(uid):
    if not _own_or_admin(uid):
        return err("Forbidden", 403)
    q = Notification.query.filter_by(user_id=uid).order_by(Notification.created_at.desc())
    return ok(paginate_query(q))
