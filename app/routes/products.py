from flask import Blueprint, request, g
from sqlalchemy import or_
from app.extensions import db
from app.models import Product, ProductImage, Tag, Category
from app.utils import ok, err, require_auth, require_admin, optional_auth, paginate_query, slugify

products_bp = Blueprint("products", __name__)


def _base_query(active_only=True):
    q = Product.query
    if active_only:
        q = q.filter_by(is_active=True)
    return q


def _apply_filters(q):
    args = request.args
    if args.get("category_id"):
        q = q.filter_by(category_id=int(args["category_id"]))
    if args.get("min_price"):
        q = q.filter(Product.price >= float(args["min_price"]))
    if args.get("max_price"):
        q = q.filter(Product.price <= float(args["max_price"]))
    if args.get("in_stock") == "true":
        q = q.filter(Product.stock_quantity > 0)
    if args.get("featured") == "true":
        q = q.filter_by(is_featured=True)
    return q


def _apply_sort(q):
    mapping = {
        "price_asc": Product.price.asc(), "price_desc": Product.price.desc(),
        "name_asc": Product.name.asc(), "name_desc": Product.name.desc(),
        "rating_desc": Product.avg_rating.desc(), "newest": Product.created_at.desc(),
        "bestseller": Product.total_sold.desc(),
    }
    return q.order_by(mapping.get(request.args.get("sort", "newest"), Product.created_at.desc()))


@products_bp.get("")
@optional_auth
def list_products():
    q = _base_query()
    q = _apply_filters(q)
    q = _apply_sort(q)
    return ok(paginate_query(q))


@products_bp.get("/featured")
def featured_products():
    q = _base_query().filter_by(is_featured=True).order_by(Product.avg_rating.desc())
    return ok(paginate_query(q))


@products_bp.get("/bestsellers")
def bestsellers():
    q = _base_query().filter(Product.total_sold > 0).order_by(Product.total_sold.desc())
    return ok(paginate_query(q))


@products_bp.get("/low-stock")
@require_admin
def low_stock():
    q = Product.query.filter(
        Product.stock_quantity <= Product.low_stock_threshold,
        Product.is_active == True
    ).order_by(Product.stock_quantity.asc())
    return ok(paginate_query(q))


@products_bp.get("/<int:product_id>")
@optional_auth
def get_product(product_id):
    p = Product.query.get_or_404(product_id)
    # Log product view
    _log_view(p.id)
    return ok(p.to_dict())


@products_bp.get("/slug/<slug>")
@optional_auth
def get_product_by_slug(slug):
    p = Product.query.filter_by(slug=slug).first()
    if not p:
        return err("Product not found", 404)
    _log_view(p.id)
    return ok(p.to_dict())


@products_bp.get("/<int:product_id>/related")
def related_products(product_id):
    p = Product.query.get_or_404(product_id)
    related = Product.query.filter(
        Product.category_id == p.category_id,
        Product.id != p.id,
        Product.is_active == True,
    ).order_by(Product.avg_rating.desc()).limit(8).all()
    return ok([r.to_dict(include_images=True, include_tags=False) for r in related])


@products_bp.post("")
@require_admin
def create_product():
    body = request.get_json(silent=True) or {}
    for field in ("name", "price"):
        if not body.get(field):
            return err(f"'{field}' is required")

    slug = body.get("slug") or slugify(body["name"])
    if Product.query.filter_by(slug=slug).first():
        import secrets as _s
        slug = slug + "-" + _s.token_hex(3)

    p = Product(
        name=body["name"], slug=slug,
        description=body.get("description"),
        short_description=body.get("short_description"),
        price=body["price"],
        compare_price=body.get("compare_price"),
        cost_price=body.get("cost_price"),
        sku=body.get("sku"),
        stock_quantity=body.get("stock_quantity", 0),
        low_stock_threshold=body.get("low_stock_threshold", 10),
        category_id=body.get("category_id"),
        is_active=body.get("is_active", True),
        is_featured=body.get("is_featured", False),
        weight=body.get("weight"),
        dimensions=body.get("dimensions"),
    )
    db.session.add(p)
    db.session.flush()

    # Tags
    for tag_name in body.get("tags", []):
        tag_slug = slugify(tag_name)
        tag = Tag.query.filter_by(slug=tag_slug).first() or Tag(name=tag_name, slug=tag_slug)
        db.session.add(tag)
        p.tags.append(tag)

    # Images
    for img in body.get("images", []):
        db.session.add(ProductImage(product_id=p.id, url=img.get("url", ""),
                                    alt_text=img.get("alt_text"),
                                    sort_order=img.get("sort_order", 0),
                                    is_primary=img.get("is_primary", False)))
    db.session.commit()
    return ok(p.to_dict(), "Product created", 201)


@products_bp.put("/<int:product_id>")
@require_admin
def update_product(product_id):
    p = Product.query.get_or_404(product_id)
    body = request.get_json(silent=True) or {}
    for field in ("name", "description", "short_description", "price", "compare_price",
                  "cost_price", "sku", "stock_quantity", "low_stock_threshold",
                  "category_id", "is_active", "is_featured", "weight", "dimensions"):
        if field in body:
            setattr(p, field, body[field])
    if "slug" in body:
        p.slug = body["slug"]
    db.session.commit()
    return ok(p.to_dict())


@products_bp.delete("/<int:product_id>")
@require_admin
def delete_product(product_id):
    p = Product.query.get_or_404(product_id)
    p.is_active = False   # soft delete
    db.session.commit()
    return ok(msg="Product deactivated")


@products_bp.put("/<int:product_id>/stock")
@require_admin
def update_stock(product_id):
    p = Product.query.get_or_404(product_id)
    body = request.get_json(silent=True) or {}
    op = body.get("operation", "set")   # set | increment | decrement
    qty = int(body.get("quantity", 0))
    if op == "set":
        p.stock_quantity = qty
    elif op == "increment":
        p.stock_quantity = (p.stock_quantity or 0) + qty
    elif op == "decrement":
        p.stock_quantity = max(0, (p.stock_quantity or 0) - qty)
    else:
        return err("operation must be set|increment|decrement")
    db.session.commit()
    return ok({"id": p.id, "stock_quantity": p.stock_quantity})


@products_bp.post("/<int:product_id>/images")
@require_admin
def add_image(product_id):
    p = Product.query.get_or_404(product_id)
    body = request.get_json(silent=True) or {}
    if not body.get("url"):
        return err("url is required")
    img = ProductImage(product_id=p.id, url=body["url"],
                       alt_text=body.get("alt_text"),
                       sort_order=body.get("sort_order", 0),
                       is_primary=body.get("is_primary", False))
    db.session.add(img)
    db.session.commit()
    return ok(img.to_dict(), "Image added", 201)


@products_bp.delete("/<int:product_id>/images/<int:img_id>")
@require_admin
def delete_image(product_id, img_id):
    img = ProductImage.query.filter_by(id=img_id, product_id=product_id).first()
    if not img:
        return err("Image not found", 404)
    db.session.delete(img)
    db.session.commit()
    return ok(msg="Image deleted")


@products_bp.post("/bulk")
@require_admin
def bulk_operation():
    """Bulk activate/deactivate/delete products."""
    body = request.get_json(silent=True) or {}
    ids = body.get("ids", [])
    op = body.get("operation")
    if not ids or op not in ("activate", "deactivate", "delete"):
        return err("ids[] and operation (activate|deactivate|delete) required")
    products = Product.query.filter(Product.id.in_(ids)).all()
    for p in products:
        if op == "activate":
            p.is_active = True
        elif op == "deactivate":
            p.is_active = False
        elif op == "delete":
            db.session.delete(p)
    db.session.commit()
    return ok({"affected": len(products)})


def _log_view(product_id):
    from app.models import AnalyticsEvent
    import json
    evt = AnalyticsEvent(
        user_id=getattr(g, "current_user", None) and g.current_user.id,
        event_type="product_view",
        event_data=json.dumps({"product_id": product_id}),
        ip_address=request.remote_addr,
    )
    db.session.add(evt)
    db.session.commit()
