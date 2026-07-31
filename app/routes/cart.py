import json
from datetime import datetime
from flask import Blueprint, request, g
from app.extensions import db
from app.models import Cart, CartItem, Product, Coupon
from app.utils import ok, err, require_auth, optional_auth

cart_bp = Blueprint("cart", __name__)


def _get_or_create_cart():
    """Return the cart for the authenticated user or guest session."""
    if g.current_user:
        cart = Cart.query.filter_by(user_id=g.current_user.id).first()
        if not cart:
            cart = Cart(user_id=g.current_user.id)
            db.session.add(cart)
            db.session.commit()
        return cart
    # Guest cart via X-Session-Key header
    sk = request.headers.get("X-Session-Key")
    if not sk:
        return None
    cart = Cart.query.filter_by(session_key=sk).first()
    if not cart:
        cart = Cart(session_key=sk)
        db.session.add(cart)
        db.session.commit()
    return cart


@cart_bp.get("")
@optional_auth
def get_cart():
    cart = _get_or_create_cart()
    if not cart:
        return err("Provide Authorization or X-Session-Key header", 400)
    return ok(cart.to_dict())


@cart_bp.post("/items")
@optional_auth
def add_item():
    cart = _get_or_create_cart()
    if not cart:
        return err("Provide Authorization or X-Session-Key header", 400)
    body = request.get_json(silent=True) or {}
    product_id = body.get("product_id")
    qty = int(body.get("quantity", 1))
    if not product_id or qty < 1:
        return err("product_id and quantity >= 1 required")

    product = Product.query.filter_by(id=product_id, is_active=True).first()
    if not product:
        return err("Product not found", 404)
    if product.stock_quantity < qty:
        return err(f"Only {product.stock_quantity} in stock", 409)

    existing = CartItem.query.filter_by(cart_id=cart.id, product_id=product_id).first()
    if existing:
        new_qty = existing.quantity + qty
        if product.stock_quantity < new_qty:
            return err(f"Only {product.stock_quantity} in stock", 409)
        existing.quantity = new_qty
        existing.unit_price = product.price
    else:
        item = CartItem(cart_id=cart.id, product_id=product_id,
                        quantity=qty, unit_price=product.price)
        db.session.add(item)
    db.session.commit()
    return ok(cart.to_dict(), "Item added")


@cart_bp.put("/items/<int:item_id>")
@optional_auth
def update_item(item_id):
    cart = _get_or_create_cart()
    if not cart:
        return err("Auth required", 400)
    item = CartItem.query.filter_by(id=item_id, cart_id=cart.id).first()
    if not item:
        return err("Cart item not found", 404)
    body = request.get_json(silent=True) or {}
    qty = int(body.get("quantity", item.quantity))
    if qty < 1:
        return err("Quantity must be >= 1")
    if item.product.stock_quantity < qty:
        return err(f"Only {item.product.stock_quantity} in stock", 409)
    item.quantity = qty
    db.session.commit()
    return ok(cart.to_dict())


@cart_bp.delete("/items/<int:item_id>")
@optional_auth
def remove_item(item_id):
    cart = _get_or_create_cart()
    if not cart:
        return err("Auth required", 400)
    item = CartItem.query.filter_by(id=item_id, cart_id=cart.id).first()
    if not item:
        return err("Cart item not found", 404)
    db.session.delete(item)
    db.session.commit()
    return ok(cart.to_dict())


@cart_bp.delete("")
@optional_auth
def clear_cart():
    cart = _get_or_create_cart()
    if not cart:
        return err("Auth required", 400)
    CartItem.query.filter_by(cart_id=cart.id).delete()
    db.session.commit()
    return ok(msg="Cart cleared")


@cart_bp.post("/apply-coupon")
@optional_auth
def apply_coupon():
    cart = _get_or_create_cart()
    if not cart:
        return err("Auth required", 400)
    body = request.get_json(silent=True) or {}
    code = (body.get("code") or "").strip().upper()
    if not code:
        return err("Coupon code required")
    coupon = Coupon.query.filter_by(code=code).first()
    if not coupon:
        return err("Coupon not found", 404)
    valid, reason = coupon.is_valid()
    if not valid:
        return err(reason, 400)
    total = cart.total()
    if float(coupon.min_order_amount or 0) > float(total):
        return err(f"Minimum order amount is {coupon.min_order_amount}", 400)

    if coupon.discount_type == "percentage":
        discount = float(total) * float(coupon.discount_value) / 100
    else:
        discount = float(coupon.discount_value)

    return ok({
        "coupon": coupon.to_dict(),
        "cart_total": float(total),
        "discount": round(discount, 2),
        "final_total": round(float(total) - discount, 2),
    })


@cart_bp.get("/summary")
@optional_auth
def cart_summary():
    cart = _get_or_create_cart()
    if not cart:
        return err("Auth required", 400)
    items = list(cart.items)
    subtotal = float(cart.total())
    tax = round(subtotal * 0.08, 2)
    shipping = 0.0 if subtotal >= 50 else 5.99
    return ok({
        "item_count": len(items),
        "subtotal": subtotal,
        "tax": tax,
        "shipping": shipping,
        "total": round(subtotal + tax + shipping, 2),
    })
