from flask import Blueprint, request, g
from sqlalchemy import or_
from app.extensions import db
from app.models import Product, Category, Tag
from app.utils import ok, err, optional_auth, paginate_query

search_bp = Blueprint("search", __name__)


@search_bp.get("")
@optional_auth
def search():
    q_str = (request.args.get("q") or "").strip()
    if len(q_str) < 2:
        return err("Query must be at least 2 characters")

    pattern = f"%{q_str}%"
    page = max(1, request.args.get("page", 1, int))
    per_page = min(request.args.get("per_page", 20, int), 100)

    # Products
    prod_q = Product.query.filter(
        Product.is_active == True,
        or_(
            Product.name.ilike(pattern),
            Product.description.ilike(pattern),
            Product.short_description.ilike(pattern),
            Product.sku.ilike(pattern),
        )
    )
    if request.args.get("category_id"):
        prod_q = prod_q.filter_by(category_id=int(request.args["category_id"]))
    if request.args.get("min_price"):
        prod_q = prod_q.filter(Product.price >= float(request.args["min_price"]))
    if request.args.get("max_price"):
        prod_q = prod_q.filter(Product.price <= float(request.args["max_price"]))

    prod_q = prod_q.order_by(Product.total_sold.desc(), Product.avg_rating.desc())
    p = prod_q.paginate(page=page, per_page=per_page, error_out=False)

    # Categories (no pagination — usually small)
    cats = Category.query.filter(
        Category.is_active == True,
        or_(Category.name.ilike(pattern), Category.description.ilike(pattern)),
    ).limit(5).all()

    # Tags
    tags = Tag.query.filter(Tag.name.ilike(pattern)).limit(10).all()

    return ok({
        "query": q_str,
        "products": {
            "items": [pr.to_dict(include_images=True, include_tags=False) for pr in p.items],
            "total": p.total, "page": p.page, "pages": p.pages,
        },
        "categories": [c.to_dict() for c in cats],
        "tags": [t.to_dict() for t in tags],
    })


@search_bp.get("/suggestions")
def suggestions():
    q_str = (request.args.get("q") or "").strip()
    if len(q_str) < 1:
        return ok([])
    pattern = f"{q_str}%"
    products = Product.query.filter(
        Product.is_active == True,
        Product.name.ilike(pattern)
    ).order_by(Product.total_sold.desc()).limit(8).all()
    return ok([{"id": p.id, "name": p.name, "slug": p.slug,
                "price": float(p.price), "type": "product"} for p in products])


@search_bp.get("/tags")
def list_tags():
    tags = Tag.query.order_by(Tag.name).all()
    return ok([t.to_dict() for t in tags])


@search_bp.post("/tags")
def create_tag():
    from app.utils import require_admin, slugify
    body = request.get_json(silent=True) or {}
    if not body.get("name"):
        return err("name required")
    from app.utils import slugify
    slug = slugify(body["name"])
    if Tag.query.filter_by(slug=slug).first():
        return err("Tag already exists", 409)
    tag = Tag(name=body["name"], slug=slug)
    db.session.add(tag)
    db.session.commit()
    return ok(tag.to_dict(), "Tag created", 201)
