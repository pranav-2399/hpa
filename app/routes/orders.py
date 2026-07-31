import json
from datetime import datetime
from flask import Blueprint, request, g
from app.extensions import db
from app.models import Order, OrderItem, OrderStatusHistory, Product, Coupon, Cart, CartItem, Notification
from app.utils import ok, err, require_auth, require_admin, paginate_query, generate_order_number

orders_bp = Blueprint("orders", __name__)

VALID_STATUSES = ("pending", "processing", "shipped", "delivered", "cancelled", "refunded")


@orders_bp.get("")
@require_auth
def list_orders():
    q = Order.query
    if g.current_user.role != "admin":
        q = q.filter_by(user_id=g.current_user.id)
    if request.args.get("status"):
        q = q.filter_by(status=request.args["status"])
    q = q.order_by(Order.created_at.desc())
    return ok(paginate_query(q))


@orders_bp.post("")
@require_auth
def create_order():
    """Checkout: converts cart to order."""
    body = request.get_json(silent=True) or {}
    user = g.current_user

    # Validate shipping address
    ship_addr = body.get("shipping_address")
    if not ship_addr or not ship_addr.get("line1") or not ship_addr.get("city"):
        return err("shipping_address with line1 and city is required")

    # Load cart
    cart = Cart.query.filter_by(user_id=user.id).first()
    if not cart or cart.items.count() == 0:
        return err("Cart is empty", 400)

    cart_items = cart.items.all()

    # Validate stock and compute subtotal
    subtotal = 0.0
    for ci in cart_items:
        prod = Product.query.with_for_update().get(ci.product_id)
        if not prod or not prod.is_active:
            return err(f"Product '{ci.product_id}' is no longer available", 409)
        if prod.stock_quantity < ci.quantity:
            return err(f"Insufficient stock for '{prod.name}' (available: {prod.stock_quantity})", 409)
        subtotal += float(ci.unit_price) * ci.quantity

    # Coupon
    discount = 0.0
    coupon_code = None
    coupon_id = None
    coupon_code_input = (body.get("coupon_code") or "").strip().upper()
    if coupon_code_input:
        coupon = Coupon.query.filter_by(code=coupon_code_input).first()
        if coupon:
            valid, reason = coupon.is_valid()
            if valid and subtotal >= float(coupon.min_order_amount or 0):
                if coupon.discount_type == "percentage":
                    discount = subtotal * float(coupon.discount_value) / 100
                else:
                    discount = float(coupon.discount_value)
                coupon.used_count = (coupon.used_count or 0) + 1
                coupon_code = coupon.code
                coupon_id = coupon.id

    tax = round(subtotal * 0.08, 2)
    shipping_cost = 0.0 if subtotal >= 50 else 5.99
    total = round(subtotal - discount + tax + shipping_cost, 2)

    order = Order(
        user_id=user.id,
        order_number=generate_order_number(),
        subtotal=subtotal,
        tax_amount=tax,
        shipping_amount=shipping_cost,
        discount_amount=discount,
        total_amount=total,
        shipping_address=json.dumps(ship_addr),
        billing_address=json.dumps(body.get("billing_address") or ship_addr),
        payment_method=body.get("payment_method", "card"),
        payment_status="paid",  # assume payment succeeded
        payment_reference="PAY-" + generate_order_number(),
        coupon_id=coupon_id,
        coupon_code=coupon_code,
        notes=body.get("notes"),
    )
    db.session.add(order)
    db.session.flush()

    # Order items + deduct stock
    for ci in cart_items:
        prod = Product.query.get(ci.product_id)
        oi = OrderItem(
            order_id=order.id, product_id=prod.id,
            product_name=prod.name, product_sku=prod.sku,
            quantity=ci.quantity, unit_price=ci.unit_price,
            total_price=float(ci.unit_price) * ci.quantity,
        )
        db.session.add(oi)
        prod.stock_quantity -= ci.quantity
        prod.total_sold = (prod.total_sold or 0) + ci.quantity

    # Clear cart
    CartItem.query.filter_by(cart_id=cart.id).delete()

    # Notification
    notif = Notification(
        user_id=user.id, type="order_update",
        title="Order Placed",
        message=f"Your order {order.order_number} has been placed successfully.",
        data=json.dumps({"order_id": order.id, "order_number": order.order_number}),
    )
    db.session.add(notif)
    db.session.commit()
    return ok(order.to_dict(include_items=True), "Order placed", 201)


@orders_bp.get("/<int:order_id>")
@require_auth
def get_order(order_id):
    order = Order.query.get_or_404(order_id)
    if order.user_id != g.current_user.id and g.current_user.role != "admin":
        return err("Forbidden", 403)
    return ok(order.to_dict(include_items=True))


@orders_bp.get("/number/<order_number>")
@require_auth
def get_by_number(order_number):
    order = Order.query.filter_by(order_number=order_number).first()
    if not order:
        return err("Order not found", 404)
    if order.user_id != g.current_user.id and g.current_user.role != "admin":
        return err("Forbidden", 403)
    return ok(order.to_dict(include_items=True))


@orders_bp.put("/<int:order_id>/cancel")
@require_auth
def cancel_order(order_id):
    order = Order.query.get_or_404(order_id)
    if order.user_id != g.current_user.id and g.current_user.role != "admin":
        return err("Forbidden", 403)
    if order.status not in ("pending", "processing"):
        return err(f"Cannot cancel order with status '{order.status}'", 409)
    old = order.status
    order.status = "cancelled"
    order.cancelled_at = datetime.utcnow()
    # Restore stock
    for item in order.items:
        prod = Product.query.get(item.product_id)
        if prod:
            prod.stock_quantity = (prod.stock_quantity or 0) + item.quantity
            prod.total_sold = max(0, (prod.total_sold or 0) - item.quantity)
    db.session.add(OrderStatusHistory(order_id=order.id, old_status=old,
                                      new_status="cancelled", created_by=g.current_user.id))
    db.session.commit()
    return ok(order.to_dict())


@orders_bp.put("/<int:order_id>/status")
@require_admin
def update_status(order_id):
    order = Order.query.get_or_404(order_id)
    body = request.get_json(silent=True) or {}
    new_status = body.get("status")
    if new_status not in VALID_STATUSES:
        return err(f"status must be one of {VALID_STATUSES}")
    old = order.status
    order.status = new_status
    if new_status == "shipped":
        order.shipped_at = datetime.utcnow()
    elif new_status == "delivered":
        order.delivered_at = datetime.utcnow()
    elif new_status == "cancelled":
        order.cancelled_at = datetime.utcnow()
    db.session.add(OrderStatusHistory(order_id=order.id, old_status=old,
                                      new_status=new_status, note=body.get("note"),
                                      created_by=g.current_user.id))
    notif = Notification(
        user_id=order.user_id, type="order_update",
        title=f"Order {new_status.capitalize()}",
        message=f"Your order {order.order_number} is now {new_status}.",
        data=json.dumps({"order_id": order.id}),
    )
    db.session.add(notif)
    db.session.commit()
    return ok(order.to_dict())


@orders_bp.get("/<int:order_id>/history")
@require_auth
def order_history(order_id):
    order = Order.query.get_or_404(order_id)
    if order.user_id != g.current_user.id and g.current_user.role != "admin":
        return err("Forbidden", 403)
    history = order.status_history.order_by(OrderStatusHistory.created_at).all()
    return ok([h.to_dict() for h in history])


@orders_bp.get("/<int:order_id>/invoice")
@require_auth
def get_invoice(order_id):
    order = Order.query.get_or_404(order_id)
    if order.user_id != g.current_user.id and g.current_user.role != "admin":
        return err("Forbidden", 403)
    return ok({
        "invoice_number": f"INV-{order.order_number}",
        "order": order.to_dict(include_items=True),
        "generated_at": datetime.utcnow().isoformat(),
    })
